# FastAPI and MCP

## Chạy local

API dùng cùng cấu hình Silver S3-compatible với `SilverDataSource`. Theo [Silver Connection](SILVER_CONNECTION.md), đặt cấu hình trong `.env` ở repository root, rồi chạy các lệnh từ `backend/`:

```sh
uv sync --all-groups
uv run --env-file ../.env python scripts/run_api.py
```

Ứng dụng mở DuckDB/Ibis connection trong ASGI lifespan và đóng khi shutdown. Host mặc định trong lệnh trên chỉ bind loopback. API hiện chưa có authentication; chỉ expose qua mạng nội bộ được kiểm soát.

## FastMCP

MCP dùng cùng `SemanticRegistry` và `QueryService`, mở kết nối Silver read-only riêng theo lifespan của server. Có thể chạy local qua `stdio`:

```sh
uv run --env-file ../.env python scripts/run_mcp.py
```

Hoặc chạy server `Streamable HTTP` tại `/mcp`:

```sh
uv run --env-file ../.env python scripts/run_mcp.py --transport streamable-http
```

Hai lệnh dùng cùng biến môi trường Silver như API. MCP cung cấp `list_apps`, `list_metrics` và `query_metrics`; tool query nhận `model`, `metrics`, `dimensions`, `filters` và `date_range` theo shared `QueryRequest`. Kết quả dùng shape `model`, `dimensions`, `metrics`, `rows`; query contract lỗi được trả dưới dạng MCP tool error. Không có raw SQL tool.

Authorization và app scope chưa được triển khai trong dự án hiện tại. Bảo vệ server HTTP bằng network boundary phù hợp.

## Endpoints

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

Body theo shared `QueryRequest`: `model`, `metrics`, `dimensions`, `filters`, `date_range`.

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

API expose apps, semantic metadata, query và dashboard JSON config. MCP expose apps, metric metadata và query qua `stdio` hoặc `Streamable HTTP`. Dashboard UI, authentication và CORS chưa được triển khai trong phase này.

## Kiểm tra

Chạy toàn bộ automated tests (gồm MCP `stdio` và `Streamable HTTP` smoke tests) bằng:

```sh
cd backend
uv run python -m unittest discover -s tests -v
```
