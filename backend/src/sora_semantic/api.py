"""FastAPI application exposing the shared semantic query service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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


def create_app(
    *,
    source_factory: Callable[[], SilverDataSource] = SilverDataSource.from_env,
    dashboard_config_dir: Path | None = None,
) -> FastAPI:
    """Create the API app; source creation is deferred until ASGI startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        source = source_factory()
        try:
            source.connect()
            app.state.silver_source = source
            app.state.semantic_registry = SemanticRegistry(source)
            app.state.query_service = QueryService(app.state.semantic_registry)
            app.state.query_lock = RLock()
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
        query = QueryRequest(
            model="dim_app",
            dimensions=("app_id", "display_name", "package_name", "platform", "status"),
        )
        result = _execute_app_query(request.app, query)
        apps = sorted(
            result.rows,
            key=lambda row: (str(row.get("display_name") or "").casefold(), row["app_id"]),
        )
        return {"apps": list(apps)}

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
    def run_query(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        try:
            query = QueryRequest.from_mapping(payload)
        except QueryContractError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

        result = _execute_app_query(request.app, query)
        return {
            "model": result.model,
            "dimensions": result.dimensions,
            "metrics": result.metrics,
            "rows": result.rows,
        }

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


app = create_app()
