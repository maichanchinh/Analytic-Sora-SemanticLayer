"""FastMCP report tools over the shared semantic registry and query service."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import logging
from threading import RLock
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from sora_semantic.data.silver import SilverDataSource, SilverReadError
from sora_semantic.semantic.query import (
    DateRange,
    QueryContractError,
    QueryRequest,
    QueryResult,
    QueryService,
)
from sora_semantic.semantic.registry import SemanticRegistry


_REPORT_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
_USER_AGGREGATION_NOTE = (
    "active_users và new_users là tổng các chỉ số theo country rows và từng ngày; "
    "không đảm bảo là số người dùng duy nhất trên toàn app hoặc cả kỳ."
)
_FINANCE_NOTE = (
    "Revenue lấy từ AdMob, cost lấy từ Google Ads; tổng VND chỉ gồm các dòng "
    "có thể quy đổi theo FX policy của finance_daily."
)


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
    """Create an MCP server exposing report-ready tools."""
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
            "Dùng get_business_summary để lấy report tổng hoặc lọc theo app_id; "
            "dùng get_top_apps để xếp hạng app theo revenue VND hoặc ROAS VND. "
            "Ngày mặc định là hôm qua theo Asia/Ho_Chi_Minh. User metrics được "
            "cộng từ country rows và không đảm bảo là số user duy nhất."
        ),
        lifespan=lifespan,
    )

    @server.tool
    def list_apps() -> dict[str, list[dict[str, Any]]]:
        """Liệt kê các app có trong Silver để lọc report."""
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
    def get_business_summary(
        date_range: dict[str, str] | None = None,
        app_id: str | None = None,
    ) -> dict[str, Any]:
        """Trả revenue VND, cost VND, ROAS, active users và new users.

        Mặc định lấy hôm qua theo Asia/Ho_Chi_Minh. Nếu không truyền app_id,
        kết quả tổng hợp mọi app. User counts được cộng qua country rows.
        """
        resolved_range = _resolve_date_range(date_range)
        filters = {"app_id": app_id} if app_id is not None else {}
        try:
            finance = _query(
                services,
                QueryRequest(
                    model="finance_daily",
                    metrics=("revenue_vnd", "cost_vnd", "roas_vnd"),
                    filters=filters,
                    date_range=DateRange.from_mapping(resolved_range),
                ),
            )
            users = _query(
                services,
                QueryRequest(
                    model="ga4_daily_overview",
                    metrics=("active_users", "new_users"),
                    filters=filters,
                    date_range=DateRange.from_mapping(resolved_range),
                ),
            )
        except QueryContractError as error:
            raise ToolError(str(error), log_level=logging.DEBUG) from None

        finance_row = _first_row(finance)
        users_row = _first_row(users)
        return {
            "date_range": resolved_range,
            "app_id": app_id,
            "currency": "VND",
            "revenue_vnd": finance_row.get("revenue_vnd"),
            "cost_vnd": finance_row.get("cost_vnd"),
            "roas_vnd": finance_row.get("roas_vnd"),
            "active_users": users_row.get("active_users"),
            "new_users": users_row.get("new_users"),
            "notes": [_FINANCE_NOTE, _USER_AGGREGATION_NOTE],
        }

    @server.tool
    def get_top_apps(
        sort_by: Literal["revenue", "roas"] = "revenue",
        date_range: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trả top 5 app theo revenue VND hoặc ROAS đã chuẩn hóa sang VND."""
        resolved_range = _resolve_date_range(date_range)
        try:
            query_range = DateRange.from_mapping(resolved_range)
            finance = _query(
                services,
                QueryRequest(
                    model="finance_daily",
                    metrics=("revenue_vnd", "cost_vnd", "roas_vnd"),
                    dimensions=("app_id",),
                    date_range=query_range,
                ),
            )
            users = _query(
                services,
                QueryRequest(
                    model="ga4_daily_overview",
                    metrics=("active_users", "new_users"),
                    dimensions=("app_id",),
                    date_range=query_range,
                ),
            )
            apps = _query(
                services,
                QueryRequest(
                    model="dim_app",
                    dimensions=("app_id", "display_name"),
                ),
            )
        except QueryContractError as error:
            raise ToolError(str(error), log_level=logging.DEBUG) from None

        users_by_app = {row["app_id"]: row for row in users.rows}
        names_by_app = {row["app_id"]: row.get("display_name") for row in apps.rows}
        ranked_rows = []
        rank_field = "revenue_vnd" if sort_by == "revenue" else "roas_vnd"
        for row in finance.rows:
            rank_value = row.get(rank_field)
            if rank_value is None:
                continue
            user_row = users_by_app.get(row["app_id"], {})
            ranked_rows.append(
                {
                    "app_id": row["app_id"],
                    "display_name": names_by_app.get(row["app_id"]),
                    "revenue_vnd": row.get("revenue_vnd"),
                    "cost_vnd": row.get("cost_vnd"),
                    "roas_vnd": row.get("roas_vnd"),
                    "active_users": user_row.get("active_users"),
                    "new_users": user_row.get("new_users"),
                }
            )
        ranked_rows.sort(
            key=lambda row: (-row[rank_field], row["app_id"]),
        )
        return {
            "date_range": resolved_range,
            "sort_by": sort_by,
            "currency": "VND",
            "apps": ranked_rows[:5],
            "notes": [_FINANCE_NOTE, _USER_AGGREGATION_NOTE],
        }

    return server


def _resolve_date_range(date_range: Mapping[str, str] | None) -> dict[str, str]:
    if date_range is not None:
        return dict(date_range)
    yesterday = _yesterday_report_date()
    iso_date = yesterday.isoformat()
    return {"from": iso_date, "to": iso_date}


def _yesterday_report_date() -> date:
    return datetime.now(_REPORT_TIMEZONE).date() - timedelta(days=1)


def _first_row(result: QueryResult) -> dict[str, Any]:
    return result.rows[0] if result.rows else {}


def _query(services: dict[str, Any], request: QueryRequest) -> QueryResult:
    try:
        with services["query_lock"]:
            return services["query_service"].query(request)
    except SilverReadError:
        raise ToolError("Silver data source is unavailable.") from None


mcp = create_mcp_server()
