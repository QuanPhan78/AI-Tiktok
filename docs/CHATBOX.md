# Dùng trợ lý theo phiên

Tại Content Studio, mở một phiên rồi bấm **Trợ lý ✦** ở góc phải. Tên sản phẩm, bước và phiên bản tham chiếu hiện ở đầu hộp chat. Trợ lý hỏi đáp về nội dung đang làm; việc sửa, chốt và gửi duyệt vẫn dùng các nút của quy trình 7 bước.

## Hai cách trả lời

- **Hướng dẫn có sẵn · không gọi AI**: tra thông tin sản phẩm đã nhập, bước tiếp theo, lỗi đã lưu, cách chuẩn bị Gemini và trạng thái MP4 đã đồng bộ. Đây là câu trả lời theo quy tắc có sẵn, không phải AI phân tích câu hỏi tự do.
- **Trao đổi với Gemini**: hỏi tự do theo dữ liệu phiên và quy tắc nội dung. Chỉ bật sau khi xác nhận dự án/key và model có Free tier. Câu trả lời có mục **Căn cứ trả lời**, cho xem dữ liệu đã tham chiếu. Hãy đối chiếu nhận xét AI trước khi dùng.

Chọn câu hỏi gợi ý chỉ điền ô soạn, bấm **Gửi câu hỏi →** để gửi. Nếu đã có bản nháp, chọn gợi ý hoặc soạn lại tin lỗi không ghi đè bản đang viết. Lịch sử lưu trong SQLite theo từng phiên; đổi phiên không trộn cuộc chat. Ô soạn chưa gửi lưu riêng trong trình duyệt. **Xem tin cũ hơn** tải thêm từng nhóm 50 lượt.

Chat không tăng revision nội dung. Câu trả lời từ revision cũ được đánh dấu; hỏi lại sau khi sửa phiên để lấy ngữ cảnh mới. Chat chỉ đọc trạng thái Notion/Telegram đã lưu; **Cập nhật trạng thái duyệt** ở Bước 7 mới đồng bộ quyết định mới nhất. Trợ lý chưa đọc nội dung âm thanh/hình ảnh trong MP4.

## Bật Gemini với dự án miễn phí

Mặc định bản clone chỉ có hướng dẫn không gọi AI. Tại [Projects trong Google AI Studio](https://aistudio.google.com/projects), đối chiếu đúng project/key hiện dùng với cột **Free tier**. Kiểm tra model ở [Rate Limit](https://aistudio.google.com/rate-limit). Không bấm thiết lập thanh toán nếu chỉ dùng miễn phí.

Sau khi kiểm tra và lưu `GEMINI_API_KEY` trong `.env`, từ gốc repo chạy:

```powershell
.\.venv\Scripts\python.exe scripts/configure_chat.py --model gemini-3.1-flash-lite --confirm-free-tier
```

Thay model bằng model đã kiểm tra trong tài khoản. Lệnh ghi nhận xác nhận cho đúng cặp key/model, không in key, không tự kiểm tra billing và không bật dịch vụ trả phí. Khởi động lại web. Khi đổi key/model, xác nhận cũ hết hiệu lực. Nếu chuyển project sang trả phí, đặt `CHAT_AI_ENABLED=0` rồi khởi động lại; ứng dụng không theo dõi thay đổi billing của Google theo thời gian thực.

`CHAT_DAILY_LIMIT=20` giới hạn lượt chat Gemini trong ứng dụng trên tất cả phiên mỗi ngày theo giờ Việt Nam, kể cả lượt lỗi. Đây không phải hạn mức Google còn lại. Một tin nhắn gọi API tối đa một lần, timeout 30 giây, không tự đổi model hoặc tự thử lại. Giới hạn ngữ cảnh và câu trả lời giúp giảm số token. [Free tier và billing của Gemini](https://ai.google.dev/gemini-api/docs/billing).

## Khi có lỗi

- Mất kết nối khi gửi: câu hỏi giữ trong ô soạn; gửi lại cùng nội dung sử dụng cùng mã tin để không gọi trùng AI nếu server đã nhận.
- AI lỗi hoặc quá tải: câu hỏi và lỗi lưu trong lịch sử. Bấm **Soạn lại câu hỏi**, rồi tự gửi một lượt mới khi sẵn sàng.
- Hết hạn mức: chờ hoặc đổi sang hướng dẫn có sẵn. Không tự nâng gói hay chuyển model.
- Server dừng giữa lượt: lịch sử đánh dấu gián đoạn, không tự gọi AI khi mở lại.
- Phiên đang sinh nội dung hoặc đã thay đổi ở tab khác: đợi xong/mở lại phiên rồi hỏi tiếp; bản nháp chat vẫn được giữ.

Phần áp dụng đề xuất sửa kịch bản đang ở [mốc tiếp theo của kế hoạch](CHATBOX_PLAN.md). Hiện chưa có nút áp dụng hoặc cho trợ lý tự duyệt.

## Kết quả kiểm tra ngày 15/11/2026

Bộ kiểm thử chung đạt **158 bài**: 141 kiểm thử Python, 10 kiểm thử Automation và 7 kiểm thử JavaScript. Bao gồm lỗi 429/503/504, JSON sai, gửi trùng, thay phiên bản khi đang trả lời, khôi phục lịch sử và bảo vệ bản nháp.

Đã thử Gemini thật sau khi đối chiếu Free tier: trợ lý nhận đúng SEJOY ở Bước 7, bộ prompt r26 và MP4 v1 đã duyệt; hướng dẫn chuyển sang chuẩn bị đăng. Đã kiểm tra tải lại trang, chuyển sang phiên dữ liệu giả, phục hồi bản nháp riêng và giao diện điện thoại. Đối chiếu SHA-256 dữ liệu các phiên trước/sau cho kết quả không thay đổi. Dữ liệu thật, ảnh nghiệm thu, khóa và lịch sử chat nằm ngoài Git.
