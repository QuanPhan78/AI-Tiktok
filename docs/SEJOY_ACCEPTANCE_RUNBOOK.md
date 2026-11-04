# Nghiệm thu SEJOY: bộ prompt → clip thử → dữ liệu nhận

Hiện đã có bundle **revision 26**, bốn cảnh, Gemini thật QC **9/10**. Phiên tăng lên revision 27 sau lần gửi lỗi kết nối, chưa có biên nhận. Không tạo lại hoặc tự sửa nội dung đã duyệt chỉ để vượt kiểm tra. Gói thật nằm trên máy tạo phiên, gửi riêng cho nhóm.

## Chuẩn bị

- Bảo kiểm tra ảnh nguồn đúng biến thể hoặc thay ảnh phù hợp. Ảnh hiện có chữ quảng cáo/chứng nhận chưa được xác minh; chưa chốt size, màu và áp lực.
- Giá đầu vào **518.600₫** là giá sau voucher trong nội dung người dùng gửi; cần kiểm tra lại khi đăng.
- Giữ câu cuối cố định. Chưa xác nhận giỏ TikTok Shop tương ứng thì chỉ dùng nội bộ; link Shopee không chứng minh đã có giỏ TikTok.
- Có database Notion thử riêng, đúng schema và được integration truy cập. Không ghi nghiệm thu vào database đang dùng.

## 1. Bên web — kiểm tra và lấy gói

Từ gốc repo, dùng `.env` riêng:

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py preflight --side quan
.\.venv\Scripts\python.exe run_server.py
```

Mở cổng 8001, chọn phiên SEJOY trên máy tạo phiên và tải ZIP tại Bước 7. Repo clone mới không có phiên đó; nhận ZIP từ nhóm, hoặc tạo một phiên khác và duyệt đủ bảy bước khi cần chạy lại.

Giữ nguyên `handoff.json`, `prompts.md` và hai ảnh. Không sửa prompt ngoài phiên. Nếu sửa đầu vào/hành động/lời thoại, quay lại bước tương ứng và duyệt lại các bước phụ thuộc để có bundle revision mới.

## 2. Bảo — tạo thử Cảnh 2

Dùng nguyên prompt Cảnh 2 trong `prompts.md`, đính kèm ảnh sản phẩm và ảnh nhân vật của chính ZIP, tạo clip 8 giây bằng công cụ đang dùng. Gửi clip gốc và ghi:

- request_id, bundle revision, mã cảnh, công cụ/model tạo video;
- hình dáng/màu sản phẩm và nhân vật có đúng không;
- lời thoại có đúng/đủ, nhịp nói, lỗi hình ảnh, watermark nếu có.

Cần sửa hành động/phong cách thì quay Bước 4; sửa lời thoại quay Bước 5. Một cảnh đạt chưa có nghĩa câu chốt Cảnh 4 đã đọc vừa thời lượng.

## 3. Long — nhận vào database thử

Làm theo [README gói automation](../integrations/long-v2/README.md): cấu hình `.env`, chạy preflight đọc schema, khởi động Docker với override nghiệm thu, import workflow v2 và bật Header Auth `X-Content-Token`.

Web và Docker cùng máy dùng `http://127.0.0.1:5678/webhook/ai-agent-callback-v2`. Hai máy khác nhau cần URL HTTPS production v2; localhost không dùng làm link chia sẻ. Không cần dựng URL HTTPS để thử trên cùng máy.

Gửi đúng bundle từ nút **Gửi sang Long** sau khi cấu hình xong. Kiểm tra phản hồi thành công, Notion trạng thái DRAFT và đầy đủ cảnh/prompt trong thân trang. Không xem HTTP lỗi hoặc thao tác đang xử lý là đã bàn giao.

## 4. Đối chiếu và lưu bằng chứng

Lưu nguyên biên nhận n8n vào `receipt.json`; nếu lấy `session.handoff` từ API web thì bọc thành `{"success":true,"data":...}`. Long đọc `GET /api/v2/content/{request_id}/revisions/{revision}` bằng revision trong bundle, lưu `readback.json`. Từ gốc repo:

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py compare --bundle handoff.json --receipt receipt.json --readback readback.json --database-id ID_DATABASE_THU --zip goi-da-duyet.zip
```

Lệnh kiểm tra schema, request/revision, toàn bộ payload, SHA-256, database đích, prompt Markdown và ảnh trong ZIP. Restart service, giữ volume, đọc lại và so lần nữa. Gửi lại cùng bundle phải trả duplicate mà không tạo trang/section trùng.

Chỉ thử bảo vệ trạng thái đã duyệt/lập lịch bằng một bản ghi tổng hợp riêng, không dùng bản SEJOY chính. Database thử không nối vào workflow đăng bài.

## Điều kiện hoàn tất

Có đủ ZIP đã duyệt, clip thử dùng được do Bảo xác nhận, biên nhận và readback khớp trước/sau restart do Long xác nhận. `technical_checks_passed=true` chưa thay thế xác nhận thủ công. Thiếu mục nào thì ghi chờ mục đó; chưa có bài đăng TikTok hoặc tích hợp Telegram trong đợt này.
