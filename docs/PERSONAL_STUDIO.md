# Content Studio cá nhân — hướng dẫn chạy

Mở [Content Studio](http://127.0.0.1:8001/app) để dùng ngay. Không có bước tạo quản trị hoặc đăng nhập Studio. Đăng nhập Gemini, Telegram và cấp quyền TikTok vẫn thuộc tài khoản dịch vụ của bạn.

## Mở hệ thống

Cần Docker Desktop, Python và các gói trong `requirements.txt`. Từ gốc repo, tạo `integrations/long-v2/.env` theo file mẫu nếu chưa có, điền các khóa riêng trên máy. Giữ nguyên file cấu hình và project của hệ thống đang dùng.

```powershell
.\.venv\Scripts\python.exe scripts/start_personal.py
```

Lệnh dùng project `sejoy-stage1`, giữ dữ liệu và khởi động web **8001**, Automation **8000**, n8n **5678**, gateway **8080**. Khi chuyển từ bản Python sang Docker, dừng bản web Python trước để tránh trùng cổng. Không chạy `docker compose down -v`.

Để bật đường kết nối ngoài máy, đăng nhập ngrok, lấy **dev domain miễn phí thuộc tài khoản của bạn** và lưu authtoken tại máy. Trong `.env` Automation:

```dotenv
STUDIO_PUBLIC_URL=https://TEN-MIEN-CUA-BAN.ngrok-free.dev
TIKTOK_V2_REDIRECT_URI=https://TEN-MIEN-CUA-BAN.ngrok-free.dev/api/v2/tiktok/callback
NGROK_DOMAIN_CONFIRMED=1
NGROK_AUTHTOKEN=
TIKTOK_MEDIA_URL_VERIFIED=0
TIKTOK_SCHEDULER_ENABLED=0
TIKTOK_APP_AUDITED=0
```

Để trống `NGROK_AUTHTOKEN` nếu máy đã cấu hình bằng ngrok. Không thay khóa mã hóa TikTok đã có. Sau khi xác nhận tên miền, chạy:

```powershell
.\.venv\Scripts\python.exe scripts/start_personal.py --tunnel
```

Tunnel chỉ trỏ gateway **8080**, không mở thẳng **8001**. Trên Internet, gateway chỉ nhận callback TikTok, webhook Telegram, file xác minh, trang chính sách và MP4 có URL ký với hạn dùng. Trang chỉnh sửa, tài khoản và API nội dung chỉ truy cập trên máy.

Thông báo đầu trang Studio kiểm tra đường gateway thực tế. “Kết nối ngoài máy đang bật” chưa có nghĩa TikTok đã cấp quyền hoặc video đã được duyệt. Khi tunnel tắt, nội dung và lịch vẫn giữ nguyên; chạy lại lệnh trên, kiểm tra trạng thái rồi cập nhật kết quả. Không tạo lại lượt đăng khi chưa biết TikTok đã nhận hay chưa.

Gói ngrok miễn phí có hạn mức và tên miền phát triển cố định theo tài khoản. Không nâng cấp hoặc thêm thẻ để chạy nghiệm thu. [Giới hạn chính thức](https://ngrok.com/docs/pricing-limits/free-plan-limits).

## Tạo nội dung và video

1. **Bước 1:** chọn **Video thường** (mặc định) hoặc **Video TikTok Shop**, nhập thông tin thật/ghi rõ dữ liệu minh họa và tải ảnh.
2. **Bước 2–4:** duyệt tình huống, nhân vật, chế độ nói/thuyết minh và 4 hoặc 5 cảnh. Mỗi cảnh dự kiến 8 giây; duyệt cỡ cảnh, hành động và trạng thái đầu/cuối.
3. **Bước 5:** duyệt từng lời thoại. Video thường duyệt cả lời kết Cảnh 4. TikTok Shop dùng câu cố định của Bảo. AI không tự sửa câu đã duyệt.
4. **Bước 6:** chọn caption; kiểm tra slogan, hashtag, bình luận ghim và chữ khi dựng. Điểm ít nhất 8 và không có lỗi chặn mới được xuất.
5. **Bước 7:** tải ZIP, bấm **Sao chép bộ cảnh**. Trong Gemini bật **Tạo video**, chọn dọc **9:16**. Tiện ích **Chọn cảnh cho Gemini → Điền prompt** chỉ điền văn bản vào ô trống. Bạn đính kèm hai ảnh từ ZIP và tự bấm tạo khi còn lượt miễn phí.
6. Xem từng clip; nếu là clip riêng, ghép đúng thứ tự. Nếu là bản nối, kiểm tra không lặp cảnh. Đo thời lượng file thật; không coi 8 giây yêu cầu là kết quả đã đạt. Tải MP4 hoàn chỉnh tối đa **45 MB** vào đúng phiên và phát lại.
7. **Lưu nội dung vào Notion → Gửi video để duyệt trên Telegram → Cập nhật trạng thái duyệt.** Người duyệt xem và bấm quyết định trên đúng tin nhắn MP4.

Đổi loại nội dung: quay về Bước 1, chọn loại mới và lưu. Phiên tăng revision, các xác nhận phía sau bị hủy; MP4 cũ cần duyệt lại và lịch chưa gửi bị hủy. Nếu video đang gửi TikTok, hệ thống chặn chỉnh sửa cho đến khi đối chiếu kết quả.

Video TikTok Shop vẫn xuất được prompt và duyệt video, nhưng **chưa được đăng tự động**. Đổi caption ở màn hình đăng không biến một kịch bản Shop đã duyệt thành Video thường.

## Kết nối TikTok và đăng riêng tư

Ưu tiên ứng dụng Developer của dự án đang có. Người quản lý ứng dụng cần:

- Đăng ký callback v2 đúng tên miền đang chạy; giữ callback v1 nếu còn dùng.
- Kiểm tra Login Kit, `video.publish` và thêm tài khoản thử vào Sandbox nếu sử dụng Sandbox.
- Xác minh tên miền hoặc URL prefix `/media/tiktok/`. Đặt file do TikTok cấp trong `integrations/long-v2/verification/`, rồi xác nhận thành công trên Developer Portal.
- Sau xác minh thật mới đặt `TIKTOK_MEDIA_URL_VERIFIED=1`. Người dùng kết nối TikTok từ Studio và cấp quyền. Giữ `TIKTOK_APP_AUDITED=0` nếu chưa được audit; chỉ thử `SELF_ONLY`, tài khoản thử ở chế độ riêng tư.
- Khi đầy đủ và sẵn sàng gửi bài mới, bật `TIKTOK_SCHEDULER_ENABLED=1` rồi nạp lại Docker. Chỉ dùng một workflow **Publishing Scheduler v2**; không bật lịch/đăng/thử lại v1 cho cùng video.

Chọn **Đăng TikTok**, đồng bộ đúng MP4 đã duyệt, chọn tài khoản, caption, hashtag, quyền **Chỉ mình tôi** và các lựa chọn đăng. Xác nhận đã xem video và đồng ý gửi. Bấm **Đăng ngay** hoặc chọn ngày giờ Việt Nam rồi **Đặt lịch đăng**. Chỉ `PUBLISHED` với kết quả TikTok mới được coi là đã đăng; phải kiểm tra bài trên tài khoản. Notion là nơi đối chiếu, lỗi Notion không làm đăng lại.

Nghiệm thu cần **hai video được duyệt riêng**, một cho Đăng ngay và một cho Đặt lịch. Lưu mã lượt, hash MP4, thời gian, trạng thái TikTok và bằng chứng bài thật. Không thay kết quả này bằng kiểm thử giả lập. [Chi tiết và xử lý lỗi](TIKTOK_PUBLISHING_V2.md).

## Sao lưu và khôi phục

Trước khi dọn dữ liệu, dừng các dịch vụ ghi, sao lưu thư mục `STUDIO_DATA_HOST`, volume `sejoy-stage1_handoff_data`, volume `sejoy-stage1_n8n_data`, các `.env` và khóa mã hóa đang dùng. Lập danh sách file/SHA-256, kiểm tra bản sao rồi mới làm sạch.

Bản sao lưu đặt **ngoài repo và ngoài thư mục dữ liệu đang dùng**. Nó chứa dữ liệu cá nhân và khóa; không đưa lên GitHub. Khi cần khôi phục, dừng stack, kiểm tra checksum, khôi phục đồng bộ dữ liệu và khóa từ cùng mốc; không chỉ chép riêng SQLite khi dịch vụ đang chạy. Khởi động đúng project cũ và đối chiếu số phiên, ảnh/MP4, biên nhận và lịch trước khi bật bộ đăng. Không phục hồi SEJOY cũ để dùng cho nghiệm thu mới.

Đợt làm sạch ngày 18/11/2026 đã giữ bản sao lưu riêng. Không xóa các trang Notion, tin Telegram hoặc bài TikTok cũ ngoài máy. Xem [biên bản trạng thái hiện tại](TIKTOK_INTEGRATION_STATUS.md).
