# 🎬 TikTok AI Agent — Hệ Thống Tự Động Hóa Kịch Bản & Guardrails TikTok

Hệ thống AI Agent thông minh sử dụng **LangGraph**, **FastAPI** và **Google Gemini** để tự động nghiên cứu sản phẩm, tạo kịch bản video TikTok 30s chất lượng cao, chọn hashtag SEO, kiểm duyệt từ cấm chính sách (Policy Guardrails) và tự động đồng bộ qua Webhook n8n / Notion.

---

## 🌟 Tính Năng Nổi Bật

- **🧠 4-Node LangGraph Pipeline**:
  - `Research Agent`: Phân tích sản phẩm, insight khách hàng mục tiêu, tìm USP và góc tiếp cận TikTok.
  - `Script Agent`: Viết kịch bản video 30s chuyên nghiệp (Hook, Voice-over, Text-on-screen, Phân cảnh visual, Image prompt cho AI video).
  - `Hashtag Agent`: Tự động tạo 6–8 hashtag tối ưu TikTok SEO theo 3 tầng (Thương hiệu, Ngành hàng, Đối tượng).
  - `QC Agent`: Tự động chấm điểm 5 tiêu chí nội dung (Hook, USP, CTA, Tone, Chính sách).
- **🛡️ TikTok Knowledge Base & Policy Guardrails**:
  - **16 Hooks Library**: Mẫu mở đầu video chia theo 4 góc tâm lý (Nỗi đau, Tò mò, Số liệu, Câu hỏi).
  - **14 CTA Templates**: Mẫu kêu gọi hành động chuẩn giỏ hàng TikTok Shop, ưu đãi, bằng chứng uy tín.
  - **48 Từ cấm & Từ phóng đại**: Bộ lọc Regex Deterministic nhận diện từ cấm y tế/cam kết quá đà trên TikTok Shop VN.
  - **Chống lách luật thông minh**: Nhận diện leetspeak (`t | r | i`, `t - r - i`), bắt hashtag dính liền (`#tridutdiem`), chuẩn hóa Unicode (NFC/NFD), không bắt nhầm số đếm hợp lệ.
  - **Vòng lặp tự sửa lỗi (Retry Loop)**: Tự động trừ điểm QC và chỉ dẫn AI viết lại kịch bản nếu phát hiện từ cấm.
- **⚡ Kiến Trúc API Bất Đồng Bộ (Asynchronous)**:
  - Phản hồi `POST /generate` ngay lập tức trong `< 50ms` (`status: processing`), giải phóng kết nối cho n8n không bị timeout.
  - Tự động gọi ngược **Webhook Callback** về `n8n` khi AI xử lý xong để lưu trữ vào **Notion Database**.

---

## 📁 Cấu Trúc Dự Án

```
tiktok-ai-agent/
├── agents/                  # Core LangGraph pipeline & state management
│   ├── __init__.py
│   └── pipeline.py
├── api/                     # FastAPI server & background tasks
│   ├── __init__.py
│   └── main.py
├── knowledge_base/          # Tài nguyên tri thức & Bộ lọc kiểm duyệt
│   ├── tiktok/
│   │   ├── hooks_library.json
│   │   ├── cta_templates.json
│   │   └── prohibited_words.json
│   ├── brand/
│   │   └── guidelines.md
│   ├── loader.py
│   └── validator.py
├── prompts/                 # Prompt templates chuẩn cho 4 Agent
│   ├── research_agent.py
│   ├── script_agent.py
│   ├── hashtag_agent.py
│   └── qc_agent.py
├── prototypes/              # Các bản prototype thử nghiệm ban đầu
├── tests/                   # Bộ test tự động (Validator, Pipeline, Webhook)
│   ├── test_policy_validator.py
│   ├── test_pipeline_kb_integration.py
│   └── test_webhook_integration.py
├── run_server.py            # Script khởi động 1-click FastAPI + Ngrok
├── requirements.txt         # Danh sách thư viện Python
├── .env.example             # Mẫu cấu hình môi trường
└── README.md
```

---

## 🚀 Cài Đặt & Chạy Hệ Thống

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Sao chép `.env.example` thành `.env` và điền API Key:
```bash
cp .env.example .env
```
Cấu hình trong `.env`:
```env
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WEBHOOK_URL=http://localhost:5678/webhook/ai-agent-callback
```

### 3. Khởi động Server (Local & Public Ngrok)
```bash
python run_server.py
```
- Local API Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Sinh kịch bản: `POST http://localhost:8000/generate`

---

## 🧪 Chạy Kiểm Thử (Tests)

```bash
# Kiểm thử Bộ lọc từ cấm & chống lách luật
python tests/test_policy_validator.py

# Kiểm thử Tích hợp Knowledge Base vào Pipeline
python tests/test_pipeline_kb_integration.py

# Kiểm thử Webhook Callback
python -m unittest tests/test_webhook_integration.py
```

---

## 👥 Thành Viên Dự Án
- **Phan Minh Quân** — AI Agent Lead (LangGraph, Prompt Engineering, Guardrails, FastAPI)
- **Vũ Thiên Long** — AI Automation Engineer (N8N, Notion, Webhook, Docker)
- **Nguyễn Thái Bảo** — AI Content & Video (CapCut, Video Generation, Creative Assets)
