# Docker Compose và Dockhand

## Dịch vụ và địa chỉ

Compose build image tại chỗ từ Dockerfile; API và MCP dùng chung backend image, Dashboard có image riêng. Ba service dùng chung `BUILD_CONTEXT` (mặc định `.`), còn mỗi image chọn Dockerfile riêng. Path tương đối tính từ Compose project directory; có thể đặt `BUILD_CONTEXT` thành path tuyệt đối khi Dockhand checkout repo ở vị trí riêng. Không cần registry.

| Service | Host port mặc định | Địa chỉ |
| --- | ---: | --- |
| API | `8000` | `http://localhost:8000`; readiness: `/api/v1/apps` |
| MCP | `8001` | `http://localhost:8001/mcp` (Streamable HTTP) |
| Dashboard | `3000` | `http://localhost:3000` |

Container dùng network mặc định của Compose và phân giải nhau bằng service name. Dashboard chạy trong browser, vì vậy `NEXT_PUBLIC_API_BASE_URL` phải là URL API mà browser của người dùng truy cập được; không đặt giá trị đó thành `http://api:8000`.

## Chạy local

```sh
cp .env.example .env
# Điền endpoint, bucket và credentials RustFS read-only trong .env.
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Chạy riêng service (Compose vẫn build image nếu chưa có):

```sh
docker compose up --build -d api
docker compose up --build -d mcp
docker compose up --build -d dashboard
```

Xem log riêng hoặc dừng stack:

```sh
docker compose logs -f api
docker compose logs -f mcp
docker compose logs -f dashboard
docker compose down
```

Override host ports bằng `API_HOST_PORT`, `MCP_HOST_PORT`, `DASHBOARD_HOST_PORT`; container ports giữ cố định để command và healthcheck luôn khớp. Compose khởi chạy API bằng Uvicorn và MCP qua `mcp.py --transport streamable-http --host 0.0.0.0 --port 8001`, đúng lệnh hướng dẫn chạy Docker bên dưới.

Compose chạy backend với `APP_ENV=production`. API và MCP xuất JSON logs ra stdout; mỗi event có timestamp UTC, level, service, logger, message và `request_id` khi log có thông tin này. Đặt `LOG_LEVEL` thành `DEBUG`, `INFO`, `WARNING`, `ERROR` hoặc `CRITICAL`; mặc định là `INFO`. Docker `json-file` giữ tối đa 5 file, mỗi file 10 MB. Dashboard chạy với `NODE_ENV=production`; Docker cũng giới hạn dung lượng log service này.

`api` healthcheck gọi `/api/v1/apps`, nên chỉ healthy khi API khởi động và đọc được Silver. `mcp` healthcheck xác nhận TCP listener; `dashboard` healthcheck xác nhận trang Next.js trả HTTP thành công. Healthcheck MCP không xác nhận một tool call có thể đọc Silver.

## Biến môi trường

API và MCP nhận cùng cấu hình Silver từ các biến `APP_CONFIG__S3__SILVER__*` trong `.env` hoặc Dockhand Compose environment. Bắt buộc: `ENDPOINT_URL`, `BUCKET`, `REGION_NAME`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`; `ADDRESSING_STYLE` mặc định `path`, `VERIFY_SSL` mặc định `true`. Dùng key chỉ có quyền đọc/list Silver. `LOG_LEVEL` điều khiển ngưỡng log của backend.

`CORS_ORIGINS` là danh sách browser origins được phép gọi API, phân tách bằng dấu phẩy; thêm origin của Dashboard, ví dụ hostname Tailscale hoặc domain HTTPS. `DASHBOARD_CORS_ORIGINS` cũ vẫn được hỗ trợ làm fallback. `NEXT_PUBLIC_API_BASE_URL` là build argument của Dashboard nên cần rebuild Dashboard image sau khi đổi URL; đây là URL công khai, không chứa credentials. Không truyền Silver credentials bằng build args.

Không cần bind mount/volume: dữ liệu được đọc từ RustFS qua S3, DuckDB chạy in-memory, dashboard JSON được đóng gói cùng backend. API và MCP không ghi dữ liệu về Sora.

## Deploy bằng Git và Dockhand

1. Trong Dockhand, tạo stack từ Git repository `maichanchinh/Analytic-Sora-SemanticLayer`, chọn branch SOF-72 và file `compose.yaml`.
2. Thêm các biến Silver vào Compose environment của stack; không commit `.env` hoặc credentials vào Git. Đặt `NEXT_PUBLIC_API_BASE_URL` theo hostname/IP mà browser sử dụng và thêm origin Dashboard vào `CORS_ORIGINS`.
3. Đặt host port nếu mặc định `8000`, `8001`, `3000` bị chiếm; không cần khai báo volume.
4. Chọn build khi deploy / recreate để Dockhand build từ `backend/Dockerfile` và `dashboard/Dockerfile`, sau đó deploy ba service.
5. Xem health và logs riêng trong Dockhand. Mở Dashboard tại `http://<homelab-host>:<DASHBOARD_HOST_PORT>`; API `/api/v1/apps`; MCP `/mcp` tại port đã chọn.

## Build image trực tiếp

Build backend image (mặc định chạy API):

```sh
docker build -f backend/Dockerfile -t sora-semantic-backend .
docker run --rm --env-file .env -p 8000:8000 sora-semantic-backend
```

Chạy MCP từ cùng image:

```sh
docker run --rm --env-file .env -p 8001:8001 sora-semantic-backend \
  mcp.py --transport streamable-http --host 0.0.0.0 --port 8001
```

Build Dashboard, đặt `NEXT_PUBLIC_API_BASE_URL` thành API URL truy cập được từ browser:

```sh
docker build -f dashboard/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 \
  -t sora-semantic-dashboard .
docker run --rm -p 3000:3000 sora-semantic-dashboard
```
