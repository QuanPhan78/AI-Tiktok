# Đối chiếu tích hợp TikTok — cập nhật 16/11/2026

Content Studio đã dùng gói Automation trong cùng repo. Không cần chép lại source từ nhánh của Long hoặc tạo thêm bộ lập lịch.

## Đã xác nhận

| Hạng mục | Bằng chứng và giới hạn |
|---|---|
| Source Long | Nhánh `Automation` tại `704fdec` đã nằm toàn bộ trong `main`; không còn commit riêng chưa hợp nhất khi kiểm tra. |
| Điểm nối | Giao diện gọi `/api/v2/tiktok/*`, `/api/v2/publications` và API duyệt MP4; web chuyển yêu cầu có xác thực tới `/api/v2/publishing/*` của Automation. |
| Lịch | n8n chỉ bật Publishing Scheduler v2 cho dữ liệu này. Các workflow Step6/8/9 v1 giữ trong source, không bật trên cùng hàng đợi. |
| Ứng dụng đã bàn giao | Có cặp mã/khóa ứng dụng trong cấu hình dự án cũ. Đã dùng lại trong `.env` riêng của Automation v2, giữ callback v1. Không công bố giá trị khóa. |
| Quyền cũ | Bảng kết nối v1 có bản ghi `video.publish` và `video.upload`; access token ghi hết hạn ngày 17/10/2026. Đây chỉ là bằng chứng lịch sử, không xác nhận quyền hiện tại hoặc app đã được audit. |
| Token theo người | Không nhập token cũ vào tài khoản web. Người dùng phải đăng nhập TikTok và cấp quyền qua OAuth v2. |
| Dữ liệu | Sao lưu cấu hình và SQLite trước khi cập nhật; SEJOY r26 và MP4 đã duyệt tiếp tục giữ nguyên. Dữ liệu thật và bản sao lưu không nằm trên GitHub. |

## Các điểm đã sửa

- Hiện riêng điều kiện kết nối tài khoản và điều kiện gửi video, kèm việc cần làm cho từng cấu hình còn thiếu. Khóa mẫu, khóa mã hóa sai và callback không khớp đều bị phát hiện.
- Gửi lại đúng yêu cầu sau lỗi mạng trả cùng biên nhận, kể cả khi bộ xử lý đã tắt sau lượt đầu.
- Lịch bị chặn/quá giờ không được bật lại nếu đã có lượt thay thế đang chờ, đang gửi hoặc đã đăng cho cùng video/tài khoản.
- Tạm dừng gửi bài mới vẫn tiếp tục đọc kết quả bài đã gửi và đồng bộ Notion. Notion lỗi không làm gửi lại TikTok.
- Giữ caption đang sửa khi gửi lỗi; hiển thị lý do chưa thể đăng cả với video tải riêng.

## Còn thiếu để nghiệm thu đăng thật

1. Tạo tài khoản quản trị tại `/login` trên máy đang chạy. Người dùng tự nhập mật khẩu và lưu mã khôi phục.
2. Dùng địa chỉ HTTPS hoạt động trỏ tới gateway 8080; khai báo callback `/api/v2/tiktok/callback` trong **ứng dụng hiện có**. Chưa gán tên miền cũ vào v2 vì chưa xác nhận tunnel và quyền quản lý tên miền đó.
3. Xác minh tên miền tải MP4; chủ ứng dụng kiểm tra quyền Direct Post và trạng thái audit. Không bật cờ xác minh/audit chỉ để bỏ qua điều kiện.
4. Chủ tài khoản kết nối TikTok trong Content Studio. Sau khi đủ điều kiện, bật gửi bài mới và thử một lượt Đăng ngay, một lượt Đặt lịch với MP4 đã duyệt phù hợp.
5. Lưu mã lần gửi thật, trạng thái TikTok, thời gian xử lý và đối chiếu bài thực tế. Chưa có bằng chứng đăng thật trong đợt kiểm tra này.

Phần Long cần hỗ trợ, nếu người quản lý máy chưa có quyền vào Developer Portal: xác nhận đúng ứng dụng và thêm callback/xác minh tên miền. Source và phần tích hợp có thể tiếp tục vận hành trên máy chạy Content Studio.

## Kiểm tra lại

Đã đạt **190 kiểm thử**: 169 kiểm thử Python cho web/API và tích hợp, 10 kiểm thử hồi quy Automation, 11 kiểm thử JavaScript. Sau cập nhật Docker ngày 16/11/2026, web 8001, gateway 8080 và API 8000 trả kết quả bình thường; nội dung của cả ba phiên lưu trên máy có SHA-256 khớp trước cập nhật. SEJOY vẫn là bundle r26, MP4 v1, `APPROVED`.

Cấu hình đang chạy đã nhận mã/khóa ứng dụng cũ và khóa mã hóa. Còn thiếu địa chỉ HTTPS, callback v2, xác minh tên miền MP4 và tài khoản quản trị; bộ xử lý gửi bài mới vẫn tắt. Đây là kết quả kiểm tra dịch vụ trên máy, không phải bằng chứng đã đăng TikTok.

Từ gốc repo, chạy `python scripts/check_tiktok_setup.py` để đọc điều kiện cấu hình, và `python scripts/verify.py` để chạy kiểm thử tổng hợp. Cả hai không gửi bài TikTok. Chi tiết vận hành và giới hạn trong [hướng dẫn lập lịch và đăng](TIKTOK_PUBLISHING_V2.md).

Không dùng SEJOY r26 để nghiệm thu bài video thường: bản đó vẫn có câu kêu gọi giỏ hàng, còn tích hợp TikTok Shop chưa được triển khai. Các kiểm thử không tự sửa hoặc duyệt lại nội dung đó.
