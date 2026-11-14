# Kế hoạch trợ lý chat trong Content Studio

Ngày 14/11/2026, người dùng chọn **trợ lý trong Content Studio**. Mục tiêu là hỏi đáp về phiên đang mở, giải thích việc cần làm, góp ý kịch bản và chuẩn bị sửa nội dung ngay trong web. Chức năng này chưa được triển khai trong bản hợp nhất.

## Trải nghiệm cần đạt

Góc phải web có nút **Trợ lý**. Bấm mở bảng chat cạnh nội dung đang duyệt, trên điện thoại mở dạng bảng toàn màn hình. Đầu bảng hiển thị tên sản phẩm, bước hiện tại và phiên bản đang tham chiếu. Đổi phiên đổi luôn lịch sử chat để không trộn sản phẩm.

Các câu gợi ý tùy bước gồm **Tôi cần làm gì tiếp?**, **Giải thích lỗi kiểm tra nội dung**, **Gợi ý rút ngắn lời thoại cảnh này**, **Cần đưa gì sang Gemini?** và **Video đã được duyệt chưa?**. Người dùng vẫn có thể hỏi tự do.

Ví dụ: đang ở Bước 5, hỏi “Rút cảnh 2 còn khoảng 22 từ”. Trợ lý đưa đề xuất, số từ và phần so sánh cũ/mới. Nút **Dùng làm bản nháp** chỉ xuất hiện khi đề xuất hợp lệ. Người dùng kiểm tra bản nháp và duyệt bằng luồng hiện có.

## Dữ liệu trợ lý được dùng

| Nguồn | Cách sử dụng |
|---|---|
| Phiên đang mở | Sản phẩm người dùng xác nhận, bước, nhân vật, lời thoại, kế hoạch cảnh, lỗi và cảnh báo. |
| Bundle đã duyệt | Revision prompt, thứ tự cảnh, chế độ giọng, hướng dẫn Notebook. Phân biệt revision phiên với revision bundle. |
| Video và biên nhận | MP4 version, trạng thái lần đồng bộ gần nhất, thời điểm nhận; không nói vừa kiểm tra Telegram nếu chỉ đọc bản lưu. |
| Knowledge Base | Nhân vật, quy tắc nội dung, hướng dẫn thương hiệu và quy trình sử dụng đã chọn lọc. |
| Cuộc chat của phiên | Các lượt gần đây có giới hạn độ dài. Lưu riêng lịch sử đầy đủ, không gửi lại vô hạn. |

Thông tin chưa xác nhận phải ghi rõ. Câu trả lời về dữ liệu sản phẩm dẫn đến trường đã xác nhận; câu trả lời về quy trình dẫn đến bước/nút hoặc tài liệu trong app. Không tự bổ sung chứng nhận, hiệu quả sức khỏe, giá hoặc biến thể từ suy đoán. Trang sản phẩm và nội dung chat được xử lý như dữ liệu, không có quyền thay đổi quy tắc hệ thống.

## Thứ tự triển khai

| Mốc | Công việc | Điều kiện hoàn thành |
|---|---|---|
| 1. Chat hỏi đáp theo phiên | Giao diện chat, API gửi/đọc tin, lưu SQLite, nhận ngữ cảnh từ server, hỗ trợ Gemini trả câu trả lời có cấu trúc. | Hỏi đúng thông tin phiên, tải lại web còn lịch sử; đổi phiên không lẫn dữ liệu; trò chuyện không sửa revision nội dung. |
| 2. Góp ý kịch bản | Trả đề xuất cho đúng trường/cảnh, so sánh cũ/mới, số từ, cảnh báo và căn cứ. | Hỏi rút lời thoại hoặc sửa caption nhận được đề xuất rõ; câu chốt cố định được bảo vệ; chưa bấm áp dụng thì nội dung không đổi. |
| 3. Áp dụng qua quy trình hiện có | Nút Dùng làm bản nháp; kiểm tra revision và field hợp lệ; mở lại bước đã duyệt khi cần, nói rõ phần nào phải duyệt lại. | Không vượt bước, không tự duyệt; thay đổi lưu lịch sử và hủy đúng xác nhận phụ thuộc; phiên đổi trong lúc chat thì đề xuất cũ bị từ chối. |
| 4. Nghiệm thu toàn luồng | Thử 4/5 cảnh, nói trực tiếp/thuyết minh, hết hạn mức/lỗi mạng, Notion và MP4 đã duyệt. | Tất cả kiểm thử mới/cũ đạt; sửa kịch bản thành revision mới, xuất Notebook đúng bản; MP4 cũ không tự nhận duyệt cho bản mới. |

Làm mốc 1 trước, dùng thử trên một bản sao dữ liệu SEJOY và một sản phẩm tổng hợp. Bản SEJOY r26 đã duyệt chỉ được hỏi đáp để đối chiếu, không tự sửa làm mẫu.

## Thiết kế kỹ thuật dự kiến

Tái sử dụng FastAPI, JavaScript và SQLite hiện có, không thêm ứng dụng frontend hoặc một pipeline phê duyệt thứ hai.

- `api/chat.py`: đề xuất `GET/POST /api/v2/sessions/{id}/chat/messages`; gửi `message_id`, `expected_revision`, `text`. Server tự đọc phiên; không tin ngữ cảnh đã duyệt do trình duyệt gửi lên. Tin trùng trả lại cùng kết quả; mỗi phiên chỉ xử lý một lượt chat AI tại một thời điểm.
- `studio/chat.py`: lấy ngữ cảnh tối thiểu, sinh câu trả lời/đề xuất, gắn revision đã đọc. Không giữ khóa giao dịch SQLite trong lúc gọi AI. Nếu nội dung đổi khi chờ trả lời, đánh dấu đề xuất hết hiệu lực trước khi cho áp dụng.
- `studio/chat_models.py`: kiểm tra `answer`, `sources`, `warnings`, `suggestions[]`; mỗi đề xuất có bước, mã cảnh, field, giá trị trước/sau và base revision. Server kiểm tra nguồn được viện dẫn và giá trị cũ, không chỉ tin JSON của model.
- `prompts/chat.py`: hướng dẫn riêng cho trợ lý; tái sử dụng quy tắc và thư viện chung, không dùng lại prompt sinh toàn bộ pipeline v1.
- SQLite bổ sung bảng tin nhắn, tác vụ chat và đề xuất. Lỗi/restart giữ lời nhắn và nội dung đã duyệt; tác vụ gián đoạn được đánh dấu để người dùng thử lại, không tự gọi lại làm tốn hạn mức.
- Áp dụng đề xuất dùng `Store.claim/finish` và quy tắc của `Studio` trong `studio/service.py`. Thêm action riêng hoặc dịch vụ dùng chung để mở lại + ghi nháp trong một thao tác có kiểm tra revision; không nối hai request rời dễ áp dụng vào nhầm phiên bản.
- `web/chat.js`, `web/chat.css`: bảng chat, trạng thái đang xử lý, lỗi có nút thử lại, lịch sử, nguồn và so sánh đề xuất. Render văn bản an toàn, không chèn HTML tùy ý từ AI.

Mốc đầu dùng phản hồi JSON và trạng thái tác vụ; chỉ thêm trả chữ dần khi có lợi rõ ràng. Các endpoint chat phải tôn trọng nguyên tắc một worker local và không mở lịch sử chat ra mạng công khai.

## Ranh giới thao tác

Trợ lý có thể giải thích, tạo đề xuất và dẫn người dùng đến nút tương ứng. Áp dụng đề xuất cần người dùng bấm, sau đó vẫn duyệt bằng quy trình 7 bước. Ảnh, bộ prompt và MP4 dùng cùng ID/revision của hệ thống.

Gửi Notion, gửi video Telegram, quyết định duyệt và đăng bài giữ nút riêng. Trợ lý không giả vờ đã tạo video, đã xem hết MP4 hay đã gửi một dịch vụ khi chưa có kết quả thực tế. Hộp chat không lấy cookie/tài khoản từ Gemini và không thay thế tiện ích điền prompt.

Nếu mở rộng công cụ cho AI sau này, server chỉ cho danh sách thao tác được phép và kiểm tra quyền/phiên bản trước khi thực hiện. [Function calling của Gemini](https://ai.google.dev/gemini-api/docs/function-calling).

## Yêu cầu chỉ dùng miễn phí

Chat dùng API văn bản có cấu hình riêng (`CHAT_MODEL`, timeout, giới hạn lượt/ngày và lượng ngữ cảnh). Tận dụng client và cách báo lỗi hiện có nhưng không tự chuyển sang model khác khi hết hạn mức. Khi 429, lưu lịch sử và báo chờ; khi lỗi tạm thời, retry giới hạn và không tạo hai tác vụ cho cùng tin.

Trước khi bật chat AI, xác nhận project/key đang dùng Free tier và model được cấp hạn mức miễn phí. Giới hạn trong ứng dụng chỉ giúp giảm số lượt gọi, không chứng minh tài khoản Google không bị tính phí. Nếu chưa xác minh được, để chat AI tắt và dùng phần hướng dẫn có sẵn. Không bật billing hay đăng ký gói thay người dùng. Gói dùng Gemini trên web không đồng nghĩa hạn mức API. [Bảng giá và Free tier của Gemini API](https://ai.google.dev/gemini-api/docs/pricing).

Không đưa key vào JavaScript, ZIP, tin chat hoặc log. Bảng thông báo trong web nêu hạn mức ứng dụng đã dùng; không ghi con số đó là hạn mức Google còn lại nếu chưa có dữ liệu từ Google.

## Kiểm thử nghiệm thu cụ thể

1. Hai phiên khác sản phẩm, chat xen kẽ vẫn trả đúng nguồn; tải lại web và restart server giữ lịch sử.
2. Hỏi đáp không thay đổi revision, lời thoại, bundle, MP4 hoặc quyết định Telegram.
3. Tin gửi trùng và nhiều lần bấm gửi chỉ gọi AI một lần. Lỗi 429/503, JSON sai và restart không xóa bản nháp; log không lộ key.
4. Đề xuất rút lời thoại vẫn giữ công dụng đã xác nhận, không có giá/link trong lời nói; câu chốt cố định không bị thay.
5. Đề xuất ở revision cũ không được áp dụng; thay lời thoại đã duyệt đưa đúng bước về chờ duyệt và ghi lịch sử.
6. Không thể dùng nội dung prompt hoặc một câu chat để bỏ bước, tự gửi Notion/Telegram hay tự duyệt.
7. Phiên 5 cảnh phân biệt 3A/3B, thuyết minh tách khỏi âm thanh clip, Notebook lấy đúng bản mới sau khi duyệt lại.
8. Kiểm thử giả lập đi qua nút dùng bản nháp đến xuất bundle; nghiệm thu AI thật chỉ thực hiện sau khi xác nhận hạn mức miễn phí.

Đầu ra đầu tiên cần bàn giao là hộp chat hỏi đáp theo phiên cùng kiểm thử lưu lịch sử và nguồn dữ liệu. Các nút áp dụng đề xuất được phát triển ở mốc tiếp theo sau khi hỏi đáp hoạt động ổn định.
