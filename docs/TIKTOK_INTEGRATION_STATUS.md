# Đối chiếu tích hợp — cập nhật 18/11/2026

**Bản dùng cá nhân đã chạy trên máy, HTTPS và webhook Telegram đã kết nối. Chưa nghiệm thu đăng TikTok thật.** Mở Studio không cần tài khoản quản trị. Hướng dẫn hiện hành: [Content Studio cá nhân](PERSONAL_STUDIO.md).

## Source và dữ liệu

- Source nhánh `Automation` đã nằm trong `main`; tiếp tục dùng `integrations/long-v2/`, không dựng thêm hệ thống lập lịch.
- Dữ liệu cũ, ảnh/MP4, lịch sử và cấu hình đã sao lưu riêng trước khi làm sạch. Không khôi phục SEJOY vào ứng dụng. Khóa dịch vụ được giữ trên máy, không đưa lên GitHub.
- Phiên mới mặc định **Video thường**, có thể chọn **Video TikTok Shop**. Video thường duyệt cả lời kết; Shop giữ mẫu chốt của Bảo và bị chặn đăng tự động.
- Gói mới **2.1** ghi loại nội dung. Gói **2.0** vẫn là mẫu Shop cũ, giữ cách kiểm tra và SHA-256; không tự chuyển đổi bản lưu.

## Đã kiểm tra trên hệ thống đang chạy

| Hạng mục | Kết quả thực tế và giới hạn |
|---|---|
| Dịch vụ | Web 8001, Automation 8000, n8n 5678, gateway 8080 hoạt động trên project Docker đang dùng. |
| Bản cá nhân | API không yêu cầu đăng nhập; dữ liệu phiên đã được làm sạch. Kiểm tra trực quan cuối đợt chưa hoàn tất vì công cụ điều khiển trình duyệt không xác định chắc chắn URL tab. |
| HTTPS | Tên miền phát triển ngrok đã được đối chiếu trong tài khoản người dùng; một tunnel trỏ đúng gateway 8080. Trang chính sách trả 200 và nhận diện đúng gateway. Trang `/app` qua địa chỉ công khai trả 404. |
| Telegram | Bot v2 đã chuyển sang webhook trên tên miền ngrok mới. Đọc lại webhook trùng địa chỉ; không có cập nhật tồn hoặc lỗi cuối ở thời điểm kiểm tra. Yêu cầu sai khóa bị từ chối. Chưa gửi MP4 mới hoặc thực hiện một lượt duyệt thật sau khi làm sạch. |
| n8n | Đang bật đúng ba workflow v2: bàn giao nội dung, duyệt video và xử lý lịch. Không bật workflow v1 trên cùng hàng đợi. |
| Contract đang chạy | Gửi dữ liệu thăm dò thiếu trường 2.0 và 2.1 qua n8n đều tới bước kiểm tra của Automation và bị từ chối 422 đúng dự kiến; không tạo trang Notion. Đây là kiểm tra đường kết nối, không phải biên nhận bàn giao thành công. |
| Ứng dụng TikTok | Giữ cấu hình ứng dụng đã bàn giao. Tài khoản Developer đang đăng nhập không hiển thị ứng dụng hoặc tổ chức; chưa xác nhận quyền quản lý ứng dụng của dự án. Không tạo ứng dụng mới. |
| Gửi bài | Chưa có tài khoản OAuth v2 mới. Cờ xác minh tên miền, bộ gửi bài và audit vẫn tắt; không bật cờ để tạo trạng thái sẵn sàng giả. |

## Kiểm thử tự động

**208 kiểm thử đạt trên máy:** 186 kiểm thử Python Studio/API/contract, 10 hồi quy Automation, 12 JavaScript cho tiện ích, trợ lý và đăng bài. Bao gồm:

- Hai loại nội dung, 4/5 cảnh, nói trực tiếp/thuyết minh; đủ duyệt mới xuất, lời thoại đã duyệt giữ nguyên.
- Đổi loại ở Bước 1 hủy xác nhận phụ thuộc; sửa revision/MP4 làm mất hiệu lực quyết định cũ và hủy lịch chưa gửi.
- Tương thích 2.0/2.1, JSON và prompt dài qua n8n, đối chiếu biên nhận/readback, thử lại không tạo bản trùng; dịch vụ Notion trong các bài này được giả lập.
- Đặt/đổi/hủy lịch, giữ dữ liệu sau khởi động lại, lỗi token/mạng, đối chiếu kết quả trước gửi lại; lỗi Notion không làm đăng lại.
- Bản cá nhân chặn truy cập ngoài máy, gateway không mở trang chỉnh sửa; tiện ích vẫn chỉ điền nguyên prompt đã duyệt.

Chạy `python scripts/verify.py` để kiểm tra lại; lệnh cách ly dữ liệu và khóa thật, không gọi tạo video, Notion, Telegram hoặc đăng TikTok. Kiểm thử tự động không được tính là nghiệm thu bên ngoài.

## Những bước còn chờ

1. **Quyền ứng dụng:** người đang quản lý ứng dụng TikTok của dự án xác nhận quyền sử dụng, cấu hình callback v2 theo tên miền đang chạy, tài khoản thử và `video.publish`. Nếu muốn tự làm, dùng tài khoản có quyền quản lý ứng dụng đó.
2. **Tên miền MP4:** xác minh tên miền hoặc URL prefix `/media/tiktok/` trong Developer Portal, đặt file xác minh được cấp vào thư mục `verification/` và kiểm tra hoàn tất. HTTPS hoạt động chưa phải xác minh TikTok.
3. **Kết nối tài khoản:** người dùng đăng nhập TikTok từ Studio và tự cấp quyền. Giữ trạng thái chưa audit nếu chưa có kết quả audit thực tế.
4. **Video mới:** tạo phiên Video thường bằng dữ liệu minh họa, duyệt đủ bảy bước; tạo clip trong Gemini khi còn lượt miễn phí, xem/ghép MP4 tối đa 45 MB. Lưu nội dung vào Notion, tải MP4 và duyệt thật qua Telegram; đối chiếu cả ba nơi.
5. **Hai lượt riêng tư:** sau khi đủ điều kiện mới bật bộ gửi bài. Dùng hai MP4 được duyệt riêng để thử Đăng ngay và Đặt lịch, chọn `SELF_ONLY`. Lưu mã lượt, hash MP4, thời gian, kết quả TikTok và bằng chứng trên tài khoản.

Giới hạn của ứng dụng chưa audit và điều kiện sử dụng Direct Post xem [tài liệu TikTok](https://developers.tiktok.com/docs/en/content-sharing-guidelines). Hướng dẫn chuyển MP4 và xác minh xem [Media Transfer Guide](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide). Đợt này không cam kết đăng công khai từ công cụ cá nhân và không mua thêm hạn mức dịch vụ.

Từ gốc repo, `python scripts/check_tiktok_setup.py` chỉ đọc điều kiện cấu hình; `ready: true` không thay thế việc kiểm tra quyền, MP4 và bài thật. Chi tiết vận hành: [lập lịch và đăng](TIKTOK_PUBLISHING_V2.md).
