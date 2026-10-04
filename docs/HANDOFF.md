# Sora Semantic Layer — Handoff

## Mục tiêu

Tiếp tục xây một analytics layer độc lập, chỉ đọc Silver Parquet từ RustFS của Sora, cung cấp semantic metrics/dimensions dùng chung cho API, MCP và dashboard. Không sửa pipeline hoặc ghi dữ liệu về dự án Sora.

Tài liệu nền:

- [Architecture](ARCHITECTURE.md): kiến trúc mục tiêu, API/MCP, dashboard JSON và phạm vi MVP.
- [Silver Data Catalog](SILVER_DATA_CATALOG.md): inventory, schema, grain, lineage và giới hạn dữ liệu theo snapshot 2026-10-03.

## Trạng thái hiện tại

Repo hiện chỉ có tài liệu và cấu hình hướng dẫn (`AGENTS.md`); chưa có Python Core, dashboard source, dependency/toolchain hoặc test suite. Chưa có build, lint hay runtime validation nào để bàn giao. Git repo chưa có commit lịch sử; tài liệu hiện nằm trong working tree.

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

Vertical slice đầu tiên:

```text
ga4_daily_overview
  → DuckDB + Ibis + Boring Semantic Layer
  → shared Query Service
  → FastAPI POST /api/v1/query
  → dashboard JSON
  → React dynamic renderer
```

Bắt đầu với metrics GA4 có nguồn rõ ràng, như `active_users` (đặt tên API theo semantic contract được chốt), `new_users` và `sessions`; giữ riêng `ga4_total_revenue` với currency implicit cho đến khi có policy. Chỉ thêm metrics khi source mapping, grain, null behavior và currency semantics đã được xác nhận.

Dashboard MVP hỗ trợ widget `metric`, `area_chart`, `bar_chart`, `table`. Dashboard được cấu hình bằng JSON; thêm dashboard mới không cần tạo React page riêng. API và MCP phải dùng chung Query Service và Authorization. MCP MVP: `list_apps`, `list_metrics`, `query_metrics`.

Ngoài phạm vi MVP: ETL, Gold Layer, dashboard drag/drop editor, custom SQL editor, complex SQL lineage, Spark, Kafka, Cube và Malloy. SQLGlot chỉ thêm nếu phát sinh nhu cầu cụ thể về raw SQL guard hoặc lineage.

## Thứ tự triển khai đề xuất

1. Khởi tạo Python Core và toolchain đã thống nhất trong architecture; ghi lệnh phát triển chuẩn vào `AGENTS.md`.
2. Cấu hình DuckDB đọc thử Silver Parquet từ RustFS bằng cấu hình runtime/secrets ngoài Git.
3. Thêm một dataset GA4, semantic registry nhỏ và QueryRequest/QueryResult có validation cho metric, dimension, filter và date range.
4. Thêm Query Service, giới hạn app theo Authorization context và `POST /api/v1/query`.
5. Tạo một dashboard JSON App Overview tối giản và dynamic renderer cho bốn widget MVP.
6. Xác nhận end-to-end từ Silver tới dashboard bằng dữ liệu thật hoặc môi trường tích hợp đã cấu hình; ghi rõ phần nào được xác nhận.
7. Sau khi contract ổn định, mở rộng dataset/metrics, Authorization roles, MCP tools và các dashboard khác.

## Tiêu chí hoàn tất MVP

- Query chỉ đọc Silver và trả kết quả qua shared Query Service.
- Metric/dimension/filter không có trong registry bị từ chối rõ ràng.
- Authorization giới hạn app áp dụng giống nhau cho API và MCP; không thể vượt giới hạn bằng filter tự gửi.
- Kết quả giữ currency và semantics nguồn; không cộng các amount khác currency.
- Dashboard JSON render được Metric, Area Chart, Bar Chart và Table; dashboard mới không cần React page mới.
- Có bằng chứng validation end-to-end; ghi riêng kiểm tra chưa chạy hoặc còn phụ thuộc RustFS/secrets.

## Ghi chú bắt đầu cho nhóm nhận bàn giao

Trước khi code, đọc Architecture và Silver Data Catalog, sau đó xác nhận kết nối RustFS/Silver và chọn đúng GA4 measure đầu tiên. `users` trong architecture hiện là tên metric dự kiến, không tự động đồng nghĩa với GA4 `active_users`; thống nhất semantic naming và null behavior trước khi public API. Không mở rộng thành revenue/profit/ROAS đa nguồn nếu chưa có quyết định currency và business definitions.
