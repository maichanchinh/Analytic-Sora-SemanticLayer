from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import date
from unittest.mock import patch

import ibis
from httpx import ASGITransport, AsyncClient

from sora_semantic.api import create_app
from sora_semantic.data.silver import SilverReadError
from sora_semantic.semantic.registry import SemanticRegistry
from test_support import ignore_known_ibis_duckdb_deprecation


APP_ROWS = [
    {
        "app_id": "app.b",
        "display_name": "Beta",
        "package_name": "example.beta",
        "platform": "android",
        "status": "active",
    },
    {
        "app_id": "app.a",
        "display_name": "Alpha",
        "package_name": "example.alpha",
        "platform": "android",
        "status": "active",
    },
]

DATE_ROWS = [
    {
        "date": date(2026, 10, day),
        "year": 2026,
        "quarter": 4,
        "month": 10,
        "week": 40,
        "day_of_month": day,
        "day_of_week": date(2026, 10, day).isoweekday(),
        "month_start": date(2026, 10, 1),
        "week_start": date(2026, 9, 28),
        "is_weekend": date(2026, 10, day).weekday() >= 5,
    }
    for day in (1, 2, 3)
]


class InMemorySilverSource:
    def __init__(self) -> None:
        self.backend = ibis.duckdb.connect()
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True
        return self

    def table(self, name: str):
        if name == "dim_app":
            return self.backend.create_table(name, APP_ROWS)
        if name == "dim_date":
            return self.backend.create_table(name, DATE_ROWS)
        else:
            raise KeyError(name)

    def close(self) -> None:
        self.closed = True
        self.backend.disconnect()


class UnavailableSilverSource(InMemorySilverSource):
    def table(self, name: str):
        raise SilverReadError("Could not register Silver dataset 'dim_app'.")


class BrokenSilverSource(InMemorySilverSource):
    def table(self, name: str):
        raise RuntimeError("private connection detail")


@asynccontextmanager
async def api_client(app, *, raise_app_exceptions: bool = True):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
            base_url="http://testserver",
        ) as client:
            yield client


class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ignore_known_ibis_duckdb_deprecation()

    async def test_apps_are_read_from_silver_and_sorted_by_display_name(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            response = await client.get("/api/v1/apps")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [app["app_id"] for app in response.json()["apps"]],
            ["app.a", "app.b"],
        )
        self.assertTrue(source.connected)
        self.assertTrue(source.closed)

    async def test_metric_and_dimension_catalogs_are_grouped_by_semantic_model(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            metrics = await client.get("/api/v1/metrics")
            dimensions = await client.get("/api/v1/dimensions")

        self.assertEqual(metrics.status_code, 200)
        metric_models = {item["model"]: item["metrics"] for item in metrics.json()["models"]}
        self.assertIn("revenue_usd", {item["name"] for item in metric_models["finance_daily"]})
        self.assertEqual(dimensions.status_code, 200)
        dimension_models = {
            item["model"]: item["dimensions"] for item in dimensions.json()["models"]
        }
        self.assertIn(
            "cohort_day",
            {item["name"] for item in dimension_models["ga4_retention_cohort"]},
        )
        self.assertTrue(source.closed)

    async def test_query_uses_shared_query_service_and_returns_metadata_and_rows(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            response = await client.post(
                "/api/v1/query",
                json={
                    "model": "dim_app",
                    "dimensions": ["app_id", "display_name"],
                    "filters": {"app_id": "app.a"},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model"], "dim_app")
        self.assertEqual(body["metrics"], [])
        self.assertEqual(body["rows"], [{"app_id": "app.a", "display_name": "Alpha"}])
        self.assertEqual([item["name"] for item in body["dimensions"]], ["app_id", "display_name"])

    async def test_query_applies_inclusive_date_range(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            response = await client.post(
                "/api/v1/query",
                json={
                    "model": "dim_date",
                    "dimensions": ["date"],
                    "date_range": {"from": "2026-10-01", "to": "2026-10-02"},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["date"] for row in response.json()["rows"]],
            ["2026-10-01", "2026-10-02"],
        )

    async def test_query_contract_errors_return_422(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            response = await client.post(
                "/api/v1/query",
                json={"model": "missing_model", "metrics": ["revenue_usd"]},
            )
            unsupported_filter = await client.post(
                "/api/v1/query",
                json={
                    "model": "dim_app",
                    "dimensions": ["app_id"],
                    "filters": {"campaign_id": "campaign-1"},
                },
            )
            malformed = await client.post("/api/v1/query", json=[])

        self.assertEqual(response.status_code, 422)
        self.assertIn("Unsupported semantic model", response.json()["detail"])
        self.assertEqual(unsupported_filter.status_code, 422)
        self.assertIn("Unsupported filter", unsupported_filter.json()["detail"])
        self.assertEqual(malformed.status_code, 422)

    async def test_silver_read_errors_return_sanitized_503(self) -> None:
        source = UnavailableSilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            response = await client.get("/api/v1/apps")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Silver data source is unavailable.")
        self.assertNotIn("dim_app", response.text)

    async def test_unexpected_query_errors_return_generic_500(self) -> None:
        source = BrokenSilverSource()
        async with api_client(
            create_app(source_factory=lambda: source),
            raise_app_exceptions=False,
        ) as client:
            response = await client.get("/api/v1/apps")

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private connection detail", response.text)

    async def test_dashboard_list_and_detail_return_registry_backed_ua_config(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            listing = await client.get("/api/v1/dashboards")
            detail = await client.get("/api/v1/dashboards/ua_app_overview")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(
            listing.json(),
            {"dashboards": [{"id": "ua_app_overview", "title": "UA App Overview"}]},
        )
        self.assertEqual(detail.status_code, 200)
        dashboard = detail.json()
        self.assertEqual(
            dashboard["filters"], ["app_id", "country_code", "date_range"]
        )
        definitions = {item["name"]: item for item in SemanticRegistry().describe()}
        for widget in dashboard["widgets"]:
            self.assertIn(widget["type"], {"metric", "area_chart", "bar_chart", "table"})
            self.assertGreaterEqual(widget["span"], 1)
            self.assertIn(widget["model"], definitions)
            model = definitions[widget["model"]]
            self.assertLessEqual(
                set(widget.get("metrics", [])),
                {item["name"] for item in model["metrics"]},
            )
            self.assertLessEqual(
                set(widget.get("dimensions", [])),
                {item["name"] for item in model["dimensions"]},
            )
            self.assertLessEqual(
                set(widget.get("filters", [])),
                {item["name"] for item in model["dimensions"]},
            )

    async def test_dashboard_cors_allows_configured_frontend_origin(self) -> None:
        source = InMemorySilverSource()
        with patch.dict("os.environ", {"DASHBOARD_CORS_ORIGINS": "http://localhost:3000"}):
            async with api_client(create_app(source_factory=lambda: source)) as client:
                response = await client.options(
                    "/api/v1/dashboards",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "GET",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), "http://localhost:3000"
        )

    async def test_unknown_and_invalid_dashboard_ids_return_404(self) -> None:
        source = InMemorySilverSource()
        async with api_client(create_app(source_factory=lambda: source)) as client:
            missing = await client.get("/api/v1/dashboards/unknown_dashboard")
            invalid = await client.get("/api/v1/dashboards/invalid.id")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(missing.json()["detail"], "Dashboard not found.")

    async def test_invalid_dashboard_json_returns_sanitized_500(self) -> None:
        source = InMemorySilverSource()
        with TemporaryDirectory() as temporary_directory:
            config_dir = Path(temporary_directory)
            (config_dir / "broken.json").write_text("{invalid", encoding="utf-8")
            (config_dir / "wrong_shape.json").write_text("[]", encoding="utf-8")
            async with api_client(
                create_app(
                    source_factory=lambda: source,
                    dashboard_config_dir=config_dir,
                )
            ) as client:
                listing = await client.get("/api/v1/dashboards")
                detail = await client.get("/api/v1/dashboards/broken")
                wrong_shape = await client.get("/api/v1/dashboards/wrong_shape")

        self.assertEqual(listing.status_code, 500)
        self.assertEqual(listing.json()["detail"], "Dashboard configs are unavailable.")
        self.assertEqual(detail.status_code, 500)
        self.assertEqual(detail.json()["detail"], "Dashboard config is unavailable.")
        self.assertEqual(wrong_shape.status_code, 500)

    async def test_empty_dashboard_directory_returns_empty_list(self) -> None:
        source = InMemorySilverSource()
        with TemporaryDirectory() as temporary_directory:
            async with api_client(
                create_app(
                    source_factory=lambda: source,
                    dashboard_config_dir=Path(temporary_directory),
                )
            ) as client:
                response = await client.get("/api/v1/dashboards")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"dashboards": []})


if __name__ == "__main__":
    unittest.main()
