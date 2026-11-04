# Hồ sơ đánh giá đầu vào — SEJOY

Nguồn: link Shopee và nội dung trang do người dùng cung cấp ngày 04/11/2026. Đây là hồ sơ chuẩn bị bài nghiệm thu, chưa phải nội dung quảng cáo được duyệt hay đánh giá hiệu quả y tế.

## Đã đưa vào phiên

| Trường | Giá trị |
|---|---|
| Tên dùng để soạn nháp | Vớ đùi hở ngón SEJOY |
| Nhận diện từ mô tả người bán | Vớ dài đến đùi, hở ngón, một đôi/hộp |
| Giá nguyên văn | 518.600₫ |
| Điều kiện giá | Giá sau voucher theo nội dung người dùng gửi; cần kiểm tra lại khi đăng |
| Link | Giữ nguyên link Shopee trong `data/sejoy-evaluation.json` |
| Ảnh | Đã tải ảnh nguồn theo image_id trong link Shopee và thêm vào Bước 1; chờ Bảo xác nhận hoặc thay ảnh sạch |
| Duyệt | Bước 7, revision 26; QC Gemini thật 9/10 sau sửa nút chốt ngày 05/11/2026 |

Trang có các lựa chọn S–XXL, màu Da/Đen và Class 1/Class 2; chưa chốt lựa chọn nào. Không tự suy ra lựa chọn từ tham số URL.

## Phân loại thông tin để soạn nội dung

Nhận diện thương hiệu, kiểu dáng và quy cách đóng gói có thể dùng làm dữ liệu nháp chờ người dùng duyệt. Ảnh thực tế phải được đối chiếu trước khi mô tả màu sắc, hình dáng hay cách nhân vật cầm sản phẩm.

Các tác dụng y tế, khả năng phòng ngừa bệnh, giảm triệu chứng, độ an toàn cho nhóm bệnh cụ thể và chứng nhận ISO/FDA/công bố lưu hành hiện mới là thông tin từ người bán, chưa có hồ sơ đối chiếu. Không tự biến chúng thành kết luận hoặc lời chứng thực trong kịch bản.

Hướng tiếp cận ban đầu: giới thiệu nhận diện và kiểu dáng sản phẩm, không tạo câu chuyện đã dùng sản phẩm rồi khỏi bệnh hay cải thiện triệu chứng. Chưa viết hoặc duyệt lời thoại thay Quân/Bảo.

## Điều kiện còn thiếu

1. Xác nhận ảnh nguồn đúng biến thể hoặc thay ảnh sạch; kiểm tra giá còn áp dụng. Ảnh nguồn có chữ quảng cáo y tế và logo chứng nhận, không coi chúng là bằng chứng xác minh.
2. Biến thể muốn thể hiện; không tự chọn size hoặc mức áp lực cho người dùng.
3. Link hoặc xác nhận giỏ TikTok Shop tương ứng. Link Shopee chưa chứng minh sản phẩm đã có trong giỏ TikTok, trong khi câu chốt cố định nói đến TikTok Shop.
4. Bảo kiểm tra gói prompt đã xuất và tạo thử một cảnh.
5. Docker/n8n/Notion của Long hoạt động; biên nhận và JSON đọc lại khớp bản đã duyệt.

Chưa đủ điều kiện nghiệm thu cả chuỗi với nhóm. Phiên hiện hoàn tất Bước 7, QC Gemini 3.1 Flash-Lite
đạt 9/10, không có lỗi chặn. Đã tải ZIP có đủ bốn cảnh và hai ảnh; lời thoại và nội dung đăng giữ nguyên
so với snapshot trước sửa nút. Xem `data/qc-fix-real-result.json` và `data/qc-fixed-sejoy.jpg`.
Chưa gọi webhook, chưa có clip thử hoặc biên nhận từ Long. QC này không phải phê duyệt của TikTok hay
xác minh độc lập các nhận định sản phẩm trong nội dung.
