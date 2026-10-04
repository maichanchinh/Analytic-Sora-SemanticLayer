from datetime import date
import unittest

import ibis

from sora_semantic.semantic.dimensions import DimensionDefinition
from sora_semantic.semantic.metrics import MetricDefinition
from sora_semantic.semantic.models.base import SilverSemanticDefinition
from sora_semantic.semantic.query import (
    DateRange,
    QueryContractError,
    QueryRequest,
    QueryService,
)
from sora_semantic.semantic.registry import SemanticRegistry
from test_support import ignore_known_ibis_duckdb_deprecation


class LocalRegistry:
    def __init__(self, definition, table):
        self.definitions = (definition,)
        self._table = table

    def get(self, name):
        if name != self._table.name:
            raise KeyError(name)
        return self._table


class InMemorySilverSource:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return self._tables[name]


class QueryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ignore_known_ibis_duckdb_deprecation()

    def setUp(self):
        self.backend = ibis.duckdb.connect()
        source = self.backend.create_table(
            "daily",
            [
                {"business_date": date(2026, 10, 1), "country_code": "US", "revenue": 10},
                {"business_date": date(2026, 10, 2), "country_code": "US", "revenue": 20},
                {"business_date": date(2026, 10, 3), "country_code": "CA", "revenue": 30},
            ],
        )
        self.definition = SilverSemanticDefinition(
            name="daily",
            grain=("business_date", "country_code"),
            dimensions=(
                DimensionDefinition("business_date", "business_date", "Date", "day", time=True),
                DimensionDefinition("country_code", "country_code", "Country", "country"),
            ),
            metrics=(MetricDefinition("revenue", "revenue", "Revenue", "USD"),),
            description="Daily test model.",
        )
        registry = LocalRegistry(self.definition, self.definition.build(source))
        self.service = QueryService(registry)

    def tearDown(self):
        self.backend.disconnect()

    def test_query_applies_in_filter_and_inclusive_date_range_without_output_date(self):
        result = self.service.query(
            QueryRequest.from_mapping(
                {
                    "model": "daily",
                    "metrics": ["revenue"],
                    "dimensions": ["country_code"],
                    "filters": {"country_code": ["US", "CA"]},
                    "date_range": {"from": "2026-10-02", "to": "2026-10-03"},
                }
            )
        )

        self.assertEqual(result.model, "daily")
        self.assertEqual(
            {row["country_code"]: row["revenue"] for row in result.rows},
            {"CA": 30, "US": 20},
        )
        self.assertEqual(result.metrics[0]["unit"], "USD")

    def test_rejects_unknown_model_and_fields(self):
        with self.assertRaisesRegex(QueryContractError, "Unsupported semantic model"):
            self.service.query(QueryRequest(model="missing", metrics=("revenue",)))
        with self.assertRaisesRegex(QueryContractError, "Unsupported metric"):
            self.service.query(QueryRequest(model="daily", metrics=("unknown",)))
        with self.assertRaisesRegex(QueryContractError, "Unsupported filter"):
            self.service.query(QueryRequest(model="daily", dimensions=("country_code",), filters={"bad": "US"}))

    def test_scalar_equality_filter_and_date_output(self):
        result = self.service.query(
            QueryRequest(
                model="daily",
                dimensions=("business_date",),
                metrics=("revenue",),
                filters={"country_code": "US"},
            )
        )

        self.assertEqual(
            {row["business_date"]: row["revenue"] for row in result.rows},
            {"2026-10-01": 10, "2026-10-02": 20},
        )

    def test_query_request_rejects_malformed_shapes_and_duplicates(self):
        invalid_payloads = (
            ({"metrics": ["revenue"]}, "model must be a string"),
            ({"model": "daily", "metrics": "revenue"}, "metrics must be a list"),
            ({"model": "daily", "unexpected": 1}, "Unsupported request field"),
            ({"model": "daily", "date_range": []}, "date_range must be an object"),
        )
        for payload, message in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaisesRegex(QueryContractError, message):
                QueryRequest.from_mapping(payload)

        duplicate = QueryRequest(model="daily", metrics=("revenue", "revenue"))
        with self.assertRaisesRegex(QueryContractError, "must not contain duplicates"):
            self.service.query(duplicate)

    def test_query_rejects_empty_selection_nested_filter_and_duplicate_dimensions(self):
        requests = (
            (QueryRequest(model="daily"), "At least one metric or dimension"),
            (QueryRequest(model="daily", dimensions=("country_code", "country_code")), "dimensions must not contain duplicates"),
            (QueryRequest(model="daily", dimensions=("country_code",), filters={"country_code": ["US", {"bad": 1}]}), "scalar values"),
        )
        for request, message in requests:
            with self.subTest(request=request), self.assertRaisesRegex(QueryContractError, message):
                self.service.query(request)

    def test_rejects_invalid_date_ranges_and_filter_values(self):
        with self.assertRaisesRegex(QueryContractError, "on or before"):
            self.service.query(
                QueryRequest(
                    model="daily",
                    metrics=("revenue",),
                    date_range=DateRange("2026-10-03", "2026-10-01"),
                )
            )
        with self.assertRaisesRegex(QueryContractError, "ISO date"):
            self.service.query(
                QueryRequest(
                    model="daily",
                    metrics=("revenue",),
                    date_range=DateRange("not-a-date", "2026-10-03"),
                )
            )
        with self.assertRaisesRegex(QueryContractError, "scalar or a list"):
            self.service.query(
                QueryRequest(
                    model="daily",
                    dimensions=("country_code",),
                    filters={"country_code": {"operator": "eq", "value": "US"}},
                )
            )
        with self.assertRaisesRegex(QueryContractError, "exactly 'from' and 'to'"):
            QueryRequest.from_mapping(
                {"model": "daily", "metrics": ["revenue"], "date_range": {"start": "2026-10-01", "end": "2026-10-02"}}
            )

    def test_rejects_date_range_for_model_without_time_dimension(self):
        definition = SilverSemanticDefinition(
            name="static",
            grain=("country_code",),
            dimensions=(DimensionDefinition("country_code", "country_code", "Country", "country"),),
            metrics=(),
            description="Static test model.",
        )
        table = definition.build(self.backend.create_table("static", [{"country_code": "US"}]))
        service = QueryService(LocalRegistry(definition, table))
        with self.assertRaisesRegex(QueryContractError, "no time dimension"):
            service.query(
                QueryRequest(
                    model="static",
                    dimensions=("country_code",),
                    date_range=DateRange("2026-10-01", "2026-10-02"),
                )
            )

    def test_rejects_date_range_when_model_has_multiple_time_dimensions(self):
        definition = SilverSemanticDefinition(
            name="two_dates",
            grain=("start_date", "end_date"),
            dimensions=(
                DimensionDefinition("start_date", "start_date", "Start", "day", time=True),
                DimensionDefinition("end_date", "end_date", "End", "day", time=True),
            ),
            metrics=(MetricDefinition("revenue", "revenue", "Revenue", "USD"),),
            description="Two time dimensions.",
        )
        table = definition.build(
            self.backend.create_table(
                "two_dates", [{"start_date": date(2026, 10, 1), "end_date": date(2026, 10, 2), "revenue": 1}]
            )
        )
        service = QueryService(LocalRegistry(definition, table))
        with self.assertRaisesRegex(QueryContractError, "multiple time dimensions"):
            service.query(
                QueryRequest(
                    model="two_dates",
                    metrics=("revenue",),
                    date_range=DateRange("2026-10-01", "2026-10-02"),
                )
            )


class RegistryBackedQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ignore_known_ibis_duckdb_deprecation()

    def setUp(self):
        self.backend = ibis.duckdb.connect()
        self.app_daily = self.backend.create_table(
            "app_daily",
            [
                {
                    "business_date": date(2026, 10, 1), "app_id": "app", "country_code": "US",
                    "revenue_currency_code": "VND", "cost_currency_code": "VND",
                    "revenue": 100_000.0, "cost": 50_000.0,
                },
                {
                    "business_date": date(2026, 10, 2), "app_id": "app", "country_code": "US",
                    "revenue_currency_code": "VND", "cost_currency_code": "VND",
                    "revenue": 1_600_000.0, "cost": 200_000.0,
                },
                {
                    "business_date": date(2026, 10, 3), "app_id": "app", "country_code": "US",
                    "revenue_currency_code": "GBP", "cost_currency_code": "VND",
                    "revenue": 25.0, "cost": 50_000.0,
                },
            ],
        )
        self.fx_daily = self.backend.create_table(
            "fx_daily",
            [{"base_currency": "VND", "quote_currency": "USD", "rate_date": date(2026, 10, 1), "rate": 0.00002}],
        )
        self.source = InMemorySilverSource(
            {"app_daily": self.app_daily, "fx_daily": self.fx_daily}
        )
        self.registry = SemanticRegistry(self.source)
        self.service = QueryService(self.registry)

    def tearDown(self):
        self.backend.disconnect()

    def test_real_registry_finance_query_preserves_fx_fallback_and_null_conversion(self):
        result = self.service.query(
            QueryRequest(
                model="finance_daily",
                dimensions=("business_date", "fx_rate_date", "fx_fallback_used"),
                metrics=("revenue_usd", "cost_usd"),
                date_range=DateRange("2026-10-02", "2026-10-03"),
            )
        )
        by_date = {row["business_date"]: row for row in result.rows}

        self.assertEqual(set(by_date), {"2026-10-02", "2026-10-03"})
        self.assertEqual(by_date["2026-10-02"]["fx_rate_date"], "2026-10-01")
        self.assertTrue(by_date["2026-10-02"]["fx_fallback_used"])
        self.assertEqual(by_date["2026-10-02"]["revenue_usd"], 32.0)
        self.assertIsNone(by_date["2026-10-03"]["revenue_usd"])
        self.assertEqual(result.metrics[0]["unit"], "USD")

    def test_real_registry_period_roas_uses_totals_and_native_mixed_currency_is_null(self):
        total = self.service.query(
            QueryRequest(
                model="finance_daily",
                metrics=("roas_usd",),
                date_range=DateRange("2026-10-01", "2026-10-02"),
            )
        )
        daily = self.service.query(
            QueryRequest(
                model="finance_daily",
                dimensions=("business_date",),
                metrics=("roas_usd",),
                date_range=DateRange("2026-10-01", "2026-10-02"),
            )
        )
        native = self.service.query(
            QueryRequest(model="finance_daily", metrics=("admob_revenue_native",))
        )

        self.assertAlmostEqual(total.rows[0]["roas_usd"], 6.8)
        self.assertEqual(
            {row["business_date"]: row["roas_usd"] for row in daily.rows},
            {"2026-10-01": 2.0, "2026-10-02": 8.0},
        )
        self.assertIsNone(native.rows[0]["admob_revenue_native"])

    def test_registry_query_returns_supported_result_metadata_and_rejects_unknown_model(self):
        result = self.service.query(
            QueryRequest(
                model="finance_daily",
                dimensions=("business_date",),
                metrics=("revenue_usd",),
            )
        )
        self.assertEqual(result.model, "finance_daily")
        self.assertEqual(result.dimensions[0]["name"], "business_date")
        self.assertEqual(result.metrics[0]["unit"], "USD")

        with self.assertRaisesRegex(QueryContractError, "Unsupported semantic model"):
            self.service.query(QueryRequest(model="not_registered", metrics=("revenue_usd",)))


if __name__ == "__main__":
    unittest.main()
