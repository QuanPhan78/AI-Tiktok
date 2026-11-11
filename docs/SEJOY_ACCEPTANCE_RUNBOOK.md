# Nghiệm thu Content Studio v2 với SEJOY

Ngày 11/11/2026, phiên SEJOY đã đi qua các mốc dưới đây trên môi trường thử. Repo chứa source và hướng dẫn tái hiện. Gói prompt, MP4 và biên nhận thật lưu riêng với dữ liệu dự án.

| Mốc | Kết quả đã ghi nhận |
|---|---|
| Nội dung đã chốt | Prompt revision 26, bốn cảnh, QC Gemini 9/10, ZIP đủ hai ảnh tham chiếu. |
| Bàn giao Notion | Database thử có một bản `DRAFT`. Prompt đầy đủ và JSON đọc lại khớp biên nhận, kể cả sau khi restart. |
| Video | Gemini trả bản nối bốn cảnh dọc 720 × 1280, dài 40,04 giây. MP4 v1 phát được tại Bước 7. |
| Duyệt video | Bot v2 gửi đúng MP4 v1. Người duyệt bấm nút trong Telegram, Notion và Content Studio cùng hiện `APPROVED`. |
| Đăng TikTok | Đã bàn giao file, caption và hashtag để chủ tài khoản chọn cách đăng. Chưa có link bài đăng trong nghiệm thu này. |

## Chạy lại với một phiên thử

1. Tạo phiên với ảnh và thông tin sản phẩm đã xác nhận. Duyệt đủ bảy bước theo [hướng dẫn sử dụng](HANDOFF_CONTENT_STUDIO_V2.md).
2. Gửi bundle vào database Notion thử. Kiểm tra bản `DRAFT`, gửi lại cùng bundle và đối chiếu biên nhận. Giữ volume khi restart.
3. Tạo MP4, gắn tại Bước 7 rồi gửi vào nhóm Telegram thử. Kiểm tra `PENDING_REVIEW`. Bấm **Duyệt video** hoặc **Cần sửa**, sau đó bấm **Đọc trạng thái duyệt** ở web.
4. Để thử nút cũ, dùng một phiên thử riêng. Gắn và gửi MP4 v2 có nội dung khác MP4 v1. Bấm nút ở tin nhắn v1 để xác nhận bị từ chối. Tiếp tục bấm nút của v2 và đối chiếu đúng quyết định trong Notion và web.

## Đối chiếu bản bàn giao

Lấy `handoff.json` từ ZIP. Lưu phản hồi n8n nguyên vẹn thành `receipt.json`. Nếu đọc từ API phiên, bọc `session.handoff` thành `{"success":true,"data":...}`. Lưu kết quả `GET /api/v2/content/{request_id}/revisions/{revision}` thành `readback.json`, với revision trong bundle.

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py compare --bundle handoff.json --receipt receipt.json --readback readback.json --database-id ID_DATABASE_THU --zip goi-da-duyet.zip
```

Lệnh kiểm tra mã yêu cầu, revision, database đích, JSON đầy đủ, SHA-256, prompt Markdown và hai ảnh. So lại sau khi restart Automation.

## Kiểm thử không dùng dữ liệu thật

Từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest tests.test_qc_results tests.test_studio_v2 tests.test_gateway_v2 tests.test_handoff_v2 tests.test_acceptance_tools tests.test_policy_validator tests.test_pipeline_kb_integration tests.test_webhook_integration tests.test_video_review_v2 -q
```

Bộ test dùng dữ liệu giả lập cho bước AI, nhận bundle, Notion, Telegram và các tình huống gửi trùng hoặc bấm nút duyệt bản cũ. Test live nằm riêng trong `tests/test_live_e2e_pipeline.py`.
