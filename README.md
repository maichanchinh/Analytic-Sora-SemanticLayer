# Sora Semantic Layer

Analytics layer chỉ đọc Silver Parquet từ Sora trên RustFS. Backend Python cung cấp semantic metrics và dimensions qua FastAPI và FastMCP; Dashboard là ứng dụng TypeScript độc lập trong cùng repository.

Tài liệu: [Architecture](docs/ARCHITECTURE.md), [Silver Data Catalog](docs/SILVER_DATA_CATALOG.md), [kết nối Silver](docs/SILVER_CONNECTION.md), [API và MCP](docs/API.md).

## Yêu cầu

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/)
- Credential RustFS chỉ có quyền đọc Silver để chạy API/MCP với dữ liệu thật

## Cài đặt và cấu hình

Backend nằm trong `backend/`; Dashboard TypeScript nằm trong `dashboard/`. Cài dependencies Python từ thư mục backend:

```sh
cd backend
uv sync --all-groups
```

Tạo file cấu hình local ở repository root:

```sh
cp ../.env.example ../.env
```

Điền đủ bảy biến `APP_CONFIG__S3__SILVER__*` trong `.env` bằng endpoint, bucket, region và credential read-only của RustFS. Không commit file `.env` hoặc chia sẻ giá trị credential. Ứng dụng không tự đọc `.env`; các lệnh bên dưới dùng `uv run --env-file ../.env` để nạp cấu hình vào process.

## Chạy API

Khởi động API trên `127.0.0.1:8000`:

```sh
uv run --env-file ../.env python scripts/run_api.py
```

Trong terminal khác, kiểm tra kết nối Silver và endpoint apps:

```sh
curl http://127.0.0.1:8000/api/v1/apps
```

API hiện chưa có authentication; chỉ expose trong mạng nội bộ được kiểm soát.

## Chạy MCP

Kết nối qua `stdio` khi MCP client khởi chạy server process:

```sh
uv run --env-file ../.env python scripts/run_mcp.py
```

Hoặc khởi chạy MCP qua `Streamable HTTP` tại `http://127.0.0.1:8001/mcp`:

```sh
uv run --env-file ../.env python scripts/run_mcp.py --transport streamable-http
```

MCP tools gồm `list_apps`, `list_metrics`, `query_metrics`. Authorization và app scope chưa được triển khai; giữ HTTP server trong network boundary phù hợp.

## Chạy tests

Tests dùng Silver giả lập và không cần `.env` hoặc kết nối RustFS:

```sh
uv run python -m unittest discover -s tests -v
```

Chạy lệnh test từ `backend/`.
