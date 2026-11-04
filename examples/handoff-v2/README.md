# Ví dụ dữ liệu v2 — hoàn toàn tổng hợp

Các file trong thư mục này được tạo bằng gateway giả lập từ fixture hộp đựng bút. Đây là mẫu cấu trúc và tài liệu thao tác, không phải một sản phẩm thật, kết quả Gemini thật hoặc nghiệm thu với Long/Bảo.

| File | Nội dung |
|---|---|
| [product.png](product.png) | Ảnh placeholder cho kiểm thử upload, không mô phỏng ngoại hình sản phẩm thật |
| [handoff.json](handoff.json) | Bundle bốn cảnh, schema 2.0, metadata model ghi rõ fake |
| [prompts.md](prompts.md) | Prompt nguyên vẹn được lắp từ bundle mẫu |

Để xem giao diện: chạy `python -m tests.preview_studio` từ gốc repo và mở cổng 8002. Nhập tên **Hộp đựng bút — dữ liệu tổng hợp**, công dụng **Đựng bút trên bàn**, giá **59.000 đồng**, link `https://example.com/test-product`, tải ảnh placeholder trong thư mục này rồi đi qua các bước.

Chọn nhân vật NV5 từ thư viện khi cần so với mẫu. Ảnh nhân vật mẫu nằm ở [thư viện NV5](../../knowledge_base/characters/images/NV5_Trang.png); ứng dụng tự đóng ảnh vào ZIP khi xuất. Các mã asset/request và thời gian của mẫu cố định chỉ dùng minh họa; không nhập nó vào database Notion đang dùng.

Gói SEJOY thật do máy tạo phiên xuất ở Bước 7 và gửi riêng trong nhóm. Repo mới clone không chứa ảnh tải lên, phiên hoặc ZIP SEJOY.
