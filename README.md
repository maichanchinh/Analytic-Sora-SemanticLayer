# Sora Semantic Layer

Analytics layer chỉ đọc Silver Parquet từ Sora trên RustFS. Backend Python cung cấp FastAPI và FastMCP; Dashboard Next.js gọi API để hiển thị dữ liệu.

Tài liệu: [Architecture](docs/ARCHITECTURE.md), [Silver Data Catalog](docs/SILVER_DATA_CATALOG.md), [kết nối Silver](docs/SILVER_CONNECTION.md), [API và MCP](docs/API.md).

## Cấu hình

Yêu cầu: Python 3.14, [`uv`](https://docs.astral.sh/uv/), Node.js 20.12+ và pnpm 10+.

Tạo các file cấu hình local:

```sh
cp -n .env.example .env
cp -n backend/.env.example backend/.env
cp -n dashboard/.env.example dashboard/.env
```

Các app tự đọc `.env` ở root và trong thư mục app. Giá trị trong `backend/.env` hoặc `dashboard/.env` ưu tiên hơn giá trị trùng tên ở root. Điền endpoint và credential RustFS chỉ đọc Silver trong `backend/.env`. Không đặt secret backend vào biến `NEXT_PUBLIC_*`.

## Chạy API

```sh
cd backend
uv sync --all-groups
uv run api.py
```

Khi cần xem log chi tiết lúc kiểm tra app hoặc lỗi truy vấn, chạy `uv run api.py --debug`.

API lắng nghe tại `http://127.0.0.1:8000`. Kiểm tra endpoint apps:

```sh
curl http://127.0.0.1:8000/api/v1/apps
```

API chưa có authentication; chỉ expose trong mạng nội bộ được kiểm soát.

## Chạy MCP

Mặc định chạy Streamable HTTP tại `http://127.0.0.1:8001/mcp` (dùng được với MCP Inspector):

```sh
cd backend && uv run mcp.py
```

Chọn stdio nếu MCP client yêu cầu transport này:

```sh
cd backend && uv run mcp.py --transport stdio
```

## Chạy Dashboard

```sh
cd dashboard
pnpm install
pnpm dev
```

Dashboard mặc định chạy tại `http://localhost:3000`; API mặc định cho phép origin này trong CORS.

## Tests

Tests backend dùng Silver giả lập, không cần credential hoặc kết nối RustFS:

```sh
cd backend && uv run python -m unittest discover -s tests -v
```
