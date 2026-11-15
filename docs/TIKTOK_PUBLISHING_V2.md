# Duyệt video, kết nối TikTok và lập lịch

Content Studio có tài khoản riêng, đăng nhập bằng mật khẩu, kết nối TikTok qua OAuth và bộ xử lý lịch lưu bền vững. MP4 phải được duyệt đúng phiên bản trước khi đăng. Người mới dùng duyệt trên web; dữ liệu dự án đã bàn giao Notion tiếp tục dùng quyết định Telegram.

**Trạng thái triển khai:** mã nguồn và kiểm thử giả lập đã có. Chủ dự án chưa có ứng dụng TikTok Developer được xác nhận quyền `video.publish`, nên chưa nghiệm thu OAuth hoặc đăng thật. Không có mã bài thử được tạo giả. Chưa tích hợp TikTok Shop. Bản SEJOY r26 có lời kêu gọi giỏ hàng vẫn được giữ để đối chiếu, không tự đăng bản đó qua luồng video thường.

## 1. Dùng trên giao diện

1. Đăng nhập. Mỗi người chỉ thấy phiên, ảnh, ZIP, MP4, chat, tài khoản TikTok và lịch của mình.
2. Với phiên ở Bước 7, tải MP4 lên rồi bấm **Duyệt và chuẩn bị đăng TikTok**. Bấm **Kiểm tra và đồng bộ MP4**; xem hết video. Phiên SEJOY đã gửi Telegram dùng quyết định từ đúng tin duyệt. Phiên khác có nút **Duyệt video này** / **Video cần sửa** trên web.
3. Với video thường đã hoàn chỉnh, mở **Lịch đăng và TikTok**, nhập caption và **Tải video thường lên**. Video này được quản lý riêng; không sửa kịch bản SEJOY. Có thể mở lại video đã tải trong danh sách này.
4. Bấm **Kết nối tài khoản TikTok**. TikTok hỏi quyền; Content Studio không hỏi mật khẩu TikTok. Sau khi quay về, chọn đúng tài khoản, đọc tên và thời lượng được phép.
5. Kiểm tra caption/hashtag, tự chọn quyền riêng tư. Bình luận/Duet/Stitch mặc định tắt. Khai báo quảng bá thương hiệu và nhãn AI phù hợp với clip. Xác nhận đã xem, quyền sử dụng âm thanh và việc gửi đăng.
6. Bấm **Đăng ngay**, hoặc chọn ngày giờ **Việt Nam UTC+7** rồi **Đặt lịch đăng**. Máy chủ phải bật và có mạng. Đây là giờ bắt đầu gửi; TikTok có thể cần thêm thời gian xử lý.
7. Bấm **Cập nhật kết quả**. Chỉ trạng thái `PUBLISHED` từ TikTok mới được hiển thị là đã đăng. Bài riêng tư có thể không có mã/link công khai.

MP4 tối đa 45 MB, có hình H.264 và thời lượng đọc được. Thay MP4 hoặc mở kịch bản để sửa sẽ hủy lịch chưa gửi và yêu cầu duyệt lại. Khi đang gửi hoặc chưa biết TikTok đã nhận chưa, phần mềm chặn thay bản đó.

## 2. Chạy trên máy và Docker

Không mua gói dịch vụ trong quy trình này. Bắt đầu bằng localhost; chỉ mở HTTPS sau khi cấu hình bảo mật và tài khoản quản trị. Các cổng vẫn là web **8001**, Automation **8000**, n8n **5678**; gateway công khai mới **8080**. Cổng Docker chỉ bind `127.0.0.1`.

Từ gốc repo, cài môi trường theo README. Trong `.env`, đặt `STUDIO_AUTH_ENABLED=1`, khởi động web rồi mở `/login` **trực tiếp trên localhost**. Tài khoản đầu là quản trị và nhận quyền sở hữu dữ liệu cũ, không viết lại JSON/bundle đã duyệt. Lưu mã khôi phục ở nơi riêng. Người dùng tiếp theo dùng Đăng ký; mã khôi phục chỉ dùng một lần và đổi sau khi khôi phục. Trang **Tài khoản** cho đổi mật khẩu, xóa dữ liệu tài khoản thường; tài khoản quản trị dự án phải chuyển giao riêng trước khi xóa.

Muốn chạy cả web trong Docker, từ `integrations/long-v2`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Điền WEBHOOK_V2_TOKEN ngẫu nhiên, dùng chung cho web, Automation và n8n.
# Điền STUDIO_DATA_HOST nếu tái sử dụng dữ liệu đã có; sao lưu trước khi đổi nơi chạy.
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build
```

Chỉ chạy một bản web ghi vào cùng database. Dừng bản Python ở cổng 8001 trước khi chuyển sang container. Giữ **cùng tên project Compose và volume** khi nâng cấp hệ thống cũ. Không chạy `down -v`. Ảnh có đường dẫn Windows cũ được đọc từ thư mục `assets` cùng volume khi chạy Linux; không thay bundle/hash.

`docker-compose.public.yml` bật đăng nhập, chặn API v1 trên public web. Thiết lập quản trị chỉ qua cổng localhost 8001; gateway chặn `/api/v2/auth/setup`. n8n và API nội bộ không mở ra Internet. Có thể tiếp tục gateway webhook cũ ở 5679 cho Telegram.

## 3. Cấu hình TikTok Developer khi sẵn sàng

Bạn **chưa cần gửi khóa trong chat**. Tạo tài khoản Developer, ứng dụng web hướng tới người dùng bên ngoài, thêm Login Kit và Content Posting API/Direct Post. Đây là điều kiện để thử đăng thật, không phải cam kết được TikTok xét duyệt. Công cụ chỉ phục vụ tài khoản nội bộ của nhóm không phù hợp hướng dẫn Direct Post. [Hướng dẫn chính thức](https://developers.tiktok.com/docs/en/content-sharing-guidelines).

1. Dùng tên miền HTTPS cố định của gói miễn phí đang có, trỏ tunnel tới gateway **8080**. Ví dụ `ngrok http 8080 --url=TEN-MIEN-MIEN-PHI-CUA-BAN`. Không đăng ký gói trả phí. Kiểm tra hạn mức gói; nếu hết, dừng và thử lại sau.
2. Điền `STUDIO_PUBLIC_URL=https://...` không có đường dẫn; `TIKTOK_V2_REDIRECT_URI` phải đúng URL đó cộng `/api/v2/tiktok/callback`. Đặt cùng URL cho web/Automation. Khai báo chính sách `/policy` và địa chỉ hỗ trợ `STUDIO_SUPPORT_CONTACT` trước khi mở đăng ký công khai.
3. Điền `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` trong `.env` của Automation. Tạo khóa Fernet cho `TIKTOK_TOKEN_ENCRYPTION_KEY` bằng lệnh dưới; giữ khóa này cùng bản sao lưu, không đổi tùy tiện:

```powershell
# Chạy từ gốc repo; lệnh hiển thị khóa mới chỉ trên terminal của bạn.
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Xác minh quyền sở hữu tên miền hoặc URL prefix `/media/tiktok/` trong TikTok Developer. Nếu TikTok cấp file xác minh, đặt vào `integrations/long-v2/verification/`; gateway chỉ phục vụ `tiktok*.txt`. Chỉ đặt `TIKTOK_MEDIA_URL_VERIFIED=1` **sau khi xác minh thật**.
5. Xin quyền `video.publish`. Giữ `TIKTOK_APP_AUDITED=0` khi chưa được audit: UI chỉ cho `SELF_ONLY`, tài khoản thử phải ở chế độ riêng tư. Sau khi đủ điều kiện và sẵn sàng chạy lịch, đặt `TIKTOK_SCHEDULER_ENABLED=1`, khởi động lại dịch vụ. Không đổi cờ audit để vượt hạn chế. [Direct Post API](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post).

Video trên máy chủ được TikTok lấy bằng `PULL_FROM_URL` qua URL ký ngẫu nhiên, có hạn hai giờ, không redirect. Không trả token hoặc đường dẫn file nội bộ cho trình duyệt. Không mở URL media công khai lâu dài.

## 4. Bật lịch trong n8n

Import [Content Studio - Publishing Scheduler v2](../integrations/long-v2/n8n/Content%20Studio%20-%20Publishing%20Scheduler%20v2.json). Trong node **Process owned schedules**, chọn Header Auth với tên header `X-Content-Token`, giá trị bằng `WEBHOOK_V2_TOKEN`. Lưu credential trong n8n rồi bật workflow. Workflow chạy mỗi phút, gọi API nội bộ; không có khóa trong file JSON.

Không bật lại các workflow lập lịch/đăng/retry **v1** cho cùng dữ liệu v2. V2 dùng `publications.sqlite3` trong volume Automation; Notion là bản đối chiếu của SEJOY, không phải hàng đợi chính. Workflow cũ vẫn giữ trong source để tương thích các hệ thống v1 riêng.

| Trạng thái | Ý nghĩa / cách xử lý |
|---|---|
| QUEUED / SCHEDULED | Chờ xử lý; có thể hủy hoặc đổi giờ. |
| INITIATING / PROCESSING | Đang gửi / TikTok đang xử lý; không đổi video, không tạo lại lượt gửi. |
| MISSED | Trễ hơn 15 phút; chọn lại giờ. Trễ trong 15 phút mới được tự tiếp tục. |
| BLOCKED | Chưa gửi được vì video, quyền hoặc cấu hình không còn hợp lệ; sửa nguyên nhân rồi xác nhận giờ mới. |
| RECONCILE | Mất kết nối/khởi động lại khi bắt đầu gửi; cần đối chiếu TikTok, không tự retry. Giữ dữ liệu để kiểm tra; chưa có nút “bỏ qua” tạo đăng trùng. |
| FAILED | TikTok xác nhận thất bại; kiểm tra nguyên nhân, tạo lượt mới sau khi xem lại. |
| PUBLISHED | TikTok xác nhận đăng xong. Không suy luận từ thông báo upload thành công. |

Token TikTok được mã hóa theo tài khoản. OAuth state có hạn và dùng một lần. Mỗi lượt có mã thao tác và lưu đúng video/hash, revision, tài khoản, caption/hashtag và lựa chọn đăng. Gửi lại cùng yêu cầu trả cùng bản ghi. Khi có `publish_id`, chỉ đọc trạng thái của mã đó. Lỗi đồng bộ Notion không gửi lại TikTok.

## 5. Kiểm thử và nghiệm thu còn lại

Chạy `python scripts/verify.py` trong môi trường đã cài requirements-test. Kiểm thử gồm cô lập hai tài khoản, CSRF, khôi phục một lần, quyền trên ảnh/ZIP/chat/video, OAuth/đăng giả lập, lịch UTC+7, trễ lịch, hủy khi đổi video, token mã hóa, trạng thái TikTok, URL media hết hạn và không gửi trùng sau lỗi mơ hồ.

Nghiệm thu thật sau khi đủ quyền: dùng MP4 tổng hợp không có yêu cầu giỏ hàng, kết nối tài khoản thử riêng tư; một lượt **Đăng ngay** và một lượt **Đặt lịch**. Lưu biên nhận thực tế, trạng thái cuối và mã bài nếu TikTok trả. Thử khởi động lại dịch vụ để đọc lại lịch. Không đánh dấu hoàn thành nghiệm thu chỉ vì kiểm thử giả lập đạt.

Trước khi mở cho nhiều người: kiểm tra HTTPS, đăng ký/đăng nhập/khôi phục/xóa dữ liệu, địa chỉ hỗ trợ, giới hạn dung lượng và sao lưu **cả** dữ liệu Studio, volume Automation/n8n và khóa mã hóa. Người quản lý kiểm soát quyền truy cập máy chủ; xóa tài khoản không xóa bài đã đăng TikTok hoặc bản sao lưu quản trị trước đó. Chưa có giới hạn tổng dung lượng từng người, nên triển khai theo nhóm thử nhỏ trong giai đoạn nghiệm thu.
