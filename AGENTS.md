# Repository Guidelines

## Cấu trúc dự án

Định hướng cấu trúc gồm Python Core trong `src/sora_semantic/` và Dashboard trong `dashboard/`; cấu hình dashboard JSON đặt tại `dashboard/config/`, kiểm thử Python tại `tests/`. Chi tiết thành phần và luồng dữ liệu nằm trong [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Đây là cấu trúc mục tiêu; hiện repo mới có tài liệu, chưa có source code hoặc toolchain.

## Phát triển và kiểm thử

Chưa có lệnh build, chạy, lint hay test vì chưa khởi tạo Python Core và Dashboard. Khi bổ sung toolchain, cập nhật lệnh chuẩn ở đây và trong README trước khi yêu cầu người đóng góp chạy chúng. Không báo một bước kiểm tra đã đạt nếu chưa thực thi.

## Quy ước code

Python Core dùng Python 3.13 và `uv`; Dashboard dùng Next.js, TypeScript và React. Dùng formatter/linter tiêu chuẩn được chọn cho từng toolchain khi chúng được cấu hình; giữ thay đổi tập trung và tên biến/hàm/mô-đun mô tả đúng trách nhiệm. Định nghĩa metric/dimension trong semantic layer, không tạo endpoint riêng cho từng metric hoặc hard-code dashboard thành từng trang React.

## Kiểm thử

Chưa chọn framework kiểm thử hoặc ngưỡng coverage. Khi triển khai code, thêm kiểm thử cho hành vi cùng phần triển khai, bao gồm regression cho bug fix; ghi lệnh chạy chính xác khi framework được thiết lập. Với vertical slice MVP, xác nhận luồng query từ Silver Parquet qua DuckDB/Ibis và API tới dashboard JSON.

## Commit và Pull Request

Repo chưa có lịch sử commit. Tạm dùng subject ngắn, mệnh lệnh, ví dụ `Add semantic metric registry`. Pull Request cần mô tả mục đích, liên kết issue nếu có, liệt kê kiểm tra đã chạy và đính kèm ảnh hoặc output mẫu khi thay đổi hiển thị.

## Dữ liệu và bí mật

Silver Parquet trên RustFS là source of truth; DuckDB chỉ là query engine. Chỉ đọc Silver, không thêm ETL hoặc sửa dự án Sora trong phạm vi này. Không commit credentials, token hoặc cấu hình riêng của máy; dùng cấu hình mẫu và biến môi trường khi ứng dụng được triển khai.
