# API và dữ liệu Content Studio v2

Xem [cách chạy web và duyệt nội dung](HANDOFF_CONTENT_STUDIO_V2.md) và [cấu hình Automation, Notion, Telegram](../integrations/long-v2/README.md).

Phiên, ảnh và lịch sử nằm trong `data/` hoặc thư mục `STUDIO_DATA_DIR`. Chạy một worker Uvicorn cho bản local và giữ web ở địa chỉ loopback. Bộ thử giao diện lưu dữ liệu riêng tại `data/browser-qa`.

AI thử tối đa ba lần model chính và hai lần model dự phòng cho lỗi tạm thời, với timeout 30 giây mỗi lần và ngân sách tổng 180 giây. Server kiểm tra lại JSON do model trả về bằng Pydantic và quy tắc nghiệp vụ. [Structured output của Gemini](https://ai.google.dev/gemini-api/docs/structured-output).

## API của Content Studio

API v1 `/generate`, `/status/{request_id}` và callback cũ giữ nguyên định dạng. `/app` là giao diện, `/docs` là OpenAPI.

| Endpoint | Mục đích |
|---|---|
| `GET /api/v2/characters` | Danh sách nhân vật và ảnh xem trước |
| `POST /api/v2/assets` | Tải ảnh bằng multipart field `file` |
| `POST /api/v2/sessions` | Tạo phiên từ `name`, `uses`, `price`, `product_link`, `asset_id` |
| `GET /api/v2/sessions` | Danh sách phiên |
| `GET /api/v2/sessions/{id}` | Toàn bộ trạng thái hiện tại |
| `GET /api/v2/sessions/{id}/history` | Lịch sử và bản chụp trước mỗi thao tác |
| `POST /api/v2/sessions/{id}/actions` | Sinh, duyệt, sửa, quay lại hoặc bàn giao |
| `GET /api/v2/sessions/{id}/export/{format}` | `json`, `markdown`, `notebook` hoặc `zip` sau Bước 6. `?revision=` đối chiếu revision bundle, trả 409 nếu đã thay đổi. |
| `POST /api/v2/sessions/{id}/videos` | Gắn MP4 vào bản prompt đã chốt. Multipart gồm `revision` của phiên và `file`. |
| `GET /api/v2/sessions/{id}/videos/{version}` | Phát MP4 đang gắn với bản prompt hiện tại. |

Mỗi thao tác gửi `revision` vừa đọc, `operation_id` duy nhất, `action` và `data`. API trả HTTP 202; đọc lại phiên để theo dõi trạng thái. Cùng mã thao tác/cùng body không chạy lại AI. Cùng mã nhưng khác body, phiên bản cũ hoặc phiên đang chạy tác vụ khác trả HTTP 409.

Các action:

- `generate`: sinh bản nháp của đúng bước hiện tại; Bước 4 nhận `data.scene_count` bằng 4 hoặc 5.
- `approve`: duyệt bước hiện tại. Bước 2 nhận `index` từ 0–3 hoặc `custom`; Bước 3 nhận `character_id`, `audio_mode` hoặc `new_character`; Bước 4 nhận `plan`; Bước 5 nhận `text`; Bước 6 nhận `publishing`.
- `revise`: sửa `product` ở Bước 1 hoặc sửa `draft` ở bước hiện tại, chưa chuyển bước.
- `reopen`: nhận `step` trước đó; ở Bước 5 có thể thêm `scene_id` để sửa một lời thoại. Các lời thoại sau được giữ thành bản nháp để duyệt lại.
- `handoff`: gửi đúng bộ nội dung đã chốt tới webhook v2. Chỉ báo nhận thành công nếu mã, phiên bản và SHA-256 trong biên nhận lưu vào Notion khớp.
- `submit_video_review`, `refresh_video_review`: gửi MP4 đang gắn vào hàng duyệt hoặc đọc quyết định Telegram. Cả hai nhận `data.version` của MP4. Tải MP4 riêng giữ trạng thái `ATTACHED` trên web. Khi Automation xác nhận nhận đúng tệp, web hiển thị `PENDING_REVIEW` hoặc quyết định đã có.

Phiên có `step`, `revision`, `status`, `draft`, `approved`, `scene_cursor`, `dialogues`, `validation`, `validation_details`, `warnings`. Kết quả `quality` gồm điểm, phản hồi, lỗi có bằng chứng và lời nhắc riêng. Trạng thái gồm `awaiting_input`, `awaiting_approval`, `processing`, `needs_changes`, `ready`, `error`. Lỗi bàn giao không xóa bộ prompt.

## Automation v2

| Endpoint | Mục đích |
|---|---|
| `POST /api/v2/content/ai-output` | Nhận nguyên bundle, lưu JSON và ghi Notion. |
| `GET /api/v2/content/{request_id}/revisions/{revision}` | Đọc JSON đã lưu và biên nhận. |
| `POST /api/v2/content/{request_id}/video-review` | Nhận multipart `revision` của bundle, `version` của MP4, `sha256` và `file`. Xác thực bằng `X-Content-Token`. |
| `GET /api/v2/content/{request_id}/video-review` | Đọc trạng thái theo `revision`, `version` và `sha256`. Xác thực bằng `X-Content-Token`. |
| `POST /api/v2/content/telegram-video-callback` | Nhận callback từ n8n với header `X-Telegram-Bot-Api-Secret-Token`. |

Hai bản contract tại `contracts/handoff_v2.py` và `integrations/long-v2/python-service/app/contracts_v2.py` phải giống nhau. Bundle có sản phẩm, nhân vật, metadata ảnh, cảnh và lời thoại, nội dung đăng, kết quả QC. Ảnh tham chiếu đi cùng ZIP.

Snapshot JSON và SQLite nằm trong Docker volume `handoff_data`. Notion lưu tóm tắt vào các cột và prompt đầy đủ dưới mục **Content Studio v2** trong trang. Prompt dài được chia thành nhiều block. [Giới hạn request của Notion](https://developers.notion.com/reference/request-limits).

Gửi lại nguyên bundle trả biên nhận cũ. Payload khác cùng revision và revision cũ hơn trả xung đột. Nếu ghi Notion dở dang, gửi lại nguyên bundle để tiếp tục. Chỉ nhận revision mới cho bản ghi `DRAFT` hoặc `FAILED`.

Lần tải MP4 đầu tiên tạo phiên bản `v1`. Upload cùng SHA-256 giữ nguyên bản. Gắn file khác tạo phiên bản mới ở web. Khi phiên bản mới được gửi duyệt, Automation từ chối callback trên tin nhắn cũ. Callback lặp cùng quyết định trả lại kết quả đã lưu.

## Kiểm thử

Dùng [lệnh chạy suite và công cụ đối chiếu](SEJOY_ACCEPTANCE_RUNBOOK.md#kiểm-thử-không-dùng-dữ-liệu-thật).
