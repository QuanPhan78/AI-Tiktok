# Hướng dẫn Content Studio v2

Quy trình đã chạy thử với SEJOY gồm duyệt prompt, tạo MP4 trong Gemini, bàn giao nội dung vào Notion và duyệt đúng MP4 qua Telegram. Người quản lý tài khoản thực hiện bước đăng hoặc lên lịch trên TikTok.

## 1. Cài và mở Content Studio

Cần Git và Python 3.12 hoặc 3.13. Cài Docker Desktop nếu chạy cả Notion và Telegram. Các lệnh dưới dùng PowerShell trên Windows.

```powershell
git clone https://github.com/QuanPhan78/AI-Tiktok.git
cd AI-Tiktok
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Điền `GEMINI_API_KEY` trong `.env` ở gốc repo. Chọn `GEMINI_MODEL` và `GEMINI_FALLBACK_MODEL` mà tài khoản API của bạn có quyền dùng. Có thể cấu hình automation sau khi đã thử giao diện.

```powershell
.\.venv\Scripts\python.exe run_server.py
```

Mở [Content Studio](http://127.0.0.1:8001/app). Phiên, ảnh và lịch sử lưu trong `data/` trên máy chạy, nên có thể tiếp tục sau khi khởi động lại. Repo clone mới bắt đầu với dữ liệu trống.

Để thử quy trình bằng AI giả lập, chạy `.\.venv\Scripts\python.exe -m tests.preview_studio` trong cửa sổ riêng rồi mở [giao diện kiểm thử](http://127.0.0.1:8002/app). Có thể dùng [sản phẩm tổng hợp](../examples/handoff-v2/README.md).

![Giao diện Content Studio với dữ liệu tổng hợp](images/content-studio-v2-demo.jpg)

## 2. Duyệt nội dung qua 7 bước

| Bước | Việc cần làm |
|---|---|
| 1. Sản phẩm | Nhập tên, công dụng đã xác nhận, giá, link và ảnh. Kiểm tra tóm tắt trước khi duyệt. |
| 2. Tình huống | Chọn một đề xuất hoặc nhập tình huống riêng. |
| 3. Nhân vật | Chọn nhân vật có ảnh tham chiếu hoặc thêm nhân vật mới. Chọn nói trực tiếp hoặc thuyết minh. |
| 4. Kế hoạch cảnh | Dùng 4 cảnh hoặc tách cảnh 3 thành 3A và 3B. Duyệt hành động, cỡ cảnh và tư thế đầu, cuối để giữ mạch hình. |
| 5. Lời thoại | Duyệt từng cảnh. Với các cảnh trước câu chốt, dùng 18–24 từ làm mục tiêu rồi kiểm tra nhịp nói khi có video. Cảnh cuối dùng câu chốt cố định. |
| 6. Tổng hợp | Kiểm tra bảng kịch bản, chữ khi dựng, slogan, caption, hashtag và bình luận ghim. Chọn caption rồi bấm **Chốt và xuất prompt**. |
| 7. Xuất prompt | Sao chép prompt từng cảnh hoặc tải JSON, Markdown, ZIP. Mở **Nội dung đăng bài** để sao chép caption, hashtag và bình luận ghim. |

Bước 6 cho xuất khi điểm QC từ 8/10, không còn lỗi chặn và đủ dữ liệu. Web chỉ ra cảnh hoặc trường cần sửa ngay gần nút chốt. Cảnh báo nhịp đọc cần đối chiếu bằng clip thật. Nếu sửa một bước đã chốt, các bước phụ thuộc cần được duyệt lại. Lịch sử phiên giữ các bản trước.

ZIP gồm `handoff.json`, `prompts.md`, `product.*` và `character.*`. Mã yêu cầu và revision trong `handoff.json` dùng để đối chiếu bản nội dung, kể cả khi số revision của phiên tăng sau khi gửi hoặc duyệt.

## 3. Tạo và kiểm tra MP4

1. Mở `prompts.md` và lấy prompt đúng revision. Dùng ảnh sản phẩm và nhân vật của cùng ZIP làm tham chiếu.
2. Trong công cụ tạo video, chọn khung dọc 9:16. Với phép thử Gemini, bật chế độ Video trước, giữ cùng cuộc chat khi yêu cầu các cảnh nối tiếp. Tải bản gốc sau từng lượt.
3. Kiểm tra file trả về sau mỗi lượt. Nếu công cụ đã nối cảnh mới vào các cảnh trước, dùng bản nối cuối. Nếu công cụ trả clip riêng, ghép theo thứ tự rồi xuất một MP4.
4. Phát hết clip để đối chiếu nhân vật, sản phẩm, thứ tự cảnh và lời thoại. Giữ bản gốc và đo thời lượng thực. Dự kiến trong prompt là 8 giây mỗi cảnh. Bản SEJOY từ Gemini dài 40,04 giây cho bốn cảnh.

## 4. Bàn giao nội dung vào Notion

Làm theo [hướng dẫn cấu hình automation](../integrations/long-v2/README.md) để chạy Docker, cấp quyền Notion cho integration và import workflow n8n. Khi web và Docker cùng máy, đặt trong `.env` ở gốc repo:

```dotenv
WEBHOOK_V2_URL=http://127.0.0.1:5678/webhook/ai-agent-callback-v2
VIDEO_REVIEW_API_URL=http://127.0.0.1:8000
WEBHOOK_V2_TOKEN=your_shared_random_token
```

Đặt cùng giá trị `WEBHOOK_V2_TOKEN` cho Automation và credential Header Auth ở n8n. Khởi động lại web sau khi sửa `.env`. Cổng 5678 nhận dữ liệu prompt, cổng 8000 xử lý yêu cầu duyệt MP4, còn cổng 8001 là giao diện.

Tại Bước 7 bấm **Gửi sang Long**. Đợi web xác nhận đã nhận đúng revision và kiểm tra bản `DRAFT` trong database thử. Notion lưu phần tóm tắt và prompt đầy đủ. Biên nhận đối chiếu mã yêu cầu, revision và SHA-256 của JSON. [Cách đối chiếu và kiểm thử](SEJOY_ACCEPTANCE_RUNBOOK.md).

## 5. Duyệt video qua Telegram

1. Cấu hình bot thử, nhóm, người duyệt và webhook HTTPS. [Hướng dẫn Telegram](../integrations/long-v2/README.md#6-duyệt-mp4-trên-telegram).
2. Ở Bước 7, trong mục **Video của bản prompt**, chọn MP4 tối đa 45 MB, bấm **Gắn MP4** và phát thử trong web.
3. Khi web đã có biên nhận bàn giao prompt, bấm **Gửi duyệt video**. Telegram nhận MP4 và hiện bản prompt cùng phiên bản video. Notion chuyển sang `PENDING_REVIEW`.
4. Người được cấp quyền mở đúng tin nhắn và chọn **Duyệt video** hoặc **Cần sửa**. Trở lại Content Studio, bấm **Đọc trạng thái duyệt** để lấy quyết định. Notion và web phải cùng hiện `APPROVED` hoặc `NEEDS_REVISION`.
5. Khi có MP4 sửa lại, chọn **Thay video MP4**, bấm **Lưu MP4 thay thế** và gửi duyệt lại. Sau khi bản thay thế được gửi, nút trên tin nhắn cũ hết hiệu lực. Quyết định gắn với đúng revision prompt, phiên bản MP4 và SHA-256 của file.

## 6. Bàn giao để đăng TikTok

- Lấy đúng file MP4 đã được duyệt. Tại Bước 7, mở **Nội dung đăng bài** rồi bấm **Sao chép caption** và **Sao chép hashtag**.
- Chủ tài khoản tải video lên TikTok, dán nội dung đã chọn và gắn đúng sản phẩm nếu clip kêu gọi bấm giỏ hàng. Với hình hoặc giọng nói AI chân thực, bật nhãn nội dung do AI tạo. [Hướng dẫn TikTok](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content?authuser=0).
- Đăng ngay hoặc chọn lịch theo giờ Việt Nam trên TikTok. Sau khi bài lên, ghi link vào trang Notion để đối chiếu.

## 7. Xử lý lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
|---|---|
| Gemini báo 401, 403 hoặc 429 | Kiểm tra key, quyền model và hạn mức tài khoản. |
| Gemini báo 503 hoặc 504 | Đợi dịch vụ ổn định rồi thử lại. Bản đã duyệt vẫn lưu trong phiên. |
| Chưa xuất được prompt | Xem trường hoặc cảnh QC chỉ ra. Kiểm tra ảnh sản phẩm ở Bước 1 và ảnh nhân vật ở Bước 3. |
| Gửi sang Long lỗi 404 hoặc lỗi kết nối | Kiểm tra Docker, URL production `/webhook/ai-agent-callback-v2` và workflow đã bật. |
| Gửi sang Long lỗi 401 hoặc 403 | Đối chiếu `X-Content-Token` và `WEBHOOK_V2_TOKEN` ở cả ba nơi. |
| Notion lỗi 502 hoặc 503 | Kiểm tra quyền integration và database thử. Nếu service đã ghi một phần, gửi lại nguyên bundle để tiếp tục. |
| Telegram chưa có video | Kiểm tra biên nhận prompt, MP4 hợp lệ, bot trong nhóm và biến cấu hình Automation. |
| Bấm nút Telegram mà trạng thái chưa đổi | Kiểm tra webhook HTTPS còn chạy và tài khoản có quyền. Bấm **Đọc trạng thái duyệt** ở Content Studio. |
