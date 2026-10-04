# FastAPI

## Chạy local

API dùng cùng cấu hình Silver S3-compatible với `SilverDataSource`. Nạp các biến `APP_CONFIG__S3__SILVER__*` theo [Silver Connection](SILVER_CONNECTION.md), rồi chạy:

```sh
uv run uvicorn sora_semantic.api:app --host 127.0.0.1 --port 8000
```

Ứng dụng mở DuckDB/Ibis connection trong ASGI lifespan và đóng khi shutdown. Host mặc định trong lệnh trên chỉ bind loopback. API hiện chưa có authentication; chỉ expose qua mạng nội bộ được kiểm soát.

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

## Phạm vi hiện tại

API expose apps, semantic metadata và query. Dashboard UI, dashboard JSON endpoints, authentication và CORS chưa được triển khai.
