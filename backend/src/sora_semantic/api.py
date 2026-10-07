"""FastAPI application exposing the shared semantic query service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import timedelta
import logging
import os
from pathlib import Path
import re
from threading import RLock
import time
from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sora_semantic.data.silver import SilverDataSource, SilverReadError
from sora_semantic.dashboard_configs import (
    DashboardConfigError,
    DashboardConfigStore,
    DashboardNotFoundError,
)
from sora_semantic.semantic.query import (
    QueryContractError,
    QueryRequest,
    QueryResult,
    QueryService,
    QUERY_DIAGNOSTIC_ID,
    safe_error_summary,
)
from sora_semantic.semantic.registry import SemanticRegistry

_LOGGER = logging.getLogger(__name__)
_MAX_SILVER_RECONNECT_ATTEMPTS = 3
_SILVER_RECONNECT_BACKOFF_SECONDS = (0.5, 1.0)


class DateRangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from", description="Inclusive start date (YYYY-MM-DD).")
    to: str = Field(description="Inclusive end date (YYYY-MM-DD).")


class QueryRequestBody(BaseModel):
    """OpenAPI schema for the shared semantic query request."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(description="Registered semantic model name.")
    metrics: list[str] = Field(default_factory=list, description="Metrics registered on model.")
    dimensions: list[str] = Field(
        default_factory=list, description="Dimensions to return from the model."
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Dimension filters; each value is a scalar equality or a list of values.",
    )
    date_range: DateRangeBody | None = Field(
        default=None,
        description="Optional inclusive range applied to the model time dimension.",
    )
    compare_previous_period: bool = Field(
        default=False,
        description="Include per-dimension comparisons with the immediately preceding period of equal length.",
    )

    def to_query_request(self) -> QueryRequest:
        return QueryRequest.from_mapping(
            self.model_dump(
                mode="python",
                by_alias=True,
                exclude={"compare_previous_period", "id"},
            )
        )


class QueryBatchItemBody(QueryRequestBody):
    """One independently evaluated query in a dashboard batch."""

    id: str = Field(min_length=1, description="Client correlation ID, usually the widget ID.")


class QueryBatchBody(BaseModel):
    """Multiple semantic queries submitted through the existing query endpoint."""

    model_config = ConfigDict(extra="forbid")

    queries: list[QueryBatchItemBody] = Field(min_length=1)

    @field_validator("queries")
    @classmethod
    def unique_query_ids(cls, queries: list[QueryBatchItemBody]):
        ids = [query.id for query in queries]
        if len(ids) != len(set(ids)):
            raise ValueError("queries must have unique ids.")
        return queries


def _default_source_factory() -> SilverDataSource:
    return SilverDataSource.from_env()


def create_app(
    *,
    source_factory: Callable[[], SilverDataSource] = _default_source_factory,
    dashboard_config_dir: Path | None = None,
) -> FastAPI:
    """Create the API app; source creation is deferred until ASGI startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        source = source_factory()
        try:
            source.connect()
            validate_read_access = getattr(source, "validate_read_access", None)
            if validate_read_access is not None:
                validate_read_access()
            app.state.silver_source = source
            app.state.semantic_registry = SemanticRegistry(source)
            app.state.query_service = QueryService(app.state.semantic_registry)
            app.state.query_lock = RLock()
            app.state.apps_cache = []
            yield
        finally:
            source.close()

    app = FastAPI(
        title="Sora Semantic Layer API",
        version="1.0.0",
        lifespan=lifespan,
    )
    cors_origins = os.getenv(
        "DASHBOARD_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins.split(",") if origin.strip()],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.state.dashboard_config_store = DashboardConfigStore(dashboard_config_dir)

    @app.get("/api/v1/apps")
    def list_apps(request: Request) -> dict[str, list[dict[str, Any]]]:
        try:
            with request.app.state.query_lock:
                apps = request.app.state.query_service.query(
                    QueryRequest(
                        model="dim_app",
                        dimensions=("app_id", "display_name", "package_name", "platform", "status"),
                    )
                )
                request.app.state.apps_cache = sorted(
                    apps.rows,
                    key=lambda row: (str(row.get("display_name") or "").casefold(), row["app_id"]),
                )
                return {"apps": list(request.app.state.apps_cache)}
        except SilverReadError:
            raise HTTPException(
                status_code=503,
                detail="Silver data source is unavailable.",
            ) from None

    @app.get("/api/v1/metrics")
    def list_metrics(request: Request) -> dict[str, list[dict[str, Any]]]:
        definitions = request.app.state.semantic_registry.describe()
        return {
            "models": [
                {"model": definition["name"], "metrics": definition["metrics"]}
                for definition in definitions
                if definition["metrics"]
            ]
        }

    @app.get("/api/v1/dimensions")
    def list_dimensions(request: Request) -> dict[str, list[dict[str, Any]]]:
        definitions = request.app.state.semantic_registry.describe()
        return {
            "models": [
                {"model": definition["name"], "dimensions": definition["dimensions"]}
                for definition in definitions
                if definition["dimensions"]
            ]
        }

    @app.post("/api/v1/query")
    def run_query(
        request: Request,
        response: Response,
        payload: QueryRequestBody | QueryBatchBody = Body(
            openapi_examples={
                "app_daily_live_sample": {
                    "summary": "App daily: live Charge Speed sample",
                    "description": "Real Silver row for 2026-10-05; shows native revenue and cost currencies.",
                    "value": {
                        "model": "app_daily",
                        "metrics": ["admob_revenue_native", "google_ads_cost_native"],
                        "dimensions": [
                            "business_date",
                            "app_id",
                            "revenue_currency_code",
                            "cost_currency_code",
                        ],
                        "filters": {"app_id": "com.chargespeed.charge"},
                        "date_range": {"from": "2026-10-05", "to": "2026-10-05"},
                    },
                },
                "campaign_geo": {
                    "summary": "Campaign spend: live campaign and country",
                    "description": "Real Silver row for Charge Speed-Global-IAA in KM on 2026-10-05.",
                    "value": {
                        "model": "campaign_geo",
                        "metrics": ["campaign_spend"],
                        "dimensions": ["campaign_name", "country_code", "currency_code"],
                        "filters": {
                            "campaign_name": "Charge Speed-Global-IAA",
                            "country_code": "KM",
                        },
                        "date_range": {"from": "2026-10-05", "to": "2026-10-05"},
                    },
                },
                "retention_cohort": {
                    "summary": "Retention: live Charge Speed cohort",
                    "description": "Real GA4 cohort for Charge Speed in ZZ on 2026-08-01.",
                    "value": {
                        "model": "ga4_retention_cohort",
                        "metrics": ["cohort_users", "retained_users", "retention_rate"],
                        "dimensions": ["cohort_date", "cohort_day"],
                        "filters": {"app_id": "com.chargespeed.charge", "country_code": "ZZ"},
                        "date_range": {"from": "2026-08-01", "to": "2026-08-01"},
                    },
                },
            }
        ),
    ) -> dict[str, Any]:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_request_id if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", supplied_request_id) else uuid4().hex
        response.headers["X-Request-ID"] = request_id
        diagnostic_token = QUERY_DIAGNOSTIC_ID.set(request_id)
        if isinstance(payload, QueryBatchBody):
            try:
                return _run_query_batch(request.app, payload)
            finally:
                QUERY_DIAGNOSTIC_ID.reset(diagnostic_token)

        try:
            query = payload.to_query_request()
        except QueryContractError as error:
            QUERY_DIAGNOSTIC_ID.reset(diagnostic_token)
            raise HTTPException(status_code=422, detail=str(error)) from None
        try:
            return _run_one_query(request.app, query, payload.compare_previous_period)
        except SilverReadError:
            raise HTTPException(
                status_code=503,
                detail="Silver data source is unavailable.",
            ) from None
        except QueryContractError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        finally:
            QUERY_DIAGNOSTIC_ID.reset(diagnostic_token)

    @app.get("/api/v1/dashboards")
    def list_dashboards(request: Request) -> dict[str, list[dict[str, str]]]:
        try:
            dashboards = request.app.state.dashboard_config_store.list()
        except DashboardConfigError:
            raise HTTPException(
                status_code=500,
                detail="Dashboard configs are unavailable.",
            ) from None
        return {"dashboards": dashboards}

    @app.get("/api/v1/dashboards/{dashboard_id}")
    def get_dashboard(dashboard_id: str, request: Request) -> dict[str, Any]:
        try:
            return request.app.state.dashboard_config_store.get(dashboard_id)
        except DashboardNotFoundError:
            raise HTTPException(status_code=404, detail="Dashboard not found.") from None
        except DashboardConfigError:
            raise HTTPException(
                status_code=500,
                detail="Dashboard config is unavailable.",
            ) from None

    return app


def _run_one_query(
    app: FastAPI,
    query: QueryRequest,
    compare_previous_period: bool,
    reconnect_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if reconnect_state is None:
        reconnect_state = {"recovery_used": False, "terminal": False}
    if compare_previous_period and query.date_range is None:
        raise HTTPException(
            status_code=422,
            detail="compare_previous_period requires date_range.",
        )

    result = _execute_app_query(app, query, reconnect_state)
    response: dict[str, Any] = {
        "model": result.model,
        "dimensions": result.dimensions,
        "metrics": result.metrics,
        "rows": result.rows,
    }
    if compare_previous_period:
        start = QueryService._parse_date(query.date_range.from_, "date_range.from")
        end = QueryService._parse_date(query.date_range.to, "date_range.to")
        period_days = (end - start).days + 1
        previous_request = QueryRequest(
            model=query.model,
            metrics=query.metrics,
            dimensions=query.dimensions,
            filters=query.filters,
            date_range=type(query.date_range)(
                from_=start - timedelta(days=period_days),
                to=start - timedelta(days=1),
            ),
        )
        previous = _execute_app_query(app, previous_request, reconnect_state)
        response["comparisons"] = _build_comparisons(result, previous)
    return response


def _run_query_batch(app: FastAPI, payload: QueryBatchBody) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    reconnect_state: dict[str, Any] = {"recovery_used": False, "terminal": False}
    silver_unavailable = False
    # Keep the batch serialized and allow one bounded recovery cycle for the whole batch.
    with app.state.query_lock:
        for item in payload.queries:
            if reconnect_state["terminal"]:
                silver_unavailable = True
                results.append({"id": item.id, "error": "Silver data source is unavailable."})
                continue
            item_started_at = time.perf_counter()
            try:
                query = item.to_query_request()
                result = _run_one_query(
                    app,
                    query,
                    item.compare_previous_period,
                    reconnect_state,
                )
                results.append({"id": item.id, "result": result})
            except HTTPException as error:
                detail = error.detail if isinstance(error.detail, str) else "Query failed."
                results.append({"id": item.id, "error": detail})
            except QueryContractError as error:
                results.append({"id": item.id, "error": str(error)})
            except SilverReadError:
                silver_unavailable = True
                reconnect_state["terminal"] = True
                results.append({"id": item.id, "error": "Silver data source is unavailable."})
            finally:
                _LOGGER.info(
                    "Silver batch query completed: request_id=%s widget_id=%s model=%s date_from=%s date_to=%s duration_ms=%.1f outcome=%s",
                    QUERY_DIAGNOSTIC_ID.get(), item.id, item.model,
                    item.date_range.from_ if item.date_range else None,
                    item.date_range.to if item.date_range else None,
                    (time.perf_counter() - item_started_at) * 1000,
                    "error" if results and "error" in results[-1] else "success",
                )
    if silver_unavailable and not any("result" in item for item in results):
        raise HTTPException(
            status_code=503,
            detail="Silver data source is unavailable.",
        )
    return {"results": results}


def _execute_app_query(
    app: FastAPI,
    query: QueryRequest,
    reconnect_state: dict[str, Any] | None = None,
) -> QueryResult:
    # QueryService lazily caches direct Silver table expressions; serialize registry access.
    state = reconnect_state if reconnect_state is not None else {
        "recovery_used": False,
        "terminal": False,
    }
    with app.state.query_lock:
        try:
            return _execute_query(app.state.query_service, query)
        except SilverReadError:
            if state["terminal"] or state["recovery_used"]:
                state["terminal"] = True
                raise
            state["recovery_used"] = True
            try:
                _reconnect_silver(app)
                result = _execute_query(app.state.query_service, query)
            except SilverReadError:
                state["terminal"] = True
                raise
            return result


def _reconnect_silver(app: FastAPI) -> None:
    """Retry rebuilding the DuckDB session, validating read access before reuse."""
    last_error: SilverReadError | None = None
    for attempt in range(_MAX_SILVER_RECONNECT_ATTEMPTS):
        if attempt:
            time.sleep(_SILVER_RECONNECT_BACKOFF_SECONDS[attempt - 1])
        try:
            _reconnect_silver_once(app)
            return
        except SilverReadError as error:
            last_error = error
            _LOGGER.warning(
                "Silver reconnect attempt failed: request_id=%s attempt=%s/%s error_type=%s cause=%s",
                QUERY_DIAGNOSTIC_ID.get(), attempt + 1, _MAX_SILVER_RECONNECT_ATTEMPTS,
                type(error).__name__, safe_error_summary(error),
            )
    raise last_error or SilverReadError("Silver data source is unavailable.")


def _reconnect_silver_once(app: FastAPI) -> None:
    """Rebuild the in-memory DuckDB session and all expressions after a read failure."""
    source = app.state.silver_source
    try:
        source.close()
        source.connect()
        validate_read_access = getattr(source, "validate_read_access", None)
        if validate_read_access is not None:
            validate_read_access()
    except Exception as error:
        _LOGGER.error(
            "Silver reconnect failed: request_id=%s error_type=%s cause=%s",
            QUERY_DIAGNOSTIC_ID.get(), type(error).__name__, safe_error_summary(error),
        )
        raise SilverReadError("Silver data source is unavailable.") from None
    app.state.semantic_registry = SemanticRegistry(source)
    app.state.query_service = QueryService(app.state.semantic_registry)


def _execute_query(service: QueryService, query: QueryRequest) -> QueryResult:
    try:
        return service.query(query)
    except QueryContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except SilverReadError:
        raise


def _build_comparisons(current: QueryResult, previous: QueryResult) -> list[dict[str, Any]]:
    """Join previous-period metric values to current rows by requested dimensions."""
    dimension_names = tuple(item["name"] for item in current.dimensions)
    metric_names = tuple(item["name"] for item in current.metrics)

    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(row.get(name) for name in dimension_names)

    previous_by_key = {key(row): row for row in previous.rows}
    comparisons: list[dict[str, Any]] = []
    for row in current.rows:
        previous_row = previous_by_key.get(key(row), {})
        values: dict[str, dict[str, float | None]] = {}
        for name in metric_names:
            before = previous_row.get(name)
            now = row.get(name)
            before_number = float(before) if isinstance(before, int | float) else None
            now_number = float(now) if isinstance(now, int | float) else None
            delta = now_number - before_number if now_number is not None and before_number is not None else None
            percent = (
                delta / abs(before_number) * 100
                if delta is not None and before_number != 0
                else None
            )
            values[name] = {
                "previous": before_number,
                "delta": delta,
                "percent_change": percent,
            }
        comparisons.append(
            {
                "dimensions": {name: row.get(name) for name in dimension_names},
                "metrics": values,
            }
        )
    return comparisons


app = create_app()
