# Đối chiếu tích hợp — cập nhật 21/11/2026

**TikTok đã xác nhận đăng hai bài riêng tư: Đăng ngay và Đặt lịch; nghiệm thu phát video chưa đạt.** Người dùng thấy đủ hai bài nhưng sau đó báo lỗi phát. Ảnh và kiểm tra trang trong trình duyệt xác nhận bài A hiện thông báo lỗi phát; chưa có kết quả đối chiếu trên điện thoại. Mở Studio không cần tài khoản quản trị. Hướng dẫn hiện hành: [Content Studio cá nhân](PERSONAL_STUDIO.md).

## Nghiệm thu đăng thật ngày 21/11/2026

- Dùng hai MP4 có sẵn, được người dùng xem và duyệt riêng trong mục **Video thường đã hoàn chỉnh**. Không khôi phục phiên SEJOY cũ, không gọi API tạo video trả phí.
- Dùng lại ứng dụng TikTok của dự án. OAuth v2 đã kết nối; đọc thông tin người đăng thành công, quyền riêng tư chọn `SELF_ONLY`.
- File xác minh URL do TikTok cấp được phục vụ qua HTTPS với nội dung khớp nguyên byte. Người dùng xác nhận người quản lý đã hoàn tất Verify; lượt gửi MP4 sau đó được TikTok chấp nhận.
- TikTok ban đầu từ chối vì tài khoản chưa riêng tư. Người dùng đã tự bật **Tài khoản riêng tư**; đây là thiết lập toàn tài khoản, khác với quyền **Chỉ mình tôi** của từng video. Giữ `TIKTOK_APP_AUDITED=0`.
- **Clip A, Đăng ngay:** gửi lúc 10:07:05 giờ Việt Nam; có mã gửi thật và trạng thái cuối `PUBLISHED`. Người dùng ban đầu xác nhận clip riêng tư 10 giây xuất hiện và phát được, sau đó cung cấp ảnh lỗi phát trong trình duyệt. Giữ cả hai ghi nhận theo thời điểm; chưa kết luận nguyên nhân.
- **Clip B, Đặt lịch:** đã kiểm tra đổi giờ và hủy lượt cũ trước hạn. Lịch cuối lúc 10:17:19 giờ Việt Nam; workflow tự gửi lúc 10:17:31, TikTok xác nhận `PUBLISHED` lúc 10:18:31. Thời điểm gửi lệch khoảng 12 giây so với lịch, phù hợp chu kỳ xử lý mỗi phút; TikTok tiếp tục xử lý trước khi hoàn tất.
- Đã khởi động lại Automation và n8n trước hạn. Đọc lại cho thấy lịch cuối và hai quyết định duyệt vẫn còn; lịch cũ vẫn `CANCELLED`.
- Sau giờ của lịch đã hủy hơn một phút, lượt đó vẫn `CANCELLED` và không có mã đăng TikTok. API có đúng hai lượt `PUBLISHED`, một lượt hủy; không có lượt gửi thừa.
- Gửi lại đúng mã yêu cầu A đã hoàn tất trả về cùng bản ghi `PUBLISHED`; số lượt không tăng và không gửi thêm bài.
- Bộ kiểm thử trên máy ngày 21/11/2026 đạt **221/221**: 199 unittest Python, 10 hồi quy Automation và 12 JavaScript. Bộ kiểm thử cách ly khóa/dữ liệu thật và không gọi đăng TikTok; các lượt đăng thật bên trên là nghiệm thu riêng.
- Mã lượt, mã gửi TikTok, hash MP4, thời điểm xử lý, snapshot API và xác nhận người dùng được lưu trong biên bản riêng ngoài Git. Khóa, tên tài khoản và video thật không nằm trong tài liệu xuất bản.

### Kiểm tra lỗi phát — 18:35 ngày 21/11/2026, giờ Việt Nam

- Đọc lại trực tiếp hai mã gửi: TikTok trả `PUBLISH_COMPLETE`, mã `ok`, không có lý do lỗi. API không trả số byte đã tải ở lần đọc này; không diễn giải trường thiếu thành 0 byte.
- File gốc và dữ liệu trả qua Studio khớp nguyên byte; tải từng phần trả HTTP 206 đúng nội dung. Cả hai file lưu trong Automation khớp hash đã duyệt.
- Giải mã hết hình và tiếng bằng FFmpeg đều không có lỗi. Hai clip là H.264 High, yuv420p, 720 × 1280, 24 fps, AAC-LC 48 kHz stereo, dài khoảng 10 và 30 giây.
- Trang bài A trong Edge vẫn hiện lỗi phát. Chưa có kết quả so sánh trên điện thoại hoặc trình duyệt khác; chưa kết luận nguyên nhân. Chưa có cơ sở chuyển mã hoặc đăng lại.
- Vẫn đúng hai lượt `PUBLISHED` và một lượt `CANCELLED`; không tạo thêm lượt, không xóa bài. Xem [cách kiểm tra bài đã đăng nhưng không phát](TIKTOK_PUBLISHING_V2.md#bài-đã-đăng-nhưng-không-phát-được).

## Mốc kiểm tra trước đó — 18/11/2026

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

## Những bước còn chờ tại mốc 18/11/2026

1. **Quyền ứng dụng:** người đang quản lý ứng dụng TikTok của dự án xác nhận quyền sử dụng, cấu hình callback v2 theo tên miền đang chạy, tài khoản thử và `video.publish`. Nếu muốn tự làm, dùng tài khoản có quyền quản lý ứng dụng đó.
2. **Tên miền MP4:** xác minh tên miền hoặc URL prefix `/media/tiktok/` trong Developer Portal, đặt file xác minh được cấp vào thư mục `verification/` và kiểm tra hoàn tất. HTTPS hoạt động chưa phải xác minh TikTok.
3. **Kết nối tài khoản:** người dùng đăng nhập TikTok từ Studio và tự cấp quyền. Giữ trạng thái chưa audit nếu chưa có kết quả audit thực tế.
4. **Video mới:** tạo phiên Video thường bằng dữ liệu minh họa, duyệt đủ bảy bước; tạo clip trong Gemini khi còn lượt miễn phí, xem/ghép MP4 tối đa 45 MB. Lưu nội dung vào Notion, tải MP4 và duyệt thật qua Telegram; đối chiếu cả ba nơi.
5. **Hai lượt riêng tư:** sau khi đủ điều kiện mới bật bộ gửi bài. Dùng hai MP4 được duyệt riêng để thử Đăng ngay và Đặt lịch, chọn `SELF_ONLY`. Lưu mã lượt, hash MP4, thời gian, kết quả TikTok và bằng chứng trên tài khoản.

Giới hạn của ứng dụng chưa audit và điều kiện sử dụng Direct Post xem [tài liệu TikTok](https://developers.tiktok.com/docs/en/content-sharing-guidelines). Hướng dẫn chuyển MP4 và xác minh xem [Media Transfer Guide](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide). Đợt này không cam kết đăng công khai từ công cụ cá nhân và không mua thêm hạn mức dịch vụ.

Từ gốc repo, `python scripts/check_tiktok_setup.py` chỉ đọc điều kiện cấu hình; `ready: true` không thay thế việc kiểm tra quyền, MP4 và bài thật. Chi tiết vận hành: [lập lịch và đăng](TIKTOK_PUBLISHING_V2.md).
