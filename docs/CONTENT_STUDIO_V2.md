# Content Studio v2

Ứng dụng chuẩn bị bộ prompt theo quy trình của Bảo, có người duyệt từng bước. Web chưa tạo video, chưa dựng MP4 và chưa đăng TikTok. Chốt prompt chỉ cho phép bàn giao nội dung; không thay thế duyệt video.

## Chạy trên máy Quân

Khuyến nghị Python 3.12 hoặc 3.13. Máy hiện tại chạy được các kiểm thử trên Python 3.14, nhưng thư viện LangChain còn phát cảnh báo tương thích Pydantic V1.

```powershell
cd AI-Tiktok
python -m pip install -r requirements.txt
python run_server.py
```

Mở [Content Studio](http://127.0.0.1:8001/app). Dùng `.env` hiện có, hoặc tạo từ `.env.example` nếu chưa có. Không ghi đè `.env` đã chứa cấu hình. Các biến mới có mặc định trong code:

```dotenv
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
PORT=8001
HOST=127.0.0.1
ENABLE_NGROK=0
WEBHOOK_V2_URL=http://127.0.0.1:5678/webhook/ai-agent-callback-v2
# Điền giá trị bí mật trùng n8n Header Auth
WEBHOOK_V2_TOKEN=
```

`GEMINI_API_KEY` chỉ lưu phía server. Chọn model mà tài khoản API thực sự có quyền dùng. Web không có chế độ giả vờ AI thành công nếu thiếu khóa, hết hạn mức hoặc model không khả dụng.

Studio giới hạn retry ở một tầng: tối đa 3 lần model chính, 2 lần model dự phòng cho lỗi tạm thời; timeout 30 giây/lần và tổng 180 giây. Model thực dùng được lưu theo bước trong metadata; model dự phòng không viết lại phần đã duyệt.

Phiên, ảnh tải lên và lịch sử được lưu dưới `data/` (hoặc `STUDIO_DATA_DIR`); không đưa lên Git. Chạy một worker Uvicorn cho bản local. Không mở web này ra Internet vì bản này chưa có đăng nhập hay phân quyền nhiều người.

## Quy trình sử dụng

1. Tạo phiên bằng tên, công dụng đã xác nhận, giá và link; tải ảnh sản phẩm. Có thể bổ sung/thay ảnh bằng phần sửa thông tin ở Bước 1.
2. Mỗi bước bấm **Tạo bản nháp**, kiểm tra và duyệt. Các bước sau chỉ mở khi bước trước được duyệt.
3. Chọn một trong tám nhân vật có ảnh; hoặc tạo NV9 trở lên, cung cấp ảnh và khối nhân vật tiếng Anh có `[PRODUCT]`. Chọn nhân vật nói hoặc thuyết minh riêng khi dựng.
4. Chọn 4 cảnh hoặc tách thành 5 cảnh. Duyệt hành động và mô tả dùng để lắp prompt.
5. Duyệt riêng từng lời thoại. Cảnh cuối giữ nguyên câu cố định. Hệ thống không tự sửa lời thoại đã chốt khi kiểm tra QC.
6. Kiểm tra hai bảng tổng hợp, chọn caption, rồi **Chốt và xuất prompt**. Lỗi cấu trúc/nội dung/ảnh sẽ chặn xuất; cảnh báo nhịp nói không có nghĩa đã đo thời lượng bằng clip thật.
7. Tải JSON, Markdown hoặc ZIP. ZIP chứa `handoff.json`, `prompts.md`, ảnh sản phẩm `product.*` và ảnh nhân vật `character.*`; metadata JSON lưu tên gốc và SHA-256 để đối chiếu.

Nhấp bước trước để sửa. Xác nhận ở các bước phụ thuộc phía sau bị hủy; lịch sử vẫn giữ. Tải lại trang hoặc đóng rồi mở lại có thể tiếp tục phiên. Nếu server dừng giữa tác vụ, phiên hiển thị lỗi gián đoạn để thử lại bằng thao tác mới.

Ở Bước 6, kết quả QC hiện ngay trên nút chốt và màn hình tự cuộn tới kết quả. Điểm từ 8/10,
không còn lỗi chặn và dữ liệu hợp lệ mới được xuất. Lỗi nội dung từ AI phải có trường/cảnh,
trích đoạn nguyên văn và lý do; trích đoạn không khớp được báo là QC chưa hợp lệ. Góp ý phong cách,
độ dài và lời nhắc chung nằm trong cảnh báo, không tự chặn xuất. Câu chốt cố định không bị sửa vì
phong cách hoặc độ dài; vẫn phải kiểm tra nhịp nói trên clip thật.

Giá dùng khi dựng và URL nguồn được server kiểm tra nguyên văn, không bị đánh giá nhầm thành lời thoại.
Phần chữ bình luận ghim ngoài URL vẫn được kiểm tra. QC hoặc API lỗi không xóa bản sửa nội dung đăng
bài vừa gửi; lời thoại và các bước đã duyệt không bị AI viết lại. Bước 7 hiển thị nút tải ZIP, JSON, Markdown.

## API của Quân

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
| `GET /api/v2/sessions/{id}/export/{format}` | `json`, `markdown` hoặc `zip` sau Bước 6 |

Mỗi thao tác gửi `revision` vừa đọc, `operation_id` duy nhất, `action` và `data`. API trả HTTP 202; đọc lại phiên để theo dõi trạng thái. Cùng mã thao tác/cùng body không chạy lại AI. Cùng mã nhưng khác body, phiên bản cũ hoặc phiên đang chạy tác vụ khác trả HTTP 409.

Các action:

- `generate`: sinh bản nháp của đúng bước hiện tại; Bước 4 nhận `data.scene_count` bằng 4 hoặc 5.
- `approve`: duyệt bước hiện tại. Bước 2 nhận `index` từ 0–3 hoặc `custom`; Bước 3 nhận `character_id`, `audio_mode` hoặc `new_character`; Bước 4 nhận `plan`; Bước 5 nhận `text`; Bước 6 nhận `publishing`.
- `revise`: sửa `product` ở Bước 1 hoặc sửa `draft` ở bước hiện tại, chưa chuyển bước.
- `reopen`: nhận `step` trước đó; ở Bước 5 có thể thêm `scene_id` để sửa một lời thoại. Các lời thoại sau được giữ thành bản nháp để duyệt lại.
- `handoff`: gửi đúng bộ nội dung đã chốt tới webhook v2. Chỉ báo nhận thành công nếu mã, phiên bản và SHA-256 trong biên nhận của Long khớp.

Phiên có `step`, `revision`, `status`, `draft`, `approved`, `scene_cursor`, `dialogues`, `validation`, `validation_details`, `warnings`. Kết quả `quality` gồm điểm, phản hồi, lỗi có bằng chứng và lời nhắc riêng. Trạng thái gồm `awaiting_input`, `awaiting_approval`, `processing`, `needs_changes`, `ready`, `error`. Lỗi bàn giao không xóa bộ prompt.

## Kết nối với Long

Dùng [gói source v2 trong repo](../integrations/long-v2/README.md). Từ gốc AI-Tiktok, chạy stack thử theo hướng dẫn trong gói; không cần thư mục source ngoài repo.

```powershell
cd integrations/long-v2
docker compose -f docker-compose.yml -f docker-compose.acceptance.yml up -d --build
```

Đặt cấu hình riêng trong `integrations/long-v2/.env`, tạo từ `.env.example` tại chính thư mục đó. Cần database thử riêng và Docker Desktop đang chạy. Không chép token vào source hoặc gói bàn giao.

Trong n8n tại cổng 5678, import `n8n/Content Studio - AI Agent Callback v2.json` rồi bật workflow. Workflow mới dùng `/webhook/ai-agent-callback-v2`; workflow v1 giữ riêng. Bản JSON được lưu inactive để tránh tự kích hoạt khi chỉ đọc source.

Trước khi bật, chọn credential Header Auth với header `X-Content-Token` trùng `WEBHOOK_V2_TOKEN`. Webhook từ máy khác bắt buộc HTTPS và token; Quân chờ tối đa 150 giây, n8n chờ API 120 giây. Workflow tắt lưu execution data để tránh giữ header token.

Long đặt thêm `NOTION_V2_DATABASE_ID` để v2 dùng database thử; `NOTION_DATABASE_ID` vẫn dành cho v1. Không đổi đích của receipt đã lưu; nếu đổi database phải tạo phiên nghiệm thu mới. Xem [runbook nghiệm thu SEJOY](SEJOY_ACCEPTANCE_RUNBOOK.md) để chuẩn bị URL khi chưa có HTTPS và chạy công cụ đối chiếu.

Long nhận `POST /api/v2/content/ai-output` theo contract `contracts/handoff_v2.py` của Quân và bản sao `integrations/long-v2/python-service/app/contracts_v2.py`. Kiểm thử xác nhận hai bản giống hệt nhau. Payload gồm version, mã yêu cầu, revision, sản phẩm, nhân vật/metadata ảnh, danh sách cảnh 8 giây, nội dung đăng, kết quả QC và metadata.

- Snapshot đầy đủ và biên nhận SQLite lưu vào Docker volume `handoff_data`, mount `/data`.
- Nội dung tóm tắt ghi vào các cột Notion hiện tại. Prompt đầy đủ nằm dưới toggle **Content Studio v2** trong trang. Văn bản dài được chia thành nhiều block, không cắt nội dung.
- Gửi lại cùng mã/phiên bản/nội dung trả biên nhận cũ, không tạo trùng. Khác nội dung nhưng cùng mã/phiên bản trả 409. Bản cũ hơn bản đã nhận cũng bị từ chối.
- Nếu Notion dừng giữa chừng, gửi lại cùng bản: service đọc phần đã ghi, đối chiếu rồi tiếp tục. Nội dung chỉnh tay trong section được giữ và báo xung đột, không ghi đè.
- Bản nhận mới là `DRAFT`. Bản ghi đã sang trạng thái khác `DRAFT`/`FAILED` không được cập nhật bằng revision mới; tạo phiên mới nếu cần.
- HTTP 200 chỉ trả khi Notion đã lưu đầy đủ. HTTP 502 cho biết chưa hoàn tất, dù snapshot local có thể đã được giữ.

Đọc lại `GET /api/v2/content/{request_id}/revisions/{revision}` để kiểm tra trạng thái, toàn bộ payload và SHA-256. Đây là dữ liệu JSON; ảnh đi cùng ZIP cho Bảo, không có link ảnh localhost để chia sẻ nhóm.

## Kiểm thử và nghiệm thu

Schema AI dùng [structured output của Gemini](https://ai.google.dev/gemini-api/docs/structured-output), sau đó server kiểm tra lại bằng Pydantic và quy tắc nghiệp vụ. Nội dung trang Notion được chia nhỏ theo [giới hạn request của Notion](https://developers.notion.com/reference/request-limits); prompt không bị cắt để vừa một trường tóm tắt.

```powershell
cd AI-Tiktok
python -m pip install -r requirements-test.txt
python -m unittest tests.test_qc_results tests.test_studio_v2 tests.test_gateway_v2 tests.test_handoff_v2 tests.test_acceptance_tools tests.test_policy_validator tests.test_pipeline_kb_integration tests.test_webhook_integration -q
```

Các test dùng ảnh/dữ liệu tổng hợp và AI/Notion giả lập; không tiêu tiền model và không ghi vào database Notion thật. Để kiểm tra giao diện bằng fake AI riêng: `python -m tests.preview_studio`, mở cổng 8002. Server này chỉ dành cho QA, dùng dữ liệu riêng dưới `data/browser-qa`.

Nghiệm thu thật còn cần: một sản phẩm do Quân/Bảo xác nhận đủ thông tin và ảnh, khóa/model API hoạt động, workflow v2 được import và Notion có quyền ghi. Đi hết 7 bước, cho Bảo tạo thử một cảnh, gửi sang Long rồi đọc lại JSON để đối chiếu. Không coi kết quả giả lập là nghiệm thu sản phẩm thật.
