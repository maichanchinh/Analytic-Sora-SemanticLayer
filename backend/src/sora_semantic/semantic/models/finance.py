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
    """Currency-normalized AdMob and Google Ads view over Silver source tables."""

    name: str = "finance_daily"
    source_tables: tuple[str, ...] = (
        "admob_mediation_daily",
        "google_ads_campaign_geo_daily",
        "fx_daily",
    )
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
                    source_column="admob_revenue_native",
                    aggregation="sum_by_currency",
                    currency_column="revenue_currency_code",
                    description="AdMob estimated_earnings from admob_mediation_daily in currency units.",
                ),
                _metric(
                    "google_ads_cost_native",
                    "currency",
                    source_column="google_ads_cost_native",
                    aggregation="sum_by_currency",
                    currency_column="cost_currency_code",
                    description="Google Ads cost_micros from google_ads_campaign_geo_daily in source currency units.",
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
            description="Daily AdMob Silver revenue and Google Ads Silver cost normalized to USD and VND using VND-to-USD FX.",
        )

    def build(self, admob: Any, google_ads: Any, fx_daily: Any) -> SemanticTable:
        fx_rates = (
            fx_daily.filter(
                (fx_daily.base_currency.upper() == "VND")
                & (fx_daily.quote_currency.upper() == "USD")
            )
            .select(
                fx_rate_date=fx_daily.rate_date.cast("date"),
                fx_rate=fx_daily.rate,
            )
            .group_by("fx_rate_date")
            .aggregate(fx_rate=fx_daily.rate.max())
        )

        grain = ("business_date", "app_id", "country_code")
        admob_by_currency = admob.group_by(*grain, "currency_code").aggregate(
            estimated_earnings=admob.estimated_earnings.sum(),
        )
        revenue_joined = admob_by_currency.asof_join(
            fx_rates,
            on=admob_by_currency.business_date >= fx_rates.fx_rate_date,
        )
        revenue_currency = revenue_joined.currency_code.upper()
        revenue_has_fx = revenue_joined.fx_rate.notnull() & (revenue_joined.fx_rate > 0)
        revenue = revenue_joined.estimated_earnings / 1_000_000
        revenue_usd = ibis.ifelse(
            revenue_currency == "USD",
            revenue,
            ibis.ifelse(
                (revenue_currency == "VND") & revenue_has_fx,
                revenue * revenue_joined.fx_rate,
                None,
            ),
        )
        revenue_vnd = ibis.ifelse(
            revenue_currency == "VND",
            revenue,
            ibis.ifelse(
                (revenue_currency == "USD") & revenue_has_fx,
                revenue / revenue_joined.fx_rate,
                None,
            ),
        )

        google_ads_by_currency = google_ads.group_by(*grain, "currency_code").aggregate(
            cost_micros=google_ads.cost_micros.sum(),
        )
        cost_joined = google_ads_by_currency.asof_join(
            fx_rates,
            on=google_ads_by_currency.business_date >= fx_rates.fx_rate_date,
        )
        cost_currency = cost_joined.currency_code.upper()
        cost_has_fx = cost_joined.fx_rate.notnull() & (cost_joined.fx_rate > 0)
        cost = cost_joined.cost_micros / 1_000_000
        cost_usd = ibis.ifelse(
            cost_currency == "USD",
            cost,
            ibis.ifelse(
                (cost_currency == "VND") & cost_has_fx,
                cost * cost_joined.fx_rate,
                None,
            ),
        )
        cost_vnd = ibis.ifelse(
            cost_currency == "VND",
            cost,
            ibis.ifelse(
                (cost_currency == "USD") & cost_has_fx,
                cost / cost_joined.fx_rate,
                None,
            ),
        )

        single_revenue_currency = (revenue_currency.nunique() == 1) & ~revenue_currency.isnull().any()
        single_cost_currency = (cost_currency.nunique() == 1) & ~cost_currency.isnull().any()
        revenue_by_grain = revenue_joined.group_by(*grain).aggregate(
            admob_revenue_native=ibis.ifelse(
                single_revenue_currency,
                revenue.sum(),
                None,
            ),
            revenue_currency_code=ibis.ifelse(
                single_revenue_currency,
                revenue_currency.max(),
                None,
            ),
            revenue_usd=revenue_usd.sum(),
            revenue_vnd=revenue_vnd.sum(),
        )
        cost_by_grain = cost_joined.group_by(*grain).aggregate(
            google_ads_cost_native=ibis.ifelse(
                single_cost_currency,
                cost.sum(),
                None,
            ),
            cost_currency_code=ibis.ifelse(
                single_cost_currency,
                cost_currency.max(),
                None,
            ),
            cost_usd=cost_usd.sum(),
            cost_vnd=cost_vnd.sum(),
        )
        combined = revenue_by_grain.join(
            cost_by_grain,
            predicates=list(grain),
            how="outer",
        )
        joined = combined.asof_join(
            fx_rates,
            on=combined.business_date >= fx_rates.fx_rate_date,
        )
        supported_currency = joined.revenue_currency_code.upper().isin(("USD", "VND")) | joined.cost_currency_code.upper().isin(("USD", "VND"))
        has_fx = joined.fx_rate.notnull() & (joined.fx_rate > 0)
        return self.definition.build(
            joined.mutate(
                fx_rate_date=ibis.ifelse(
                    supported_currency & has_fx,
                    joined.fx_rate_date.cast("date"),
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
