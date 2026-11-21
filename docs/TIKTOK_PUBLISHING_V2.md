# Duyệt video, kết nối TikTok và lập lịch

Cách khởi động thống nhất và sao lưu: [Content Studio cá nhân](PERSONAL_STUDIO.md). Video thường từ quy trình 7 bước có thể đăng khi đủ quyền; Video TikTok Shop chỉ tạo/xuất/duyệt, chưa đăng tự động.

Content Studio dùng cá nhân trên máy, không cần tài khoản Studio, đăng ký hay mật khẩu. Kết nối TikTok qua OAuth và bộ xử lý lịch vẫn được giữ. MP4 phải được duyệt đúng phiên bản trước khi đăng. Người mới dùng duyệt trên web; dữ liệu dự án đã bàn giao Notion tiếp tục dùng quyết định Telegram.

**Trạng thái triển khai:** phần Automation của Long đã nằm trong `main` và được nối với giao diện v2. Ngày 21/11/2026 đã kết nối OAuth v2 bằng ứng dụng của dự án, hoàn tất cấu hình URL tải MP4 và đăng thử riêng tư thành công bằng video tải sẵn. Tiến độ lượt đặt lịch và bằng chứng đối chiếu xem [biên bản tích hợp](TIKTOK_INTEGRATION_STATUS.md). Chưa tích hợp TikTok Shop; không dùng clip có lời kêu gọi giỏ hàng cho luồng video thường.

## 1. Dùng trên giao diện

1. Mở http://127.0.0.1:8001/app và dùng ngay. Các phiên, ảnh, ZIP, MP4, chat và lịch được lưu trên máy này. Trang đăng nhập/tài khoản cũ tự quay về ứng dụng.
2. Với phiên ở Bước 7, tải MP4 lên rồi bấm **Duyệt và chuẩn bị đăng TikTok**. Bấm **Kiểm tra và đồng bộ MP4**; xem hết video. Phiên SEJOY đã gửi Telegram dùng quyết định từ đúng tin duyệt. Phiên khác có nút **Duyệt video này** / **Video cần sửa** trên web.
3. Với video thường đã hoàn chỉnh, mở **Lịch đăng và TikTok**, nhập caption và **Tải video thường lên**. Video này được quản lý riêng; không sửa kịch bản SEJOY. Có thể mở lại video đã tải trong danh sách này.
4. Bấm **Kết nối tài khoản TikTok**. TikTok hỏi quyền; Content Studio không hỏi mật khẩu TikTok. Sau khi quay về, chọn đúng tài khoản, đọc tên và thời lượng được phép.
5. Kiểm tra caption/hashtag, tự chọn quyền riêng tư. Bình luận/Duet/Stitch mặc định tắt. Khai báo quảng bá thương hiệu và nhãn AI phù hợp với clip. Xác nhận đã xem, quyền sử dụng âm thanh và việc gửi đăng.
6. Bấm **Đăng ngay**, hoặc chọn ngày giờ **Việt Nam UTC+7** rồi **Đặt lịch đăng**. Máy chủ phải bật và có mạng. Đây là giờ bắt đầu gửi; TikTok có thể cần thêm thời gian xử lý.
7. Bấm **Cập nhật kết quả**. Chỉ trạng thái `PUBLISHED` từ TikTok mới được hiển thị là đã đăng. Bài riêng tư có thể không có mã/link công khai.

MP4 tối đa 45 MB, có hình H.264 và thời lượng đọc được. Thay MP4 hoặc mở kịch bản để sửa sẽ hủy lịch chưa gửi và yêu cầu duyệt lại. Khi đang gửi hoặc chưa biết TikTok đã nhận chưa, phần mềm chặn thay bản đó.

Mục **Tài khoản TikTok** hiển thị từng điều kiện còn thiếu, cách hoàn tất và trạng thái chưa kết nối tài khoản. Có thể kết nối TikTok khi cấu hình đăng nhập đã đủ, trước khi xác minh tên miền MP4; nút đăng vẫn bị chặn cho tới khi đủ điều kiện và bật bộ xử lý. Dấu “đã cấu hình” chỉ xác nhận thiết lập trên máy, không thay cho xác nhận quyền từ TikTok. Lỗi gửi API giữ nguyên caption đang sửa và mã yêu cầu để thử lại không tạo lịch trùng.

## 2. Chạy trên máy và Docker

Không mua gói dịch vụ trong quy trình này. Giao diện chỉ mở trên localhost; HTTPS chỉ dành cho callback TikTok, MP4 có liên kết ký và webhook Telegram. Các cổng vẫn là web **8001**, Automation **8000**, n8n **5678**; gateway công khai mới **8080**. Cổng Docker chỉ bind `127.0.0.1`.

Từ gốc repo, cài môi trường theo README. Trong `.env`, dùng `STUDIO_AUTH_ENABLED=0`, `STUDIO_LOCAL_ONLY=1`, `STUDIO_PUBLIC_MODE=0`. Mở `/app` trực tiếp trên localhost. Không có bước tạo quản trị. Không dùng cấu hình này để mở giao diện chỉnh sửa cho người ngoài qua Internet.

Muốn chạy cả web trong Docker, từ `integrations/long-v2`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Điền WEBHOOK_V2_TOKEN ngẫu nhiên, dùng chung cho web, Automation và n8n.
# Điền STUDIO_DATA_HOST nếu tái sử dụng dữ liệu đã có; sao lưu trước khi đổi nơi chạy.
docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build
```

Chỉ chạy một bản web ghi vào cùng database. Dừng bản Python ở cổng 8001 trước khi chuyển sang container. Giữ **cùng tên project Compose và volume** khi nâng cấp hệ thống cũ. Không chạy `down -v`. Ảnh có đường dẫn Windows cũ được đọc từ thư mục `assets` cùng volume khi chạy Linux; không thay bundle/hash.

`docker-compose.public.yml` chạy Studio cá nhân tại 8001. Gateway 8080 chỉ cho `/api/v2/tiktok/callback`, `/media/tiktok/`, file xác minh `tiktok*.txt`, `/policy` và webhook Telegram v2. `/app`, trang tài khoản và các API chỉnh sửa bị chặn trên gateway; n8n và API nội bộ không mở ra Internet. Dùng cùng tên miền ngrok qua gateway 8080 cho Telegram. Chỉ ngừng đường cũ sau khi webhook mới được kiểm tra; không mở hai tunnel mới.

## 3. Dùng lại ứng dụng TikTok của dự án

Kiểm tra ứng dụng Long đã dùng trước; không cần tạo một ứng dụng Developer khác chỉ vì đổi giao diện sang Content Studio. Người quản lý ứng dụng xác nhận đúng dự án, quyền sử dụng, Login Kit, Direct Post và `video.publish`. Dùng cặp `TIKTOK_CLIENT_KEY`/`TIKTOK_CLIENT_SECRET` của ứng dụng đó trong `.env` của Automation; không ghi khóa vào source hay chat. Giữ cấu hình v1 còn sử dụng. Không sao chép token tài khoản dùng chung từ bảng Notion v1 vào các kết nối mới: chủ tài khoản tự cấp quyền qua OAuth v2.

Chỉ xem xét ứng dụng mới nếu ứng dụng hiện có không thể dùng cho dự án. Việc có source hoặc khóa không chứng minh ứng dụng đã được audit. Khi triển khai Direct Post công khai, ứng dụng cần đáp ứng yêu cầu dành cho nhiều người dùng, không chỉ công cụ nội bộ. [Hướng dẫn chính thức](https://developers.tiktok.com/docs/en/content-sharing-guidelines).

1. Dùng tên miền HTTPS cố định của gói miễn phí đang có, trỏ tunnel tới gateway **8080**. Ví dụ `ngrok http 8080 --url=TEN-MIEN-MIEN-PHI-CUA-BAN`. Không đăng ký gói trả phí. Kiểm tra hạn mức gói; nếu hết, dừng và thử lại sau.
2. Điền `STUDIO_PUBLIC_URL=https://...` không có đường dẫn; `TIKTOK_V2_REDIRECT_URI` phải đúng URL đó cộng `/api/v2/tiktok/callback`. Thêm chính xác callback này trong cùng ứng dụng TikTok, giữ callback v1 nếu còn dùng. Đặt cùng URL cho web/Automation. Callback trả liên kết về ứng dụng trên localhost. Không dùng link HTTPS để mở giao diện Studio.
3. Giữ khóa Fernet `TIKTOK_TOKEN_ENCRYPTION_KEY` đã có. Chỉ khi chưa có khóa mã hóa và chưa lưu kết nối nào mới tạo bằng lệnh dưới; lưu cùng bản sao lưu, không thay khóa đang dùng:

```powershell
# Chạy từ gốc repo; lệnh hiển thị khóa mới chỉ trên terminal của bạn.
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Xác minh quyền sở hữu tên miền hoặc URL prefix `/media/tiktok/` trong TikTok Developer. Nếu TikTok cấp file xác minh, đặt vào `integrations/long-v2/verification/`; gateway chỉ phục vụ `tiktok*.txt`. Chỉ đặt `TIKTOK_MEDIA_URL_VERIFIED=1` **sau khi xác minh thật**.
5. Xác nhận ứng dụng có `video.publish` và tài khoản vừa kết nối cấp quyền đó; nếu thiếu, hoàn tất quyền trong ứng dụng hiện có. Giữ `TIKTOK_APP_AUDITED=0` khi chưa được audit: UI chỉ cho `SELF_ONLY`, tài khoản thử phải ở chế độ riêng tư. Sau khi đủ điều kiện và sẵn sàng chạy lịch, đặt `TIKTOK_SCHEDULER_ENABLED=1`, khởi động lại dịch vụ. Không đổi cờ audit để vượt hạn chế. [Direct Post API](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post).

Kiểm tra cấu hình từ gốc repo bằng `python scripts/check_tiktok_setup.py`. Có thể chỉ định `--env-file` để kiểm tra một file được bàn giao. Lệnh chỉ đọc file, không gọi TikTok, không in giá trị khóa và không sửa cấu hình. Mã thoát `1` nghĩa là cấu hình gửi video chưa đủ; kết quả cũng nêu riêng khả năng kết nối tài khoản và trạng thái bộ xử lý. Sau khi sửa `.env`, nạp lại đúng stack Docker đang dùng rồi mở lại mục TikTok để đọc trạng thái thực tế trong dịch vụ.

Video trên máy chủ được TikTok lấy bằng `PULL_FROM_URL` qua URL ký ngẫu nhiên, có hạn hai giờ, không redirect. Không trả token hoặc đường dẫn file nội bộ cho trình duyệt. Không mở URL media công khai lâu dài.

## 4. Bật lịch trong n8n

Import [Content Studio - Publishing Scheduler v2](../integrations/long-v2/n8n/Content%20Studio%20-%20Publishing%20Scheduler%20v2.json). Trong node **Process owned schedules**, chọn Header Auth với tên header `X-Content-Token`, giá trị bằng `WEBHOOK_V2_TOKEN`. Lưu credential trong n8n rồi bật workflow. Workflow chạy mỗi phút, gọi API nội bộ; không có khóa trong file JSON.

Không bật lại các workflow lập lịch/đăng/retry **v1** cho cùng dữ liệu v2. V2 dùng `publications.sqlite3` trong volume Automation; Notion là bản đối chiếu nội dung và kết quả, không phải hàng đợi chính. Workflow cũ vẫn giữ trong source để tương thích các hệ thống v1 riêng.

Đặt `TIKTOK_SCHEDULER_ENABLED=0` sẽ dừng gửi bài mới. Giữ workflow v2 chạy để tiếp tục đọc kết quả những bài TikTok đã nhận và thử lại đồng bộ Notion. Một workflow chạy thành công khi bộ xử lý tắt không phải bằng chứng đã đăng bài. Lịch lỗi có lượt thay thế không được bật lại để tạo hai bài cùng video/tài khoản.

| Trạng thái | Ý nghĩa / cách xử lý |
|---|---|
| QUEUED / SCHEDULED | Chờ xử lý; có thể hủy hoặc đổi giờ. |
| INITIATING / PROCESSING | Đang gửi / TikTok đang xử lý; không đổi video, không tạo lại lượt gửi. |
| MISSED | Trễ hơn 15 phút; chọn lại giờ. Trễ trong 15 phút mới được tự tiếp tục. |
| BLOCKED | Chưa gửi được vì video, quyền hoặc cấu hình không còn hợp lệ; sửa nguyên nhân rồi xác nhận giờ mới. |
| RECONCILE | Mất kết nối/khởi động lại khi bắt đầu gửi; cần đối chiếu TikTok, không tự retry. Giữ dữ liệu để kiểm tra; chưa có nút “bỏ qua” tạo đăng trùng. |
| FAILED | TikTok xác nhận thất bại; kiểm tra nguyên nhân, tạo lượt mới sau khi xem lại. |
| PUBLISHED | TikTok xác nhận đăng xong. Không suy luận từ thông báo upload thành công. |

Nếu gặp `unaudited_client_can_only_post_to_private_accounts`, **cả tài khoản TikTok phải ở chế độ riêng tư** tại thời điểm đăng; chỉ chọn **Chỉ mình tôi** cho video chưa đủ. Trong ứng dụng TikTok, vào **Hồ sơ → ☰ → Cài đặt và quyền riêng tư → Quyền riêng tư → Tài khoản riêng tư**. Người dùng tự thay đổi vì lựa chọn này ảnh hưởng toàn bộ tài khoản; có thể dùng tài khoản thử riêng nếu muốn giữ tài khoản chính công khai. Sau khi xử lý, đổi giờ của lượt đang `BLOCKED` để thử lại; không bấm tạo thêm lượt giống nhau. [Quy định ứng dụng chưa audit](https://developers.tiktok.com/docs/en/content-sharing-guidelines).

Token TikTok được mã hóa theo tài khoản. OAuth state có hạn và dùng một lần. Mỗi lượt có mã thao tác và lưu đúng video/hash, revision, tài khoản, caption/hashtag và lựa chọn đăng. Gửi lại cùng yêu cầu trả cùng bản ghi. Khi có `publish_id`, chỉ đọc trạng thái của mã đó. Lỗi đồng bộ Notion không gửi lại TikTok.

## 5. Kiểm thử và nghiệm thu còn lại

Chạy `python scripts/verify.py` trong môi trường đã cài requirements-test. Kiểm thử gồm cô lập hai tài khoản, CSRF, khôi phục một lần, quyền trên ảnh/ZIP/chat/video, OAuth/đăng giả lập, lịch UTC+7, trễ lịch, hủy khi đổi video, token mã hóa, trạng thái TikTok, URL media hết hạn và không gửi trùng sau lỗi mơ hồ.

Nghiệm thu thật sau khi đủ quyền: dùng MP4 tổng hợp không có yêu cầu giỏ hàng, kết nối tài khoản thử riêng tư; một lượt **Đăng ngay** và một lượt **Đặt lịch**. Lưu biên nhận thực tế, trạng thái cuối và mã bài nếu TikTok trả. Thử khởi động lại dịch vụ để đọc lại lịch. Không đánh dấu hoàn thành nghiệm thu chỉ vì kiểm thử giả lập đạt.

Bản này dành cho một máy và không có đăng ký công khai. Sao lưu cả dữ liệu Studio, volume Automation/n8n và cấu hình riêng trước khi làm sạch dữ liệu. Giữ các khóa dịch vụ, khóa mã hóa, workflow và credential n8n. Bản sao lưu nằm ngoài thư mục dữ liệu đang dùng và ngoài Git. Làm sạch trên máy không xóa trang Notion, tin Telegram hoặc bài TikTok đã có. Sau khi làm sạch, tạo phiên mới và duyệt lại video trước khi đăng.
