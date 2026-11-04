# Trạng thái Content Studio v2 — 05/11/2026

Bài chính: [bàn giao và chạy thử](HANDOFF_CONTENT_STUDIO_V2.md). Source automation v2 đóng trong [gói cho Long](../integrations/long-v2/README.md). Phần Telegram, tạo video, ghép MP4 và đăng TikTok chưa triển khai trong đợt này.

## Đã có trong source

- Web tiếng Việt `/app`, bảy bước có người duyệt; SQLite lưu phiên/lịch sử, ảnh và tác vụ.
- Tám nhân vật với ảnh tham chiếu; nhân vật mới có ảnh riêng; chế độ nói/thuyết minh.
- Bốn hoặc năm cảnh dự kiến 8 giây, chốt riêng lời thoại, câu cuối cố định; xuất JSON/Markdown/ZIP.
- QC có lỗi trích dẫn theo trường/cảnh và lời nhắc riêng; tự cuộn tới kết quả. Cảnh báo phong cách/độ dài không tự chặn, điểm dưới 8 hoặc lỗi nội dung thật vẫn chặn. Lỗi AI/API giữ bản chỉnh sửa và lời thoại đã duyệt.
- API v2, workflow n8n giữ toàn bộ JSON, lưu snapshot/receipt trên volume, ghi Notion DRAFT; chống trùng và đọc lại để đối chiếu. API v1 giữ định dạng cũ.
- Gói source tự chứa trong repo; test tích hợp không còn mặc định đọc thư mục ngoài repo. Có thể đặt `LONG_AUTOMATION_ROOT` để kiểm tra checkout riêng.

## Kiểm chứng đã thực hiện

Trước đợt đóng gói, **119/119 test đạt**, gồm 10 bài QC và các bài API v1. Trình duyệt đã xác minh: lỗi có trích đoạn hiển thị gần nút chốt, tự cuộn/focus đúng, lỗi AI giữ caption vừa sửa, trường hợp 8 điểm chỉ có cảnh báo được sang Bước 7.

Chạy suite không gọi AI/Notion thật từ gốc repo, sau khi cài `requirements-test.txt`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_qc_results tests.test_studio_v2 tests.test_gateway_v2 tests.test_handoff_v2 tests.test_acceptance_tools tests.test_policy_validator tests.test_pipeline_kb_integration tests.test_webhook_integration -q
```

Không dùng test live để thay lệnh này. Các log chi tiết ở `data/` là artifact local và không có trong repo clone mới.

### Xác minh source bàn giao

| Kiểm tra ngày 05/11/2026 | Kết quả |
|---|---|
| Suite với gói automation trong repo | **119/119 đạt**, 32,488 giây |
| Bản sao chỉ từ file staged, môi trường Python cài mới | **119/119 đạt**, 29,061 giây; không có thư mục source Long bên ngoài hoặc credential được sao chép |
| Web từ bản sao sạch | Khởi động được; `/app` và `/health` HTTP 200 trên cổng kiểm thử 18001; nhãn giao diện đã bỏ tên cá nhân |
| Docker Compose | Cấu hình base + override nghiệm thu hợp lệ |
| Image API Python 3.12 | Build thành công; kiểm tra health, route v1/v2 và mẫu JSON hợp lệ trong container tắt mạng; thiếu Notion trả 503, không báo thành công giả |
| Contract và gói source | Hai bản contract giống từng byte; manifest hash khớp cả trên bản sao sạch |
| Tài liệu và dữ liệu | Liên kết tương đối hợp lệ; ví dụ/screenshot dùng dữ liệu tổng hợp; không có `.env` thật, DB hay credential trong file chuẩn bị commit |

Môi trường cài mới dùng Python 3.14, FastAPI 0.162.0, google-genai 2.34.0, Pydantic 2.14.2,
LangGraph 1.2.19 và notion-client 2.2.1. Container Python 3.12 chỉ được smoke test API, không phải
toàn bộ 119 bài. Số liệu máy đọc được nằm trong [verification-2026-11-05.json](verification-2026-11-05.json).
Các kiểm tra này chưa chạy workflow n8n/ghi Notion thật và chưa tạo video.

## SEJOY thật

| Hạng mục | Kết quả |
|---|---|
| Model | Gemini 3.1 Flash-Lite đã trả nội dung thật; model dự phòng cấu hình 3.5 Flash-Lite |
| Bộ prompt | Revision 26, bốn cảnh, QC **9/10**, không lỗi chặn; JSON/Markdown/ZIP đã tải thành công |
| Bảo toàn dữ liệu | Đối chiếu snapshot xác nhận sản phẩm, lời thoại, các bước 1–5 và nội dung đăng không thay đổi trong lần sửa nút chốt |
| Ảnh | ZIP có đủ ảnh sản phẩm/nhân vật, SHA-256 khớp; ảnh nguồn và biến thể vẫn cần nhóm kiểm tra |
| Lần gửi sau đó | Phiên revision 27 có lỗi kết nối, không có biên nhận; bundle được giữ ở revision 26 |
| Nghiệm thu nhóm | Chưa có clip thử Bảo xác nhận và readback/biên nhận từ Long |

Các lần dùng model cũ đã gặp 503/504; sau đổi cấu hình đã gọi AI thật thành công. Không xem model quá tải trước đây là trạng thái hiện tại của mọi bước. Đổi key không bảo đảm giải quyết quá tải dịch vụ.

Bằng chứng gốc trên máy tạo phiên gồm snapshot trước/sau, kết quả đối chiếu QC và ZIP SEJOY. Chúng nằm ngoài Git vì chứa phiên thực. [Ví dụ tổng hợp](../examples/handoff-v2/README.md) minh họa cấu trúc, không thay cho bằng chứng thật.

## Còn chờ

1. Bảo xác nhận ảnh/biến thể, tạo thử Cảnh 2 và trả clip gốc cùng nhận xét.
2. Chạy workflow v2 với database thử; nhận và đọc lại JSON khớp bundle, kiểm tra giữ dữ liệu sau restart.
3. Kiểm tra giá/giỏ TikTok Shop trước khi dùng nội dung công khai; QC không xác minh độc lập hiệu quả hay chứng nhận sản phẩm.

Docker engine đã phản hồi trong lần chuẩn bị gói. Điều này chưa chứng minh stack n8n/Notion đã được cấu hình hoặc nghiệm thu. Xem [runbook SEJOY](SEJOY_ACCEPTANCE_RUNBOOK.md).
