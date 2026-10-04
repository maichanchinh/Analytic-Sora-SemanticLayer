# Sora Semantic Layer

Analytics layer chỉ đọc Silver Parquet từ Sora trên RustFS. Backend Python cung cấp semantic metrics và dimensions qua FastAPI và FastMCP; Dashboard là ứng dụng TypeScript độc lập trong cùng repository.

Tài liệu: [Architecture](docs/ARCHITECTURE.md), [Silver Data Catalog](docs/SILVER_DATA_CATALOG.md), [kết nối Silver](docs/SILVER_CONNECTION.md), [API và MCP](docs/API.md).

## Yêu cầu

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/)
- [`direnv`](https://direnv.net/) with zsh hook enabled
- Credential RustFS chỉ có quyền đọc Silver để chạy API/MCP với dữ liệu thật

## Cài đặt và cấu hình

Backend nằm trong `backend/`; Dashboard TypeScript sẽ nằm trong `dashboard/`. `direnv` hiện được cấu hình bằng `.envrc` ở root và từng app. Tạo các file local từ mẫu:

Trên macOS/zsh, cài `direnv` bằng Homebrew nếu máy chưa có; bảo đảm `eval "$(direnv hook zsh)"` nằm trong `~/.zshrc`, rồi mở shell mới:

```sh
brew install direnv
```

```sh
cp -n .env.shared.example .env.shared
cp -n backend/.env.example backend/.env.local
cp -n dashboard/.env.example dashboard/.env.local
```

`.env.shared` chỉ dành cho biến an toàn, thật sự dùng chung. Biến riêng và credential Silver để trong `backend/.env.local`; config riêng Dashboard để trong `dashboard/.env.local`. Các file local đã bị Git ignore. Không đưa secret backend vào biến `NEXT_PUBLIC_*`.

Cho phép `direnv` đọc các `.envrc` đã review, mỗi thư mục một lần:

```sh
direnv allow .
direnv allow backend
direnv allow dashboard
cd ..
```

`.envrc` root nạp shared env; `.envrc` mỗi app nạp shared trước và `.env.local` sau.

Cài backend dependencies từ thư mục backend:

```sh
cd backend
uv sync --all-groups
```

Điền bảy biến `APP_CONFIG__S3__SILVER__*` trong `backend/.env.local` bằng endpoint, bucket, region và credential read-only của RustFS.

## Chạy API

Khởi động API trên `127.0.0.1:8000`:

```sh
cd backend && uv run api.py
```

Trong terminal khác, kiểm tra kết nối Silver và endpoint apps:

```sh
curl http://127.0.0.1:8000/api/v1/apps
```

API hiện chưa có authentication; chỉ expose trong mạng nội bộ được kiểm soát.

## Chạy MCP

Kết nối qua `stdio` khi MCP client khởi chạy server process:

```sh
cd backend && uv run mcp.py
```

Hoặc khởi chạy MCP qua `Streamable HTTP` tại `http://127.0.0.1:8001/mcp`:

```sh
cd backend && uv run mcp.py --transport streamable-http
```

MCP tools gồm `list_apps`, `list_metrics`, `query_metrics`. Authorization và app scope chưa được triển khai; giữ HTTP server trong network boundary phù hợp.

## Chạy tests

Tests dùng Silver giả lập và không cần `.env` hoặc kết nối RustFS:

```sh
cd backend && uv run python -m unittest discover -s tests -v
```

Các lệnh API/MCP/Test chạy từ `backend/`; sau khi direnv load env, không cần `--env-file`.
