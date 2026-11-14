# Bản hợp nhất Content Studio

Đối chiếu ngày 14/11/2026 bằng các nhánh tải trực tiếp từ GitHub. `main` là bản dùng chung để clone và chạy toàn bộ chương trình.

## Kết quả đối chiếu nhánh

| Nhánh tại thời điểm kiểm tra | Commit | Nội dung và cách hợp nhất |
|---|---|---|
| `main` | `6b47461` | Web duyệt 7 bước, Automation v2, MP4, Notion, Telegram và hướng dẫn vận hành. |
| `Automation` | `704fdec` | Toàn bộ lịch sử đã nằm trong `main`, không có commit riêng còn thiếu. |
| `docs/content-studio-v2-handoff` | `6a700aa` | Gói bàn giao ban đầu; toàn bộ lịch sử đã nằm trong `main`. |
| Bản làm việc trên máy | Sau `6b47461` | Bổ sung vào `main` tiện ích Gemini, bộ đầu vào Notebook, chữ trên web và kiểm thử chung. |

Các nhánh cũ được giữ làm lịch sử. Không cần xóa nhánh hoặc chép source thủ công giữa các nhánh. Công việc mới tạo nhánh từ `main` mới nhất rồi mở PR về `main`.

## Các phần nối với nhau như thế nào

| Phần | Source | Vai trò và điểm nối |
|---|---|---|
| Web và AI | `web/`, `api/`, `studio/`, `prompts/` | Cổng 8001, lưu phiên SQLite, duyệt 7 bước, xuất bundle đã chốt. |
| Notebook và tiện ích | `studio/output.py`, `extensions/gemini/` | Cùng bundle revision, prompt nguyên văn và hai ảnh từ ZIP. Tiện ích chỉ điền prompt vào tab Gemini khi người dùng bấm. |
| Automation | `integrations/long-v2/` | API 8000, n8n 5678, nhận JSON nguyên vẹn, lưu Notion, duyệt đúng MP4 qua Telegram. |
| Contract | `contracts/handoff_v2.py` và bản trong Automation | Hai bản phải khớp; kiểm thử phát hành kiểm tra tự động. |
| Dữ liệu thật | `STUDIO_DATA_DIR`, Docker volume | Giữ riêng trên máy chạy; không đi theo Git. |

Đã thống nhất tên thao tác trên web, hướng dẫn và tiện ích. ZIP có `handoff.json`, `prompts.md`, `gemini-notebook.md` cùng hai ảnh. Endpoint xuất hỗ trợ `notebook`, đối chiếu revision để không sao chép nhầm bản. Bộ kiểm thử chung bao gồm cả kiểm tra lỗi, trùng thao tác, mất kết nối và nút Telegram của bản MP4 cũ.

Pipeline v1 vẫn dùng endpoint/workflow riêng để tương thích. Workflow đăng TikTok v1 không tự nhận một MP4 v2 chỉ vì trạng thái là `APPROVED`. Luồng v2 hiện bàn giao MP4, caption và hashtag cho người quản lý tài khoản đăng theo [hướng dẫn](HANDOFF_CONTENT_STUDIO_V2.md#6-bàn-giao-để-đăng-tiktok).

## Cập nhật một máy đã cài

1. Xác định đúng thư mục đang chạy server và thư mục tiện ích Edge/Chrome đã chọn. Sao lưu `.env`, `STUDIO_DATA_DIR` và volume trước khi chuyển hẳn sang một bản clone khác. `git pull` không mang dữ liệu phiên từ máy khác về.
2. Chạy `git status`. Nếu còn thay đổi riêng, commit vào nhánh riêng hoặc sao lưu trước; không reset hoặc chép đè. Khi cây làm việc sạch, chạy `git fetch origin`, `git switch main`, `git pull --ff-only origin main`.
3. Cài lại `requirements.txt`; nếu chạy kiểm thử thì cài `requirements-test.txt`, có Node.js, rồi chạy `python scripts/verify.py`. Kiểm tra cấu hình mẫu để bổ sung biến còn thiếu, không ghi đè `.env` thật.
4. Khởi động lại đúng server web. Nếu cập nhật Automation, chạy lại Compose trong thư mục gói đang dùng với đúng cấu hình và giữ volume. Không chạy thêm một stack khác trên cùng cổng.
5. Trong trang Tiện ích của Edge/Chrome, bấm tải lại **Content Studio · Gemini**, rồi tải lại tab web. Nếu chuyển thư mục clone, cài tiện ích từ thư mục mới.
6. Mở phiên cũ và đối chiếu revision prompt, hai ảnh, MP4 và trạng thái duyệt. Tạo một phiên thử riêng cho nội dung mới.

`scripts/verify.py` chạy bằng dữ liệu tổng hợp và vùng dữ liệu tạm. GitHub Actions chạy cùng suite trên Linux/Python 3.12 và Windows/Python 3.13. Các kiểm thử gọi dịch vụ thật chỉ chạy khi đang nghiệm thu riêng, không tự chạy khi đẩy code.

## Việc tiếp theo

[Trợ lý chat ngay trong Content Studio](CHATBOX_PLAN.md) sẽ dùng trạng thái phiên và quy trình duyệt hiện có. Đây là kế hoạch phát triển tiếp theo; bản hợp nhất chưa có hộp chat.
