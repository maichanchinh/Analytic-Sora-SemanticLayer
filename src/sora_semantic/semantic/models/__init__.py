"""Catalog-backed Boring Semantic Layer definitions for Silver datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ibis
from boring_semantic_layer import SemanticTable, to_semantic_table

from sora_semantic.semantic.dimensions import DimensionDefinition
from sora_semantic.semantic.metrics import MetricDefinition


@dataclass(frozen=True)
class SilverSemanticDefinition:
    """Semantic contract for one production Silver dataset."""

    name: str
    grain: tuple[str, ...]
    dimensions: tuple[DimensionDefinition, ...]
    metrics: tuple[MetricDefinition, ...]
    description: str

    def build(self, table: Any) -> SemanticTable:
        semantic_table = to_semantic_table(
            table,
            name=self.name,
            description=self.description,
        )
        if self.dimensions:
            semantic_table = semantic_table.with_dimensions(
                **{
                    item.name: item.as_bsl_dimension(self.name)
                    for item in self.dimensions
                }
            )
        if self.metrics:
            semantic_table = semantic_table.with_measures(
                **{
                    item.name: item.as_bsl_measure(self.name, self.grain)
                    for item in self.metrics
                }
            )
        return semantic_table

    def metadata(self) -> dict[str, Any]:
        """Return a JSON-ready description of the supported fields."""
        return {
            "name": self.name,
            "source": self.name,
            "grain": list(self.grain),
            "description": self.description,
            "dimensions": [
                {
                    "name": item.name,
                    "source_column": item.source_column,
                    "grain": item.grain,
                    "description": item.description,
                }
                for item in self.dimensions
            ],
            "metrics": [
                {
                    "name": item.name,
                    "source_column": item.source_column,
                    "grain": list(self.grain),
                    "unit": item.unit,
                    "aggregation": item.aggregation,
                    "currency_column": item.currency_column,
                    "paired_currency_column": item.paired_currency_column,
                    "guard_column": item.guard_column,
                    "numerator_column": item.numerator_column,
                    "denominator_column": item.denominator_column,
                    "null_behavior": item.null_behavior,
                    "description": item.description,
                }
                for item in self.metrics
            ],
        }


@dataclass(frozen=True)
class FinanceDailyDefinition:
    """Currency-normalized finance view over app_daily and fx_daily."""

    name: str = "finance_daily"
    source_tables: tuple[str, ...] = ("app_daily", "fx_daily")
    grain: tuple[str, ...] = ("business_date", "app_id", "country_code")

    @property
    def definition(self) -> SilverSemanticDefinition:
        return SilverSemanticDefinition(
            name=self.name,
            grain=self.grain,
            dimensions=(
                _dim("business_date", time=True),
                _dim("app_id", entity=True),
                _dim("country_code", entity=True),
                _dim("revenue_currency_code"),
                _dim("cost_currency_code"),
                _dim("fx_rate_date"),
                _dim("fx_fallback_used"),
            ),
            metrics=(
                _metric(
                    "admob_revenue_native",
                    "currency",
                    source_column="revenue",
                    aggregation="sum_by_currency",
                    currency_column="revenue_currency_code",
                    description="AdMob estimated_earnings copied into app_daily, in source currency.",
                ),
                _metric(
                    "google_ads_cost_native",
                    "currency",
                    source_column="cost",
                    aggregation="sum_by_currency",
                    currency_column="cost_currency_code",
                    description="Google Ads spend copied into app_daily, in source currency.",
                ),
                _metric(
                    "revenue_usd",
                    "USD",
                    aggregation="sum_preserve_null",
                    null_behavior="Null when any contributing revenue row lacks a supported FX conversion.",
                ),
                _metric(
                    "revenue_vnd",
                    "VND",
                    aggregation="sum_preserve_null",
                    null_behavior="Null when any contributing revenue row lacks a supported FX conversion.",
                ),
                _metric(
                    "cost_usd",
                    "USD",
                    aggregation="sum_preserve_null",
                    null_behavior="Null when any contributing cost row lacks a supported FX conversion.",
                ),
                _metric(
                    "cost_vnd",
                    "VND",
                    aggregation="sum_preserve_null",
                    null_behavior="Null when any contributing cost row lacks a supported FX conversion.",
                ),
                _metric(
                    "profit_usd",
                    "USD",
                    source_column="revenue_usd",
                    aggregation="difference_preserve_null",
                    denominator_column="cost_usd",
                    description="Revenue USD minus cost USD; null if either side is incomplete.",
                ),
                _metric(
                    "profit_vnd",
                    "VND",
                    source_column="revenue_vnd",
                    aggregation="difference_preserve_null",
                    denominator_column="cost_vnd",
                    description="Revenue VND minus cost VND; null if either side is incomplete.",
                ),
                _metric(
                    "roas_usd",
                    "ratio",
                    aggregation="ratio_preserve_null",
                    numerator_column="revenue_usd",
                    denominator_column="cost_usd",
                    null_behavior="Null when spend is not positive or either converted amount is incomplete.",
                ),
                _metric(
                    "roas_vnd",
                    "ratio",
                    aggregation="ratio_preserve_null",
                    numerator_column="revenue_vnd",
                    denominator_column="cost_vnd",
                    null_behavior="Null when spend is not positive or either converted amount is incomplete.",
                ),
            ),
            description="Daily AdMob revenue and Google Ads cost normalized to USD and VND using VND-to-USD FX.",
        )

    def build(self, app_daily: Any, fx_daily: Any) -> SemanticTable:
        fx_rates = (
            fx_daily.filter(
                (fx_daily.base_currency.upper() == "VND")
                & (fx_daily.quote_currency.upper() == "USD")
            )
            .select(
                fx_rate_date=fx_daily.rate_date.cast("date"),
                fx_rate=fx_daily.rate,
            )
        )
        joined = app_daily.asof_join(
            fx_rates,
            on=app_daily.business_date >= fx_rates.fx_rate_date,
        )

        revenue_currency = joined.revenue_currency_code.upper()
        cost_currency = joined.cost_currency_code.upper()
        has_fx = joined.fx_rate.notnull() & (joined.fx_rate > 0)

        revenue_usd = ibis.ifelse(
            revenue_currency == "USD",
            joined.revenue,
            ibis.ifelse(
                (revenue_currency == "VND") & has_fx,
                joined.revenue * joined.fx_rate,
                None,
            ),
        )
        revenue_vnd = ibis.ifelse(
            revenue_currency == "VND",
            joined.revenue,
            ibis.ifelse(
                (revenue_currency == "USD") & has_fx,
                joined.revenue / joined.fx_rate,
                None,
            ),
        )
        cost_usd = ibis.ifelse(
            cost_currency == "USD",
            joined.cost,
            ibis.ifelse(
                (cost_currency == "VND") & has_fx,
                joined.cost * joined.fx_rate,
                None,
            ),
        )
        cost_vnd = ibis.ifelse(
            cost_currency == "VND",
            joined.cost,
            ibis.ifelse(
                (cost_currency == "USD") & has_fx,
                joined.cost / joined.fx_rate,
                None,
            ),
        )

        supported_currency = (
            revenue_currency.isin(("USD", "VND"))
            | cost_currency.isin(("USD", "VND"))
        )
        return self.definition.build(
            joined.mutate(
                revenue_usd=revenue_usd,
                revenue_vnd=revenue_vnd,
                cost_usd=cost_usd,
                cost_vnd=cost_vnd,
                fx_rate_date=ibis.ifelse(
                    supported_currency & has_fx,
                    joined.fx_rate_date,
                    None,
                ),
                fx_fallback_used=ibis.ifelse(
                    supported_currency & has_fx,
                    joined.fx_rate_date < joined.business_date,
                    None,
                ),
            )
        )

    def metadata(self) -> dict[str, Any]:
        metadata = self.definition.metadata()
        metadata["source_tables"] = list(self.source_tables)
        metadata["dimensions"] = [
            {
                "name": item.name,
                "source_column": item.source_column,
                "grain": item.grain,
                "description": item.description,
            }
            for item in self.definition.dimensions
        ]
        metadata["metrics"] = [
            {
                "name": item.name,
                "source_column": item.source_column,
                "grain": list(self.grain),
                "unit": item.unit,
                "aggregation": item.aggregation,
                "currency_column": item.currency_column,
                "paired_currency_column": item.paired_currency_column,
                "guard_column": item.guard_column,
                "numerator_column": item.numerator_column,
                "denominator_column": item.denominator_column,
                "null_behavior": item.null_behavior,
                "description": item.description,
            }
            for item in self.definition.metrics
        ]
        metadata["fx_policy"] = {
            "pair": "VND/USD",
            "rate_unit": "USD per VND",
            "lookup": "latest rate_date on or before business_date",
            "fallback_fields": ["fx_rate_date", "fx_fallback_used"],
            "unsupported_currency_behavior": "retain native amount; normalized amount is null",
        }
        return metadata


def _dim(
    name: str,
    grain: str | None = None,
    *,
    entity: bool | None = None,
    time: bool = False,
):
    if entity is None:
        entity = name in {"app_id", "country_code"}
    return DimensionDefinition(
        name=name,
        source_column=name,
        description=f"Silver {name} dimension.",
        grain=grain or name,
        entity=entity,
        time=time,
    )


def _metric(
    name: str,
    unit: str,
    *,
    source_column: str | None = None,
    aggregation: str = "sum",
    currency_column: str | None = None,
    paired_currency_column: str | None = None,
    guard_column: str | None = None,
    numerator_column: str | None = None,
    denominator_column: str | None = None,
    multiplier: float = 1.0,
    null_behavior: str | None = None,
    description: str | None = None,
):
    return MetricDefinition(
        name=name,
        source_column=source_column or name,
        description=description or f"Silver {source_column or name} metric.",
        unit=unit,
        aggregation=aggregation,
        currency_column=currency_column,
        paired_currency_column=paired_currency_column,
        guard_column=guard_column,
        numerator_column=numerator_column,
        denominator_column=denominator_column,
        multiplier=multiplier,
        null_behavior=null_behavior,
    )


SILVER_SEMANTIC_DEFINITIONS: tuple[SilverSemanticDefinition, ...] = (
    SilverSemanticDefinition(
        name="dim_app",
        grain=("app_id",),
        dimensions=(
            _dim("app_id", entity=True),
            _dim("package_name"),
            _dim("display_name"),
            _dim("platform"),
            _dim("status"),
        ),
        metrics=(),
        description="Production app dimension; one row per app_id.",
    ),
    SilverSemanticDefinition(
        name="dim_country",
        grain=("country_code",),
        dimensions=(_dim("country_code", entity=True), _dim("country_name")),
        metrics=(),
        description="Production country dimension; one row per country_code.",
    ),
    SilverSemanticDefinition(
        name="dim_date",
        grain=("date",),
        dimensions=tuple(
            _dim(column, time=column == "date")
            for column in (
                "date",
                "year",
                "quarter",
                "month",
                "week",
                "day_of_month",
                "day_of_week",
                "month_start",
                "week_start",
                "is_weekend",
            )
        ),
        metrics=(),
        description="Production calendar dimension; one row per date.",
    ),
    SilverSemanticDefinition(
        name="ga4_daily_overview",
        grain=("business_date", "app_id", "country_code"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in (
                "business_date",
                "app_id",
                "country_code",
                "account_id",
                "property_id",
                "property_name",
                "mapping_status",
            )
        ),
        metrics=(
            _metric("active_users", "users", aggregation="sum_preserve_null", null_behavior="Preserve null when multiple GA4 properties contribute."),
            _metric("new_users", "users", aggregation="sum_preserve_null", null_behavior="Preserve null when multiple GA4 properties contribute."),
            _metric("sessions", "sessions"),
            _metric("engaged_sessions", "sessions"),
            _metric("screen_page_views", "views"),
            _metric(
                "ga4_total_revenue_reference",
                "currency_implicit",
                source_column="total_revenue",
                aggregation="sum_by_group_column",
                guard_column="property_id",
                null_behavior="Reference only; currency is absent. Keep isolated from financial revenue and group by property_id.",
            ),
        ),
        description="GA4 daily overview at business_date/app_id/country_code grain.",
    ),
    SilverSemanticDefinition(
        name="ga4_retention_cohort",
        grain=("cohort_date", "app_id", "country_code", "cohort_day"),
        dimensions=tuple(
            _dim(column, time=column == "cohort_date")
            for column in ("cohort_date", "app_id", "country_code", "cohort_day")
        ),
        metrics=(
            _metric("cohort_users", "users"),
            _metric("retained_users", "users"),
            _metric(
                "retention_rate",
                "ratio",
                aggregation="ratio",
                numerator_column="retained_users",
                denominator_column="cohort_users",
                null_behavior="Null when cohort_users is zero or null.",
            ),
        ),
        description="GA4 retention cohort at cohort_date/app_id/country_code/cohort_day grain.",
    ),
    SilverSemanticDefinition(
        name="admob_mediation_daily",
        grain=("business_date", "app_id", "country_code"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in ("business_date", "app_id", "country_code", "currency_code")
        ),
        metrics=(
            _metric("ad_requests", "requests"),
            _metric("clicks", "clicks"),
            _metric("estimated_earnings", "currency", aggregation="sum_by_currency", currency_column="currency_code"),
            _metric("impressions", "impressions"),
            _metric("matched_requests", "requests"),
            _metric(
                "impression_ctr",
                "ratio",
                aggregation="ratio",
                numerator_column="clicks",
                denominator_column="impressions",
                null_behavior="Null when impressions is zero or currencies are mixed.",
            ),
            _metric(
                "match_rate",
                "ratio",
                aggregation="ratio",
                numerator_column="matched_requests",
                denominator_column="ad_requests",
                null_behavior="Null when ad_requests is zero.",
            ),
            _metric(
                "observed_ecpm",
                "currency_per_thousand_impressions",
                aggregation="ratio_by_currency",
                currency_column="currency_code",
                numerator_column="estimated_earnings",
                denominator_column="impressions",
                multiplier=1000.0,
                null_behavior="Null when impressions is zero or currencies are mixed.",
            ),
        ),
        description="AdMob mediation daily at business_date/app_id/country_code grain; no ad_source or ad_unit fields exist.",
    ),
    SilverSemanticDefinition(
        name="google_ads_campaign_geo_daily",
        grain=("business_date", "app_id", "campaign_id", "country_code"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in (
                "business_date",
                "app_id",
                "campaign_id",
                "campaign_name",
                "country_code",
                "currency_code",
            )
        ),
        metrics=(
            _metric("cost_micros", "currency_micros", aggregation="sum_by_currency", currency_column="currency_code"),
            _metric("campaign_spend", "currency", source_column="cost_micros", aggregation="scaled_sum", currency_column="currency_code", multiplier=1 / 1_000_000),
        ),
        description="Google Ads campaign geo daily at business_date/app_id/campaign_id/country_code grain.",
    ),
    SilverSemanticDefinition(
        name="fx_daily",
        grain=("business_date", "base_currency", "quote_currency"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in ("business_date", "base_currency", "quote_currency", "rate_date", "rate_provider")
        ),
        metrics=(
            _metric(
                "fx_rate",
                "quote_currency_per_base_currency",
                source_column="rate",
                aggregation="non_additive",
                description="FX rate; meaningful at business_date/base_currency/quote_currency grain only.",
            ),
        ),
        description="FX rates at business_date/base_currency/quote_currency grain; not applied by current Sora report outputs.",
    ),
    SilverSemanticDefinition(
        name="app_daily",
        grain=("business_date", "app_id", "country_code"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in ("business_date", "app_id", "country_code", "revenue_currency_code", "cost_currency_code")
        ),
        metrics=(
            _metric("admob_revenue_native", "currency", source_column="revenue", aggregation="sum_by_currency", currency_column="revenue_currency_code", description="AdMob estimated_earnings copied into report/app_daily; native currency."),
            _metric("google_ads_cost_native", "currency", source_column="cost", aggregation="sum_by_currency", currency_column="cost_currency_code", description="Google Ads cost_micros converted to source-currency units in report/app_daily."),
            _metric(
                "reported_roas_native",
                "ratio",
                source_column="roas",
                aggregation="non_additive",
                currency_column="revenue_currency_code",
                paired_currency_column="cost_currency_code",
                null_behavior="Existing Silver report value; null unless cost is positive and both currency codes match. Do not sum or average.",
                description="Existing Sora app_daily ROAS at native currency; reference only, separate from normalized finance ROAS.",
            ),
        ),
        description="Sora app_daily report at business_date/app_id/country_code grain; revenue and cost retain separate currencies.",
    ),
    SilverSemanticDefinition(
        name="campaign_geo",
        grain=("business_date", "app_id", "campaign_id", "country_code"),
        dimensions=tuple(
            _dim(column, time=column == "business_date")
            for column in ("business_date", "app_id", "campaign_id", "campaign_name", "country_code", "currency_code")
        ),
        metrics=(
            _metric("cost_micros", "currency_micros", aggregation="sum_by_currency", currency_column="currency_code"),
            _metric("campaign_spend", "currency", source_column="cost_micros", aggregation="scaled_sum", currency_column="currency_code", multiplier=1 / 1_000_000),
        ),
        description="Sora campaign_geo report at business_date/app_id/campaign_id/country_code grain; kept separate from the Google Ads source dataset.",
    ),
    SilverSemanticDefinition(
        name="retention",
        grain=("cohort_date", "app_id", "country_code", "cohort_day"),
        dimensions=tuple(
            _dim(column, time=column == "cohort_date")
            for column in ("cohort_date", "app_id", "country_code", "cohort_day")
        ),
        metrics=(
            _metric("cohort_users", "users"),
            _metric("retained_users", "users"),
            _metric(
                "retention_rate",
                "ratio",
                aggregation="ratio",
                numerator_column="retained_users",
                denominator_column="cohort_users",
                null_behavior="Null when cohort_users is zero or null.",
            ),
        ),
        description="Sora retention report at cohort_date/app_id/country_code/cohort_day grain; kept separate from the GA4 cohort source.",
    ),
)

FINANCE_DAILY_DEFINITION = FinanceDailyDefinition()

__all__ = [
    "FINANCE_DAILY_DEFINITION",
    "SILVER_SEMANTIC_DEFINITIONS",
    "FinanceDailyDefinition",
    "SilverSemanticDefinition",
]
