# Sora Semantic Layer — Handoff

## Mục tiêu

Tiếp tục xây một analytics layer độc lập, chỉ đọc Silver Parquet từ RustFS của Sora, cung cấp semantic metrics/dimensions dùng chung cho API, MCP và dashboard. Không sửa pipeline hoặc ghi dữ liệu về dự án Sora.

Tài liệu nền:

- [Architecture](ARCHITECTURE.md): kiến trúc mục tiêu, API/MCP, dashboard JSON và phạm vi MVP.
- [Silver Data Catalog](SILVER_DATA_CATALOG.md): inventory, schema, grain, lineage và giới hạn dữ liệu theo snapshot 2026-10-03.
- [FastAPI and MCP](API.md): cách chạy API/MCP, transports, request/response và error status hiện triển khai.
- [UA Marketing Dashboard Contract](UA_MARKETING_DASHBOARD.md): metric coverage, filter applicability, null/currency behavior, JSON contract mẫu và acceptance criteria SOF-69.

## Trạng thái hiện tại

Backend Python nằm trong `backend/`; package ở `backend/src/sora_semantic/`. Backend đã có kết nối Silver read-only qua DuckDB/Ibis, semantic registry cho các dataset production trong Catalog, `finance_daily`, và shared Query Service có validation cho model/metric/dimension/filter/date range. Semantic definitions hiện có ở `backend/src/sora_semantic/semantic/models/datasets.py` và `finance.py`; danh sách theo model lấy từ registry, còn Architecture mô tả target semantic contract rộng hơn.

Đã có FastAPI routes cho apps, metric/dimension metadata, shared query service và dashboard JSON config; cấu hình ban đầu ở `backend/dashboard/config/ua_app_overview.json`. FastMCP cung cấp `list_apps`, `list_metrics` và `query_metrics` qua `stdio` và `Streamable HTTP`, dùng chung `SemanticRegistry`/`QueryService`; hướng dẫn chạy và contract ở [FastAPI and MCP](API.md). Tests ở `backend/tests/` bao phủ API, query và hai MCP transports. Live RustFS API smoke test trước đó đã đọc 20 apps và 4 finance rows cho 2026-09-30 đến 2026-10-03; đó là snapshot lúc chạy, không phải freshness/retention guarantee. Dashboard UI chưa có. Authentication/Authorization được loại khỏi phạm vi hiện tại. Git đã có lịch sử commit; kiểm tra trạng thái từng lần trước khi thay đổi.

## Hợp đồng dữ liệu cần giữ

- Silver Parquet trên RustFS là source of truth; DuckDB chỉ đọc và thực thi query.
- Dùng catalog để xác nhận schema, grain và lineage trước khi định nghĩa hoặc expose metric/dimension. Catalog phản ánh snapshot, không đảm bảo retention hay freshness liên tục.
- GA4 `active_users`, `new_users`, `sessions` lấy từ `ga4_daily_overview`. `active_users`/`new_users` có thể null ở dòng app/date/country khi có nhiều GA4 property đóng góp.
- GA4 `total_revenue` thiếu currency trong Silver hiện tại; không gộp với doanh thu có currency hoặc mặc định đó là purchase revenue.
- AdMob `estimated_earnings` là ad revenue và giữ `currency_code`. `admob_mediation_daily` hiện không có `ad_source`/`ad_unit`.
- Google Ads `cost_micros` phải chia 1,000,000 để ra đơn vị tiền tệ nguồn; giữ `currency_code`.
- `report/app_daily.revenue` là tổng AdMob earnings; `cost` là Google Ads cost. `roas` hiện chỉ có khi cost dương và hai currency code giống nhau.
- `fx_daily` chưa được áp dụng vào `report/app_daily`; không giả định đã có quy đổi tiền tệ.
- Silver hiện không có installs/conversions, `app_version`, `ad_source` hoặc `ad_unit`. Không giả lập installs, CPI, purchase revenue hay các dimension thiếu nguồn.
- Retention được lưu theo `cohort_day`; D1/D7/D30 phải lọc đúng cohort day.

## Phạm vi MVP

Vertical slice mục tiêu:

```text
ga4_daily_overview
  → DuckDB + Ibis + Boring Semantic Layer
  → shared Query Service
  → FastAPI POST /api/v1/query
  → dashboard JSON
  → React dynamic renderer
```

Đã triển khai shared Query Service, model-backed semantic registry, FastAPI apps/metadata/query/dashboard-config routes và SOF-70 MCP tools. SOF-69 API dùng contract UA Marketing Dashboard trong [UA Marketing Dashboard Contract](UA_MARKETING_DASHBOARD.md); Dashboard UI chưa được triển khai. Authentication/Authorization bị loại khỏi phạm vi hiện tại.

Bắt đầu với metrics GA4 có nguồn rõ ràng, như `active_users` (đặt tên API theo semantic contract được chốt), `new_users` và `sessions`; giữ riêng `ga4_total_revenue` với currency implicit cho đến khi có policy. Chỉ thêm metrics khi source mapping, grain, null behavior và currency semantics đã được xác nhận.

Dashboard MVP hỗ trợ widget `metric`, `area_chart`, `bar_chart`, `table`. Dashboard được cấu hình bằng JSON; thêm dashboard mới không cần tạo React page riêng. API và MCP dùng chung Query Service. MCP MVP: `list_apps`, `list_metrics`, `query_metrics`.

Ngoài phạm vi MVP: ETL, Gold Layer, dashboard drag/drop editor, custom SQL editor, complex SQL lineage, Spark, Kafka, Cube và Malloy. SQLGlot chỉ thêm nếu phát sinh nhu cầu cụ thể về raw SQL guard hoặc lineage.

## Thứ tự triển khai đề xuất

1. Tạo dashboard JSON App Overview tối giản và dynamic renderer cho bốn widget MVP.
2. Xác nhận end-to-end từ Silver tới dashboard bằng môi trường đã cấu hình; ghi rõ phần nào được xác nhận.
3. Sau khi contract ổn định, mở rộng tools và dashboard theo nhu cầu.

## Tiêu chí hoàn tất MVP

- Query chỉ đọc Silver và trả kết quả qua shared Query Service.
- Metric/dimension/filter không có trong registry bị từ chối rõ ràng.
- API và MCP chỉ expose các semantic model/fields đã đăng ký; không cung cấp raw SQL.
- Kết quả giữ currency và semantics nguồn; không cộng các amount khác currency.
- Dashboard JSON render được Metric, Area Chart, Bar Chart và Table; dashboard mới không cần React page mới.
- Có bằng chứng validation end-to-end; ghi riêng kiểm tra chưa chạy hoặc còn phụ thuộc RustFS/secrets.

## Ghi chú bắt đầu cho nhóm nhận bàn giao

Trước khi mở rộng metrics/dimensions, đọc Architecture và Silver Data Catalog rồi đối chiếu definitions theo model trong semantic registry. Không xem target list trong Architecture là danh sách đã bật đồng loạt: chỉ expose field có source mapping và semantics đã xác nhận. GA4 `active_users`/`new_users` có thể null khi nhiều property đóng góp; revenue GA4 giữ vai trò reference vì thiếu currency. Không mở rộng revenue/profit/ROAS đa nguồn nếu chưa có policy currency và business definitions.
