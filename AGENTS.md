# Repository Guidelines

## Cấu trúc dự án

Backend Python nằm trong `backend/`: package ở `backend/src/sora_semantic/`, launcher ở `backend/api.py` và `backend/mcp.py`, tests ở `backend/tests/`, dashboard JSON do API phục vụ ở `backend/dashboard/config/`. Dashboard TypeScript là ứng dụng riêng tại `dashboard/`. Direnv nạp `.env.shared` và env riêng của app. Chi tiết thành phần và luồng dữ liệu nằm trong [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Phát triển và kiểm thử

Quản lý dependencies bằng `uv` trên Python 3.14 và env tự nạp bằng `direnv`; chạy các lệnh backend từ thư mục `backend/`. Launcher là `api.py` và `mcp.py`. Hướng dẫn nằm trong [README.md](README.md) và [docs/API.md](docs/API.md). Chạy automated tests:

```sh
uv run python -m unittest discover -s tests -v
```

Chạy API và MCP xem [docs/API.md](docs/API.md). Không báo một bước kiểm tra đã đạt nếu chưa thực thi.

## Quy ước code

Python Core dùng Python 3.14 và `uv`; Dashboard dùng Next.js, TypeScript và React. Dùng formatter/linter tiêu chuẩn được chọn cho từng toolchain khi chúng được cấu hình; giữ thay đổi tập trung và tên biến/hàm/mô-đun mô tả đúng trách nhiệm. Định nghĩa metric/dimension trong semantic layer, không tạo endpoint riêng cho từng metric hoặc hard-code dashboard thành từng trang React.

## Kiểm thử

Kiểm thử dùng Python `unittest`. Bổ sung kiểm thử hành vi cùng phần triển khai, gồm regression cho bug fix. Với vertical slice MVP, xác nhận luồng query từ Silver Parquet qua DuckDB/Ibis và API tới dashboard JSON.

## Commit và Pull Request

Repo chưa có lịch sử commit. Tạm dùng subject ngắn, mệnh lệnh, ví dụ `Add semantic metric registry`. Pull Request cần mô tả mục đích, liên kết issue nếu có, liệt kê kiểm tra đã chạy và đính kèm ảnh hoặc output mẫu khi thay đổi hiển thị.

## Dữ liệu và bí mật

Silver Parquet trên RustFS là source of truth; DuckDB chỉ là query engine. Chỉ đọc Silver, không thêm ETL hoặc sửa dự án Sora trong phạm vi này. Không commit credentials, token hoặc cấu hình riêng của máy; dùng cấu hình mẫu và biến môi trường khi ứng dụng được triển khai.
