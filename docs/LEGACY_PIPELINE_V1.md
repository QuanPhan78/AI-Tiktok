# Pipeline tự động v1

V1 được giữ để tương thích với workflow cũ. Web duyệt 7 bước dùng [Content Studio v2](HANDOFF_CONTENT_STUDIO_V2.md).

## Luồng và cách chạy

LangGraph chạy Research → Script → Hashtag → QC. Pipeline v1 có vòng tự sửa khi QC chưa đạt; quy trình v2 giữ lời thoại đã duyệt và chỉ yêu cầu người dùng chỉnh sửa.

Cài runtime từ gốc repo bằng `python -m pip install -r requirements.txt`, cấu hình `.env` rồi chạy `python run_server.py`:

- API ở cổng 8001, tài liệu tại `/docs`, kiểm tra tại `/health`.
- `POST /generate` nhận sản phẩm, trả trạng thái xử lý nền.
- `GET /status/{request_id}` đọc tiến độ trong RAM; log v1 không phải lịch sử SQLite của v2.
- Kết quả gửi webhook `/webhook/ai-agent-callback` dưới dạng `ai_result`.

```dotenv
GEMINI_API_KEY=your_gemini_api_key
WEBHOOK_URL=http://localhost:5678/webhook/ai-agent-callback
PORT=8001
ENABLE_NGROK=0
```

Contract v1 gồm hook, voice-over, text-on-screen, image prompt, caption, hashtag và QC; không có cấu trúc từng cảnh/ảnh của v2. Model pipeline cũ cấu hình theo source hiện hành; không mặc định rằng đổi model web v2 sẽ thay mọi prototype.

Các prototype so sánh trong `prototypes/` dùng dependency riêng tại `requirements-prototypes.txt`, không cần để chạy web v2. Không truyền bundle `scenes[]` của v2 vào webhook v1. Gói automation v2 được bàn giao riêng, không chứa workflow n8n v1; Long giữ workflow v1 từ repo của mình.
