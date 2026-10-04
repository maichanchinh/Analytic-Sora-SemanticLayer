"""FastMCP interface over the shared semantic registry and query service."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import logging
from threading import RLock
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from sora_semantic.data.silver import SilverDataSource, SilverReadError
from sora_semantic.semantic.query import (
    QueryContractError,
    QueryRequest,
    QueryResult,
    QueryService,
)
from sora_semantic.semantic.registry import SemanticRegistry


@asynccontextmanager
async def _silver_services(
    source_factory: Callable[[], SilverDataSource],
) -> AsyncIterator[tuple[SemanticRegistry, QueryService, RLock]]:
    source = source_factory()
    try:
        source.connect()
        registry = SemanticRegistry(source)
        yield registry, QueryService(registry), RLock()
    finally:
        source.close()


def create_mcp_server(
    *,
    source_factory: Callable[[], SilverDataSource] = SilverDataSource.from_env,
) -> FastMCP:
    """Create an MCP server whose tools share one registry and query service."""
    services: dict[str, Any] = {}

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with _silver_services(source_factory) as runtime:
            services.update(registry=runtime[0], query_service=runtime[1], query_lock=runtime[2])
            try:
                yield {}
            finally:
                services.clear()

    server = FastMCP(
        name="Sora Semantic Layer",
        instructions=(
            "Discover registered apps and metrics, then query only registered "
            "semantic models, metrics, dimensions, and filters."
        ),
        lifespan=lifespan,
    )

    @server.tool
    def list_apps() -> dict[str, list[dict[str, Any]]]:
        """List apps available in the Silver semantic model."""
        request = QueryRequest(
            model="dim_app",
            dimensions=("app_id", "display_name", "package_name", "platform", "status"),
        )
        result = _query(services, request)
        apps = sorted(
            result.rows,
            key=lambda row: (str(row.get("display_name") or "").casefold(), row["app_id"]),
        )
        return {"apps": list(apps)}

    @server.tool
    def list_metrics() -> dict[str, list[dict[str, Any]]]:
        """List registered metrics grouped by semantic model."""
        definitions = services["registry"].describe()
        return {
            "models": [
                {"model": definition["name"], "metrics": definition["metrics"]}
                for definition in definitions
                if definition["metrics"]
            ]
        }

    @server.tool
    def query_metrics(
        model: str,
        metrics: list[str] | None = None,
        dimensions: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        date_range: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Query registered metrics and dimensions through the shared service."""
        try:
            payload: dict[str, Any] = {
                "model": model,
                "metrics": metrics or [],
                "dimensions": dimensions or [],
                "filters": filters or {},
            }
            if date_range is not None:
                payload["date_range"] = date_range
            result = _query(services, QueryRequest.from_mapping(payload))
        except QueryContractError as error:
            raise ToolError(str(error), log_level=logging.DEBUG) from None
        return {
            "model": result.model,
            "dimensions": list(result.dimensions),
            "metrics": list(result.metrics),
            "rows": list(result.rows),
        }

    return server


def _query(services: dict[str, Any], request: QueryRequest) -> QueryResult:
    try:
        with services["query_lock"]:
            return services["query_service"].query(request)
    except SilverReadError:
        raise ToolError("Silver data source is unavailable.") from None


mcp = create_mcp_server()
