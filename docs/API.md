# FastAPI and MCP

## Chạy local

API dùng cùng cấu hình Silver S3-compatible với `SilverDataSource`. Tạo `backend/.env` từ `backend/.env.example`; launcher tự nạp `.env` ở root rồi `backend/.env` (project ghi đè root):

```sh
cd backend && uv sync --all-groups
uv run api.py
```

Mặc định launcher dùng log level `INFO`. Để debug khi kiểm tra app, query hoặc lỗi kết nối Silver, chạy `uv run api.py --debug`; chế độ này bật log level `DEBUG` cho ứng dụng và Uvicorn, gồm access log và thời gian/model/date range của query thành công.

Ứng dụng mở DuckDB/Ibis connection in-memory trong ASGI lifespan và đóng khi shutdown. Dataset được đăng ký dưới dạng Parquet scan từ Silver; query đọc trực tiếp dữ liệu Silver, không dùng bảng materialize hoặc DuckDB file cache. External-file, Parquet metadata và HTTP metadata caches của DuckDB đều bị tắt trên connection API đang chạy. Sau khi Sora publish Parquet mới, query tiếp theo đọc glob Silver hiện hành mà không cần thêm API refresh. Startup chạy một read check trên `dim_app`; nếu Silver không đọc được, API startup thất bại thay vì phục vụ snapshot cũ. Log chẩn đoán đã làm sạch thông tin nhạy cảm; `X-Request-ID` giúp đối chiếu log giữa request và query. `SORASEMANTIC_DUCKDB_PATH` không còn được sử dụng.

Các file DuckDB cache cũ trong `backend/.cache` không còn được đọc hoặc tự xóa. Query trực tiếp Silver có thể tốn thêm thời gian và lượt đọc S3. Dừng API process cũ trước khi khởi chạy bản mới để tránh tiếp tục dùng process đang phục vụ. Host mặc định trong lệnh trên chỉ bind loopback. API hiện chưa có authentication; chỉ expose qua mạng nội bộ được kiểm soát.

## FastMCP

MCP dùng cùng `SemanticRegistry` và `QueryService`, mở kết nối Silver read-only riêng theo lifespan của server. Có thể chạy local qua `stdio`:

```sh
cd backend && uv run mcp.py
```

Hoặc chạy server `Streamable HTTP` tại `/mcp`:

```sh
cd backend && uv run mcp.py --transport streamable-http
```

Hai lệnh dùng cùng biến môi trường Silver như API. MCP cung cấp `list_apps`, `list_metrics` và `query_metrics`; tool query nhận `model`, `metrics`, `dimensions`, `filters` và `date_range` theo shared `QueryRequest`. Kết quả dùng shape `model`, `dimensions`, `metrics`, `rows`; query contract lỗi được trả dưới dạng MCP tool error. Không có raw SQL tool.

Authorization và app scope chưa được triển khai trong dự án hiện tại. Bảo vệ server HTTP bằng network boundary phù hợp.

## Endpoints

FastAPI permits Dashboard browser requests from the local development origins
`http://localhost:3000` and `http://127.0.0.1:3000` by default. Configure
`DASHBOARD_CORS_ORIGINS` as a comma-separated allowlist when the Dashboard uses
other origins; wildcard origins are not enabled.

### `GET /api/v1/apps`

Đọc danh sách từ semantic model `dim_app`, sắp xếp theo `display_name` rồi `app_id`.

```json
{
  "apps": [
    {
      "app_id": "blur_face",
      "display_name": "Blur Face",
      "package_name": "example.blurface",
      "platform": "android",
      "status": "active"
    }
  ]
}
```

### `GET /api/v1/metrics` và `GET /api/v1/dimensions`

Trả metadata registry được nhóm theo semantic model. Chỉ model có metrics/dimensions tương ứng mới xuất hiện. Field metadata giữ các thuộc tính do semantic definition cung cấp như source, grain, unit, aggregation, currency và null behavior.

```json
{
  "models": [
    {
      "model": "finance_daily",
      "metrics": [
        {
          "name": "revenue_usd",
          "unit": "USD",
          "aggregation": "sum_preserve_null"
        }
      ]
    }
  ]
}
```

Dimensions route dùng cùng shape `models`, với key `dimensions` thay cho `metrics`.

### `POST /api/v1/query`

Request schema hiển thị trong Swagger UI tại `/docs`. Dropdown Example Value có ba request mẫu lấy từ Silver thật: `app_daily`, `campaign_geo` và `ga4_retention_cohort`. Snapshot mẫu được đọc ngày `2026-10-05`; khi dùng Swagger, chọn **Try it out** rồi **Execute** để chạy request và xem rows trả về. Chỉ chọn example sẽ điền payload, không tự gửi request.

Body gồm `model`, `metrics`, `dimensions`, `filters`, `date_range` và tùy chọn `compare_previous_period` (mặc định `false`). Khi bật, `comparisons` ghép theo dimensions và trả mỗi metric các giá trị `previous`, `delta`, `percent_change`; kỳ trước có cùng số ngày và liền trước kỳ hiện tại. Nếu thiếu metric hoặc kỳ trước bằng 0, `percent_change` là `null`.

Dashboard có thể gửi nhiều truy vấn widget trong một POST tới cùng route để giảm số request. Mỗi phần tử dùng schema query đơn và thêm `id`; response giữ kết quả hoặc lỗi riêng theo `id`, nên một widget lỗi không làm mất kết quả widget khác.

```json
{
  "queries": [
    {"id": "revenue", "model": "finance_daily", "metrics": ["revenue_usd"], "dimensions": [], "filters": {}},
    {"id": "trend", "model": "app_daily", "metrics": ["admob_revenue_native"], "dimensions": ["business_date"], "filters": {}, "date_range": {"from": "2026-10-05", "to": "2026-10-05"}}
  ]
}
```

Response batch có dạng `{"results":[{"id":"revenue","result":{...}},{"id":"trend","error":"..."}]}`. Lỗi đọc Silver được chuẩn hóa thành thông báo an toàn; API thử reconnect DuckDB/S3 tối đa ba lần, chờ 0,5 giây rồi 1 giây giữa các lần. Batch có dữ liệu một phần trả `200`; nếu không có widget nào đọc được do Silver unavailable, API trả `503`.

```json
{
  "model": "finance_daily",
  "metrics": ["revenue_usd", "roas_usd"],
  "dimensions": ["business_date", "app_id"],
  "filters": {"app_id": "blur_face"},
  "date_range": {"from": "2026-10-01", "to": "2026-10-03"}
}
```

Mỗi request chọn đúng một model; dimensions và metrics phải có trong model đó. Filters dùng dimension hợp lệ với giá trị scalar hoặc list. Date range inclusive, áp vào time dimension duy nhất của model kể cả khi dimension đó không nằm trong output. Query không hợp lệ trả `422`; Silver read error trả `503` với nội dung đã làm sạch. Kết quả giữ contract của shared `QueryResult`:

```json
{
  "model": "finance_daily",
  "dimensions": [],
  "metrics": [],
  "rows": []
}
```

### `GET /api/v1/dashboards` và `GET /api/v1/dashboards/{id}`

Config JSON được đọc read-only từ `backend/dashboard/config/`. Danh sách chỉ trả `id` và `title`, sắp xếp theo `id`; endpoint chi tiết trả toàn bộ config.

```json
{
  "dashboards": [
    {"id": "ua_app_overview", "title": "UA App Overview"}
  ]
}
```

ID không hợp lệ hoặc không có config trả `404`. Config không đọc được hoặc sai cấu trúc trả `500` với thông báo đã làm sạch. Config ban đầu là `ua_app_overview`; metric/dimension trong widget được đối chiếu với semantic registry bằng API tests.

## Phạm vi hiện tại

API expose apps, semantic metadata, query và dashboard JSON config. MCP expose apps, metric metadata và query qua `stdio` hoặc `Streamable HTTP`. Dashboard Next.js tiêu thụ các endpoint này; CORS dùng allowlist cấu hình ở trên. Authentication/Authorization chưa được triển khai trong phase này.

## Kiểm tra

Chạy toàn bộ automated tests (gồm MCP `stdio` và `Streamable HTTP` smoke tests) bằng:

```sh
cd backend && uv run python -m unittest discover -s tests -v
```

Dashboard checks chạy trong `dashboard/`:

```sh
pnpm test
pnpm run typecheck
pnpm run build
```
