from __future__ import annotations

from sora_semantic.semantic.models.base import SilverSemanticDefinition, _dim, _metric


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
            _metric(
                "estimated_earnings",
                "currency",
                aggregation="scaled_sum",
                currency_column="currency_code",
                multiplier=1 / 1_000_000,
                description="AdMob estimated earnings, converted from currency micros to currency units.",
            ),
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
                multiplier=1 / 1_000,
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
            _metric("admob_revenue_native", "currency", source_column="revenue", aggregation="scaled_sum", currency_column="revenue_currency_code", multiplier=1 / 1_000_000, description="AdMob estimated_earnings copied into report/app_daily and converted from currency micros to currency units."),
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
