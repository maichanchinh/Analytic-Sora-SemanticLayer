# Silver Data Catalog

## Phạm vi và cách đọc

Catalog này mô tả schema Parquet đọc trực tiếp từ Silver bucket RustFS của Sora bằng DuckDB `httpfs` và đối chiếu với model/grain trong `Sora/silver_project`. Không ghi dữ liệu hoặc credentials vào tài liệu.

Inventory snapshot ngày **2026-10-03**: 54 object gồm 38 production Parquet thuộc 11 dataset, 4 Silver build manifest và 12 object thử nghiệm dưới `staging/` (11 Parquet cùng một manifest). Staging bị loại khỏi dataset production. Các dataset có partition ngày trong snapshot có dữ liệu từ `2026-09-30` đến `2026-10-03`; đây là trạng thái tại thời điểm khảo sát, không phải cam kết retention.

Schema được so sánh trên tất cả file Parquet production của mỗi dataset có partition ngày. Mỗi dataset có một schema variant trong các file đang tồn tại. Các type bên dưới là type DuckDB suy ra từ Parquet. Ngày trong `date=YYYY-MM-DD` là Hive path partition; nó không nhất thiết là field vật lý trong file.

## Dataset inventory

| Dataset | S3 path | Partition | Grain |
|---|---|---|---|
| `dim_app` | `dimensions/dim_app/data.parquet` | Snapshot, không partition ngày | `app_id` |
| `dim_country` | `dimensions/dim_country/data.parquet` | Snapshot, không partition ngày | `country_code` |
| `dim_date` | `dimensions/dim_date/date={date}/data.parquet` | `date` | `date` |
| `ga4_daily_overview` | `ga4/ga4_daily_overview/date={date}/data.parquet` | `date` | `business_date, app_id, country_code` |
| `ga4_retention_cohort` | `ga4/ga4_retention_cohort/date={date}/data.parquet` | `date` | `cohort_date, app_id, country_code, cohort_day` |
| `admob_mediation_daily` | `admob/admob_mediation_daily/date={date}/data.parquet` | `date` | `business_date, app_id, country_code` |
| `google_ads_campaign_geo_daily` | `google_ads/google_ads_campaign_geo_daily/date={date}/data.parquet` | `date` | `business_date, app_id, campaign_id, country_code` |
| `fx_daily` | `finance/fx_daily/date={date}/data.parquet` | `date` | `business_date, base_currency, quote_currency` |
| `app_daily` | `report/app_daily/date={date}/data.parquet` | `date` | `business_date, app_id, country_code` |
| `campaign_geo` | `report/campaign_geo/date={date}/data.parquet` | `date` | Same grain as `google_ads_campaign_geo_daily` |
| `retention` | `report/retention/date={date}/data.parquet` | `date` | Same grain as `ga4_retention_cohort` |

Date-partitioned tables also carry their business/cohort/date field in the Parquet schema, except the path partition is a separate storage key. Consumers should inspect both path and physical schema when scanning partitions.

## Schemas

### Dimensions

**`dim_app`** — `app_id VARCHAR`, `package_name VARCHAR`, `display_name VARCHAR`, `platform VARCHAR`, `status VARCHAR`.

**`dim_country`** — `country_code VARCHAR`, `country_name VARCHAR`.

**`dim_date`** — `date DATE`, `year BIGINT`, `quarter BIGINT`, `month BIGINT`, `week BIGINT`, `day_of_month BIGINT`, `day_of_week BIGINT`, `month_start DATE`, `week_start DATE`, `is_weekend BOOLEAN`.

### GA4

**`ga4_daily_overview`** — `account_id VARCHAR`, `property_id VARCHAR`, `property_name VARCHAR`, `package_name VARCHAR`, `app_id VARCHAR`, `mapping_status VARCHAR`, `business_date DATE`, `report_timezone VARCHAR`, `country_name VARCHAR`, `country_code VARCHAR`, `active_users BIGINT`, `new_users BIGINT`, `sessions BIGINT`, `engaged_sessions BIGINT`, `screen_page_views BIGINT`, `total_revenue DOUBLE`, `snapshot_at TIMESTAMP WITH TIME ZONE`, `extracted_at TIMESTAMP WITH TIME ZONE`.

**`ga4_retention_cohort`** — `cohort_date DATE`, `app_id VARCHAR`, `country_code VARCHAR`, `cohort_day INTEGER`, `cohort_users BIGINT`, `retained_users BIGINT`, `retention_rate DOUBLE`, `loaded_at TIMESTAMP WITH TIME ZONE`.

### AdMob

**`admob_mediation_daily`** — `business_date DATE`, `app_id VARCHAR`, `country_code VARCHAR`, `ad_requests BIGINT`, `clicks BIGINT`, `estimated_earnings DOUBLE`, `currency_code VARCHAR`, `impressions BIGINT`, `matched_requests BIGINT`, `impression_ctr DOUBLE`, `match_rate DOUBLE`, `observed_ecpm DOUBLE`, `snapshot_at TIMESTAMP WITH TIME ZONE`, `extracted_at TIMESTAMP WITH TIME ZONE`.

This Silver model is already aggregated to date/app/country. It does not expose `ad_source` or `ad_unit` in its current schema.

### Google Ads

**`google_ads_campaign_geo_daily`** — `business_date DATE`, `app_id VARCHAR`, `campaign_id VARCHAR`, `campaign_name VARCHAR`, `country_code VARCHAR`, `cost_micros BIGINT`, `currency_code VARCHAR`, `snapshot_at TIMESTAMP WITH TIME ZONE`, `extracted_at TIMESTAMP WITH TIME ZONE`.

`cost_micros` is stored in millionths of the currency unit. The dataset does not currently expose installs or conversion counts.

### FX

**`fx_daily`** — `business_date DATE`, `base_currency VARCHAR`, `quote_currency VARCHAR`, `rate DOUBLE`, `rate_date VARCHAR`, `rate_provider VARCHAR`.

### Sora report outputs

**`app_daily`** — `business_date DATE`, `app_id VARCHAR`, `country_code VARCHAR`, `revenue DOUBLE`, `revenue_currency_code VARCHAR`, `cost DOUBLE`, `cost_currency_code VARCHAR`, `roas DOUBLE`.

**`campaign_geo`** has the same physical schema as `google_ads_campaign_geo_daily`: `business_date DATE`, `app_id VARCHAR`, `campaign_id VARCHAR`, `campaign_name VARCHAR`, `country_code VARCHAR`, `cost_micros BIGINT`, `currency_code VARCHAR`, `snapshot_at TIMESTAMP WITH TIME ZONE`, `extracted_at TIMESTAMP WITH TIME ZONE`.

**`retention`** has the same physical schema as `ga4_retention_cohort`: `cohort_date DATE`, `app_id VARCHAR`, `country_code VARCHAR`, `cohort_day INTEGER`, `cohort_users BIGINT`, `retained_users BIGINT`, `retention_rate DOUBLE`, `loaded_at TIMESTAMP WITH TIME ZONE`.

## Lineage and metric semantics

```text
GA4 daily_country / geo_device
  → ga4_daily_overview

GA4 retention_cohort
  → ga4_retention_cohort
  → report/retention (copy)

AdMob mediation
  → admob_mediation_daily
  → report/app_daily.revenue

Google Ads campaign geo
  → google_ads_campaign_geo_daily
  → report/campaign_geo (copy)
  → report/app_daily.cost

FX rates
  → fx_daily (not used by current report/app_daily calculation)
```

In Sora's existing `report/app_daily` model, `revenue` is summed AdMob `estimated_earnings`; `cost` is Google Ads `cost_micros / 1,000,000`. `roas` is `revenue / cost` only when cost is positive and the revenue and cost currency codes are equal; otherwise it is null. This report revenue is not the same field as GA4 `total_revenue`.

GA4 `total_revenue` has no currency column in this Silver schema. Do not combine it with amounts carrying explicit currency codes until its property currency is made available and an aggregation policy is defined. Do not treat `total_revenue` as `purchase_revenue` without a confirmed business definition.

## Semantic-layer availability

| Semantic candidate | Current Silver support | Notes |
|---|---|---|
| GA4 active users, new users, sessions | Available | From `ga4_daily_overview`; `active_users`/`new_users` are null for a grouped app/date/country row when more than one GA4 property contributes. |
| GA4 total revenue | Available, currency implicit | Expose as source-specific until property currency is captured. |
| Ad revenue, impressions, clicks, requests | Available | From `admob_mediation_daily`; amounts use `currency_code`. |
| CTR, match rate, observed eCPM | Available | Precomputed in the AdMob Silver model as `impression_ctr`, `match_rate`, `observed_ecpm`. |
| Campaign spend | Available | `cost_micros` plus `currency_code`; divide by 1,000,000 for source-currency units. |
| Retention by cohort day | Available | Use `cohort_day` and `retention_rate`; D1/D7/D30 require selecting the matching day. |
| App, country, campaign | Available | Join via `app_id`, `country_code`, and campaign fields. |
| `app_version`, `ad_source`, `ad_unit` | Not in current Silver schemas | Do not expose as supported dimensions until a source dataset provides them. |
| Installs, CPI, purchase revenue | Not established by current schemas | No install/conversion field; GA4 `total_revenue` is not an approved purchase-only measure. |
| Unified revenue, profit, cross-currency ROAS | Requires policy | Preserve source-specific amounts; current `app_daily.roas` only covers matching currencies. `fx_daily` is not applied by Sora's current report model. |

## Build metadata

Silver manifests are stored at `metadata/silver_build/date={date}/manifest.json`. The observed manifest fields are `business_date`, `trigger_sources`, `failed_sources`, `source_status`, and `built_at`; source statuses identify `admob`, `fx`, `ga4`, and `google_ads`. The 2026-10-03 manifest reported all four source statuses as fresh. Treat this as a snapshot, not a permanent freshness guarantee.
