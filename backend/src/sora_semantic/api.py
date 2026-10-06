"""FastAPI application exposing the shared semantic query service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import timedelta
import os
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

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
)
from sora_semantic.semantic.registry import SemanticRegistry


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
            self.model_dump(mode="python", by_alias=True, exclude={"compare_previous_period"})
        )


def _default_source_factory() -> SilverDataSource:
    backend_dir = Path(__file__).resolve().parents[2]
    configured_path = os.environ.get("SORASEMANTIC_DUCKDB_PATH", "").strip()
    cache_path = (
        Path(configured_path)
        if configured_path
        else backend_dir / ".cache" / "sora-semantic.duckdb"
    )
    if not cache_path.is_absolute():
        cache_path = backend_dir / cache_path
    return SilverDataSource.from_env(database_path=cache_path)


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
            refresh_cached_datasets = getattr(source, "refresh_cached_datasets", None)
            if refresh_cached_datasets is not None:
                refresh_cached_datasets()
            app.state.silver_source = source
            app.state.semantic_registry = SemanticRegistry(source)
            app.state.query_service = QueryService(app.state.semantic_registry)
            app.state.query_lock = RLock()
            apps = app.state.query_service.query(
                QueryRequest(
                    model="dim_app",
                    dimensions=("app_id", "display_name", "package_name", "platform", "status"),
                )
            )
            app.state.apps_cache = sorted(
                apps.rows,
                key=lambda row: (str(row.get("display_name") or "").casefold(), row["app_id"]),
            )
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
        allow_headers=["Content-Type"],
    )
    app.state.dashboard_config_store = DashboardConfigStore(dashboard_config_dir)

    @app.get("/api/v1/apps")
    def list_apps(request: Request) -> dict[str, list[dict[str, Any]]]:
        return {"apps": list(request.app.state.apps_cache)}

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
        payload: QueryRequestBody = Body(
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
        try:
            query = payload.to_query_request()
        except QueryContractError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

        result = _execute_app_query(request.app, query)
        response: dict[str, Any] = {
            "model": result.model,
            "dimensions": result.dimensions,
            "metrics": result.metrics,
            "rows": result.rows,
        }
        if payload.compare_previous_period:
            if query.date_range is None:
                raise HTTPException(
                    status_code=422,
                    detail="compare_previous_period requires date_range.",
                )
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
            previous = _execute_app_query(request.app, previous_request)
            response["comparisons"] = _build_comparisons(result, previous)
        return response

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


def _execute_app_query(app: FastAPI, query: QueryRequest) -> QueryResult:
    # QueryService lazily caches semantic tables; serialize access to its registry.
    with app.state.query_lock:
        return _execute_query(app.state.query_service, query)


def _execute_query(service: QueryService, query: QueryRequest) -> QueryResult:
    try:
        return service.query(query)
    except QueryContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except SilverReadError:
        raise HTTPException(
            status_code=503,
            detail="Silver data source is unavailable.",
        ) from None


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
