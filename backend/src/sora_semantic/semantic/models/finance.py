from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ibis

from sora_semantic.semantic.models.base import (
    SilverSemanticDefinition,
    _dim,
    _metric,
)


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
                    aggregation="scaled_sum",
                    currency_column="revenue_currency_code",
                    multiplier=1 / 1_000_000,
                    description="AdMob estimated_earnings copied into app_daily and converted from currency micros to currency units.",
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
                    aggregation="sum",
                    null_behavior="Rows without a supported FX conversion are omitted from the total.",
                ),
                _metric(
                    "revenue_vnd",
                    "VND",
                    aggregation="sum",
                    null_behavior="Rows without a supported FX conversion are omitted from the total.",
                ),
                _metric(
                    "cost_usd",
                    "USD",
                    aggregation="sum",
                    null_behavior="Rows without a supported FX conversion are omitted from the total.",
                ),
                _metric(
                    "cost_vnd",
                    "VND",
                    aggregation="sum",
                    null_behavior="Rows without a supported FX conversion are omitted from the total.",
                ),
                _metric(
                    "profit_usd",
                    "USD",
                    source_column="revenue_usd",
                    aggregation="difference",
                    denominator_column="cost_usd",
                    description="Revenue USD minus cost USD after omitting rows without a supported FX conversion.",
                ),
                _metric(
                    "profit_vnd",
                    "VND",
                    source_column="revenue_vnd",
                    aggregation="difference",
                    denominator_column="cost_vnd",
                    description="Revenue VND minus cost VND after omitting rows without a supported FX conversion.",
                ),
                _metric(
                    "roas_usd",
                    "ratio",
                    aggregation="ratio",
                    numerator_column="revenue_usd",
                    denominator_column="cost_usd",
                    null_behavior="Null when spend is not positive or no converted revenue is available.",
                ),
                _metric(
                    "roas_vnd",
                    "ratio",
                    aggregation="ratio",
                    numerator_column="revenue_vnd",
                    denominator_column="cost_vnd",
                    null_behavior="Null when spend is not positive or no converted revenue is available.",
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

        revenue = joined.revenue / 1_000_000
        revenue_usd = ibis.ifelse(
            revenue_currency == "USD",
            revenue,
            ibis.ifelse(
                (revenue_currency == "VND") & has_fx,
                revenue * joined.fx_rate,
                None,
            ),
        )
        revenue_vnd = ibis.ifelse(
            revenue_currency == "VND",
            revenue,
            ibis.ifelse(
                (revenue_currency == "USD") & has_fx,
                revenue / joined.fx_rate,
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


FINANCE_DAILY_DEFINITION = FinanceDailyDefinition()
