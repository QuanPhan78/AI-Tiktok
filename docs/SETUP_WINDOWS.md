# Cài và chạy Content Studio trên Windows

Hướng dẫn dành cho bản `main` của AI-Tiktok. Cài đặt tạo môi trường Python và hai file cấu hình mẫu; không tự kết nối dịch vụ hoặc đăng video. Máy đã cài có thể dùng lại bộ cài mà không thay file cấu hình hoặc xóa dữ liệu.

## 1. Chuẩn bị và lấy mã nguồn

- Windows, Python **3.12 hoặc 3.13** (hai phiên bản được kiểm tra trên GitHub Actions). Bộ cài cũng chấp nhận Python 3 mới hơn từ 3.12; nếu thư viện không tương thích, dùng 3.12/3.13. Khi cài Python, chọn Python Launcher và thêm Python vào PATH.
- Git để clone/cập nhật. Nếu tải ZIP từ GitHub, giải nén toàn bộ, không lấy riêng script cài.
- Docker Desktop đã mở, dùng Linux containers và có Docker Compose nếu cần chạy cả hệ thống.
- Ngrok và tài khoản của bạn nếu cần callback từ Telegram/TikTok. Dùng tên miền phát triển miễn phí thuộc tài khoản đó.
- Node.js **20 trở lên** chỉ cần khi chạy kiểm thử, không bắt buộc để dùng Studio.

```powershell
git clone https://github.com/QuanPhan78/AI-Tiktok.git
cd AI-Tiktok
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

`ExecutionPolicy Bypass` chỉ áp dụng cho lần chạy này, không đổi thiết lập toàn máy. Lệnh hoạt động với thư mục có dấu cách. Nếu dùng ZIP, mở PowerShell trong thư mục chứa README rồi chạy lệnh cuối. Không cần mở quyền quản trị.

Bộ cài tạo `.venv`, cài `requirements.txt`, tạo `.env` và `integrations/long-v2/.env` nếu chưa có. File đã tồn tại được giữ nguyên từng byte. Nếu môi trường `.venv` cũ bị hỏng, bộ cài báo lỗi để bạn xử lý, không tự xóa hay thay thế.

## 2. Chọn phần cần dùng và điền cấu hình

Mở hai file `.env` bằng trình soạn thảo tại máy. Không gửi file này vào chat, GitHub, ảnh chụp hoặc báo cáo. File `.env.example` chỉ chứa mẫu, không điền khóa thật vào đó.

| Phần cần dùng | Cấu hình cần chuẩn bị |
|---|---|
| Studio chạy bằng Python | `GEMINI_API_KEY` trong `.env`. Giữ `HOST=127.0.0.1`, `PORT=8001`, `ENABLE_NGROK=0` và chế độ cá nhân mặc định. |
| Studio chạy trong Docker | `GEMINI_API_KEY` trong `integrations/long-v2/.env`. Docker lấy khóa từ file này; khóa trong `.env` ở gốc không tự truyền sang Docker. |
| Bàn giao nội dung vào Notion | `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `NOTION_V2_DATABASE_ID`, `MASTER_DB_PROVIDER=notion` trong file Automation. Database thử v2 phải khác database v1 và cho integration truy cập; xem schema ở [hướng dẫn Automation](../integrations/long-v2/README.md#1-chuẩn-bị-cấu-hình-và-notion-thử). |
| Kết nối Studio → n8n → Automation | Một `WEBHOOK_V2_TOKEN` giống nhau trong hai file `.env` và credential Header Auth của n8n. Khi chạy Studio bằng Python, giữ `WEBHOOK_V2_URL=http://127.0.0.1:5678/webhook/ai-agent-callback-v2` và `VIDEO_REVIEW_API_URL=http://127.0.0.1:8000`. Docker đã khai báo địa chỉ nội bộ tương ứng. |
| Duyệt MP4 qua Telegram | Trong file Automation: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_AUTHORIZED_USER_IDS`, `TELEGRAM_WEBHOOK_SECRET`. ID người duyệt cách nhau bằng dấu phẩy. |
| Callback qua HTTPS | Trong file Automation: `STUDIO_PUBLIC_URL` là tên miền HTTPS ngrok miễn phí, không kèm đường dẫn; `NGROK_DOMAIN_CONFIRMED=1` chỉ sau khi đối chiếu tên miền trong tài khoản. Cấu hình ngrok authtoken trên máy hoặc điền `NGROK_AUTHTOKEN` tại đây. |
| Kết nối và đăng TikTok | Trong file Automation: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_V2_REDIRECT_URI`, `TIKTOK_TOKEN_ENCRYPTION_KEY`; xem bước 5. |

Khi chuyển giữa Studio Python và Docker, điền cùng khóa Gemini và token dùng chung vào cả hai file. Không chạy cả hai Studio trên cùng cổng 8001.

Để tạo token nội bộ cho **lần cài mới**, chạy tại máy và lưu kết quả vào cấu hình riêng:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Tạo riêng một giá trị cho `WEBHOOK_V2_TOKEN` và một giá trị khác cho `TELEGRAM_WEBHOOK_SECRET`. Khi cập nhật máy đã cài, dùng lại các giá trị đang dùng; không tạo lại chỉ vì chạy bộ cài.

Các khóa OpenAI/Anthropic và biến của pipeline v1 trong mẫu phục vụ tính năng tùy chọn/cũ; không bắt buộc cho luồng Studio dùng Gemini. Chat AI mặc định tắt, xem [hướng dẫn trợ lý](CHATBOX.md) nếu muốn bật.

## 3. Kiểm tra và khởi động

**Chỉ dùng Studio bằng Python:**

```powershell
.\.venv\Scripts\python.exe scripts/check_setup.py --profile studio
.\.venv\Scripts\python.exe run_server.py
```

Giữ cửa sổ server mở, truy cập [Studio](http://127.0.0.1:8001/app). Cách này chưa khởi động Automation/n8n. Muốn thử giao diện không gọi AI, dùng `python -m tests.preview_studio` bằng Python trong `.venv`, rồi mở cổng 8002; đây là dữ liệu giả lập.

**Chạy đầy đủ bằng Docker:** mở Docker Desktop, điền cấu hình rồi chạy:

```powershell
.\.venv\Scripts\python.exe scripts/check_setup.py --profile automation
.\.venv\Scripts\python.exe scripts/start_personal.py
.\.venv\Scripts\python.exe scripts/check_setup.py --profile automation --runtime
```

Lệnh khởi động giữ project hiện có `sejoy-stage1` và dữ liệu của nó: Studio **8001**, Automation **8000**, n8n **5678**, gateway **8080**. Lần đầu cần mạng để tải image/cài thư viện. Đợi dịch vụ lên rồi kiểm tra lại nếu health chưa đạt.

`check_setup.py` trả mã 0 khi các mục kiểm tra đạt, mã 1 khi còn thiếu. Ba profile lần lượt kiểm tra Studio, thêm Automation, rồi thêm điều kiện cấu hình đăng TikTok. Profile `automation` kiểm tra cả hai file để hỗ trợ chuyển giữa cách chạy Python và Docker. `--runtime` chỉ đọc các địa chỉ localhost. Công cụ không xác nhận khóa còn hiệu lực, schema Notion, credential/workflow n8n hay quyền tài khoản bên ngoài; kiểm tra các phần đó ở bước tiếp theo.

## 4. Hoàn tất n8n, Notion và Telegram

Mở [n8n trên máy](http://127.0.0.1:5678), thiết lập tài khoản n8n lần đầu. Import ba workflow trong [thư mục n8n](../integrations/long-v2/n8n):

1. `Content Studio - AI Agent Callback v2.json`: gắn credential **Header Auth**, tên `Content Studio v2 - X-Content-Token`, header `X-Content-Token`, giá trị bằng `WEBHOOK_V2_TOKEN` đã lưu. Sau đó bật workflow.
2. `Content Studio - Telegram Video Review v2.json`: bật workflow nhận phản hồi duyệt.
3. `Content Studio - Publishing Scheduler v2.json`: chọn cùng credential Header Auth ở node **Process owned schedules**. Chỉ bật khi sẵn sàng nghiệm thu đăng; giữ bộ gửi bài tắt trong cấu hình khi chưa đủ điều kiện. Không bật lịch/đăng/thử lại v1 cho cùng dữ liệu v2.

Kiểm tra quyền và schema database thử bằng lệnh chỉ đọc:

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py --env-file integrations/long-v2/.env preflight --side long
```

Mở kết nối ngoài máy sau khi đã xác nhận tên miền:

```powershell
.\.venv\Scripts\python.exe scripts/start_personal.py --tunnel
```

Tunnel trỏ gateway **8080**. Trang chỉnh sửa `/app` vẫn chỉ dùng trên máy. Làm theo [hướng dẫn Telegram](../integrations/long-v2/README.md#6-duyệt-mp4-trên-telegram) để lấy đúng ID và đăng ký webhook `/webhook/telegram-video-callback-v2` có secret. Bot đã có webhook thì kiểm tra đúng hệ thống trước khi thay; mỗi bot chỉ dùng một webhook.

Tạo phiên mới, duyệt nội dung, xuất gói, tạo clip trong Gemini và tải MP4 thật về Studio. Thử lưu nội dung vào Notion và duyệt đúng MP4 qua Telegram. Mã kiểm tra và hướng dẫn này không tự tạo video hoặc thay việc xem/duyệt video của bạn.

## 5. Điều kiện kết nối và đăng TikTok

Dùng lại ứng dụng Developer của dự án nếu bạn có quyền sử dụng. Người quản lý ứng dụng cần đăng ký callback **chính xác** bằng `STUDIO_PUBLIC_URL` + `/api/v2/tiktok/callback` trong **Login Kit của đúng Sandbox**; cấu hình `TIKTOK_V2_REDIRECT_URI` cũng phải trùng. Giữ callback v1 nếu hệ thống cũ vẫn dùng.

**Đối chiếu ngày 19/11/2026:** lần thử trên máy trả `invalid_request`, `error_type=redirect_uri` trước bước đăng nhập. Có tên trong Target Users chưa chứng minh quyền sửa ứng dụng Developer. Cần người quản lý kiểm tra callback đúng Sandbox; bộ cài không thể tự sửa điều kiện này hoặc coi OAuth đã hoàn tất.

Tạo khóa mã hóa cho **lần cài mới**:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Lưu vào `TIKTOK_TOKEN_ENCRYPTION_KEY`; sao lưu riêng và giữ nguyên khi cập nhật. Không thay khóa của hệ thống đã lưu tài khoản TikTok.

Tiếp tục theo [hướng dẫn đăng và nghiệm thu](TIKTOK_PUBLISHING_V2.md):

- Kiểm tra Login Kit, quyền `video.publish` và tài khoản thử của đúng Sandbox.
- Xác minh tên miền hoặc prefix `/media/tiktok/`; đặt file TikTok cấp vào [thư mục verification](../integrations/long-v2/verification/README.md). Chỉ sau xác minh thành công mới đặt `TIKTOK_MEDIA_URL_VERIFIED=1`.
- Kết nối tài khoản từ Studio và tự cấp quyền. Giữ `TIKTOK_APP_AUDITED=0` khi chưa có kết quả audit.
- Giữ `TIKTOK_SCHEDULER_ENABLED=0` cho đến khi cấu hình và quyền được kiểm tra, có MP4 đã duyệt và bạn sẵn sàng gửi bài mới. Khi đủ điều kiện, bật cờ, nạp lại Docker, bật đúng workflow lịch v2 rồi kiểm tra:

```powershell
.\.venv\Scripts\python.exe scripts/check_setup.py --profile publishing --runtime
```

Kết quả đạt chỉ là điều kiện trên máy, chưa chứng minh TikTok cho phép đăng. Nghiệm thu bằng hai video đã duyệt riêng: một đăng ngay, một đặt lịch, quyền **Chỉ mình tôi**. Đối chiếu kết quả trên tài khoản TikTok. Video TikTok Shop chưa hỗ trợ đăng tự động trong bản này.

## 6. Cập nhật, sao lưu và kiểm thử

Trước khi đổi bản chạy, sao lưu cấu hình, dữ liệu Studio và volume theo [hướng dẫn sao lưu](PERSONAL_STUDIO.md#sao-lưu-và-khôi-phục). Không chạy `docker compose down -v`; không thay project khi muốn giữ dữ liệu cũ.

```powershell
git status
git pull --ff-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Nếu có thay đổi riêng hoặc Git báo xung đột, giữ chúng và xử lý trước; không reset hoặc chép đè. Chạy lại lệnh khởi động để nạp mã/cấu hình mới. Bộ cài giữ `.env` cũ, nên đối chiếu mẫu nếu bản mới bổ sung biến.

Để chạy kiểm thử bằng dữ liệu giả lập:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -WithTests
.\.venv\Scripts\python.exe scripts/verify.py
```

Kiểm thử tách khóa và dữ liệu thật; GitHub Actions chạy Windows/Linux và kiểm tra Compose. Nếu thư viện cài lỗi, kiểm tra mạng và phiên bản Python. Nếu Docker chưa sẵn sàng, mở Docker Desktop rồi thử lại. Nếu cổng bận, xác định bản đang chạy trước khi khởi động thêm. Nếu callback TikTok lỗi, kiểm tra bước 5; không bật cờ xác minh để bỏ qua lỗi.
