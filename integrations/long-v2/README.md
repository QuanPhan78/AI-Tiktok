# Gói automation Content Studio v2 cho Long

Gói này chạy Automation API và n8n để nhận bundle Content Studio v2, lưu bản đầy đủ vào Notion và duyệt đúng phiên bản MP4 qua Telegram. Source nền từ [LongVu-AI/AI_Content_Automation](https://github.com/LongVu-AI/AI_Content_Automation). Gói cũng có workflow v1 để phục vụ tích hợp cũ.

## 1. Chuẩn bị cấu hình và Notion thử

Từ gốc repo AI-Tiktok, cài dependency theo [bài chính](../../docs/HANDOFF_CONTENT_STUDIO_V2.md), mở Docker Desktop rồi:

```powershell
cd integrations/long-v2
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Trong `.env` tại thư mục này, điền `NOTION_TOKEN` của integration, `NOTION_DATABASE_ID` của database v1/cấu trúc gốc và `NOTION_V2_DATABASE_ID` của **database thử khác**. Cho integration truy cập database thử. Có thể nhân cấu trúc database hiện có nhưng không sao chép các dòng dữ liệu.

Schema database thử phải có các cột dưới đây, đúng tên và kiểu. Cột `status` dùng các lựa chọn bên dưới.

| Cột | Kiểu Notion |
|---|---|
| `request_id` | Title |
| `product_name`, `hook_text`, `voice_over_text`, `text_on_screen`, `image_prompt_en` | Rich text |
| `post_caption`, `hashtags`, `qc_feedback` | Rich text |
| `product_link` | URL |
| `qc_score` | Number |
| `status` | Select với `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `NEEDS_REVISION` |

Chạy preflight từ gốc repo; lệnh chỉ đọc schema, không tạo trang:

```powershell
cd ../..
.\.venv\Scripts\python.exe scripts/acceptance.py --env-file integrations/long-v2/.env preflight --side long
```

Nếu có lỗi, sửa cấu hình/schema trước khi gửi. Source dùng `notion-client==2.2.1`; giữ phiên bản đó cho đợt nghiệm thu, không tự nâng SDK trong lúc kiểm tra.

## 2. Chạy stack thử

```powershell
cd integrations/long-v2
docker compose -f docker-compose.yml -f docker-compose.acceptance.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.acceptance.yml up -d --build
```

- API: [health cổng 8000](http://127.0.0.1:8000/health), [tài liệu API](http://127.0.0.1:8000/docs).
- n8n: [cổng 5678](http://127.0.0.1:5678), hoàn tất thiết lập tài khoản local nếu chạy lần đầu.
- Override bật `CONTENT_V2_ACCEPTANCE_MODE=1`, từ chối ghi khi database thử thiếu/trùng database v1.
- Gateway tùy chọn cổng 5679 chỉ phục vụ webhook v2, để nhận callback HTTPS từ Telegram hoặc từ máy khác. Gửi bundle từ web trên cùng máy dùng cổng 5678.

Stack dùng volume cho n8n và dữ liệu bàn giao. Không dùng `docker compose down -v` nếu cần giữ dữ liệu. Nếu máy đã chạy các container/cổng 8000 hoặc 5678, chọn cập nhật stack hiện có hoặc dừng đúng stack cũ trước; không chạy hai bản trên cùng cổng. Gói dùng tên container tương ứng source Long để thuận tiện đối chiếu.

## 3. Import workflow và Header Auth

1. Import [Content Studio - AI Agent Callback v2.json](n8n/Content%20Studio%20-%20AI%20Agent%20Callback%20v2.json).
2. Tạo credential **Header Auth**, tên `Content Studio v2 - X-Content-Token`, header `X-Content-Token`. Giá trị là token bí mật tự đặt, trùng `WEBHOOK_V2_TOKEN` trong `.env` của web.
3. Chọn credential đó ở node Webhook v2. Workflow ở trạng thái tắt sau khi import. Bật sau khi đã gắn credential.
4. Web cùng máy dùng URL production `http://127.0.0.1:5678/webhook/ai-agent-callback-v2`. Sau khi đổi `.env`, khởi động lại web để nạp cấu hình.
5. Thiếu/sai Header Auth phải bị từ chối, không tạo trang Notion. Workflow tắt lưu execution data chứa header; không bật lại để chụp token.

Node HTTP gọi `http://python-service:8000/api/v2/content/ai-output` trong mạng Docker. Không thay nó bằng `127.0.0.1:8000` trong container n8n. Biên nhận được trả nguyên về web; chỉ trả thành công sau khi Notion đã ghi đủ.

Nếu chạy khác máy, cung cấp URL HTTPS v2 có Header Auth cho máy web. Gateway trong override chỉ mở đường dẫn callback; chỉ mở tunnel sau khi xác thực đã hoạt động, không mở giao diện n8n ra ngoài. `.env` và credential được trao đổi qua kênh riêng, không đặt vào URL hoặc Git.

## 4. Đọc lại và đối chiếu

Từ API, lấy `GET /api/v2/content/{request_id}/revisions/{revision}`. Dùng revision **trong bundle**, lưu nguyên JSON thành `readback.json`; nhận biên nhận từ web hoặc response n8n. Từ gốc repo:

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py compare --bundle handoff.json --receipt receipt.json --readback readback.json --database-id ID_DATABASE_THU --zip goi-da-duyet.zip
```

`session.handoff` là phần `data` của biên nhận; nếu lấy từ API phiên, bọc nó thành `{"success":true,"data":...}` trước khi lưu `receipt.json`. Công cụ so request/revision, database, SHA-256, toàn bộ payload, prompt Markdown và hash hai ảnh trong ZIP. Đọc lại sau khi restart để xác nhận volume giữ dữ liệu.

JSON đầy đủ và receipt SQLite nằm ở `/data`, mount volume `handoff_data`. Gửi lại cùng bản không tạo trùng; bản đã sang trạng thái ngoài `DRAFT`/`FAILED` không được ghi đè bằng revision mới. Lỗi 502 có thể đã lưu một phần; gửi lại **nguyên bản** để tiếp tục, không sửa payload cùng revision.

## 5. Áp dụng vào repo hiện có của Long

Review diff của `python-service/app/main.py`, hai module v2, Compose, workflow và script trước khi áp dụng. `main.py` cần import/include router v2; không chép đè file nếu repo Long đã có thay đổi mới. Giữ `.env`, workflow v1 và volume hiện tại; bổ sung volume `handoff_data`, các biến v2 cùng database thử. `SOURCE_MANIFEST.json` liệt kê toàn bộ source đóng gói để đối chiếu, với SHA-256 văn bản UTF-8 đã chuẩn hóa xuống dòng LF để giống nhau trên Windows/Linux. Khi sửa gói, chạy `python scripts/package_manifest.py` từ gốc repo rồi chạy kiểm thử.

Từ gốc AI-Tiktok, kiểm thử mặc định dùng gói này. Muốn kiểm tra một checkout khác của Long, đặt `LONG_AUTOMATION_ROOT` bằng đường dẫn tới thư mục có `python-service/` và `n8n/`, rồi chạy lại suite. Hai bản contract phải giống nguyên vẹn.

Lệnh kiểm thử phát hành là `python scripts/verify.py` từ gốc repo sau khi cài `requirements-test.txt` và Node.js 20 trở lên. `run_tests.ps1` cũng gọi lệnh chung này. Lệnh phát hành luôn kiểm tra gói ngay trong repo và cách ly cấu hình thật. Để đối chiếu checkout khác bằng `LONG_AUTOMATION_ROOT`, chạy riêng `python -m unittest tests.test_handoff_v2 -q`.

Xem [runbook SEJOY](../../docs/SEJOY_ACCEPTANCE_RUNBOOK.md) và [API web](../../docs/CONTENT_STUDIO_V2.md).

## 6. Duyệt MP4 trên Telegram

### Tạo bot và lấy ID người duyệt

1. Trong Telegram, mở [BotFather](https://t.me/BotFather), gửi `/newbot`, đặt tên và username kết thúc bằng `bot`. Lưu token của bot thử vào `TELEGRAM_BOT_TOKEN` trong `integrations/long-v2/.env`. Mỗi bot chỉ có một webhook, nên dùng bot riêng cho v2 nếu v1 đang hoạt động. [Hướng dẫn BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).
2. Thêm bot vào nhóm thử với quyền thành viên thường. Giữ chế độ riêng tư mặc định. Từ tài khoản sẽ duyệt, gửi `/start@TenBotCuaBan sejoy-test` trong nhóm. Thay `TenBotCuaBan` bằng username thật.
3. Trước khi đăng ký webhook, dùng `getUpdates` để lấy `message.chat.id` và `message.from.id` của đúng tin nhắn thử. Đặt chúng trong `TELEGRAM_CHAT_ID` và `TELEGRAM_AUTHORIZED_USER_IDS`. Với nhiều người duyệt, phân tách các ID bằng dấu phẩy. [Telegram Bot API](https://core.telegram.org/bots/api#getupdates).

Có thể đọc ID từ PowerShell. Chạy trong `integrations/long-v2`, sau khi lưu token bot thử và gửi tin nhắn trên:

```powershell
function Read-AutomationSetting([string]$Name) {
    $prefix = "$Name="
    $line = Get-Content -LiteralPath .env |
        Where-Object { $_.StartsWith($prefix) } |
        Select-Object -First 1
    if (!$line) { throw "Thiếu $Name trong .env" }
    $line.Substring($prefix.Length).Trim()
}
function Invoke-BotApi([string]$Method, [hashtable]$Body = @{}) {
    $token = Read-AutomationSetting TELEGRAM_BOT_TOKEN
    $request = @{
        Method = 'Post'
        Uri = "https://api.telegram.org/bot$token/$Method"
        ContentType = 'application/json'
        Body = ($Body | ConvertTo-Json -Depth 5)
        TimeoutSec = 20
    }
    try {
        $result = Invoke-RestMethod @request
    } catch {
        throw "Telegram chưa xác nhận $Method. Kiểm tra kết nối và bot thử."
    }
    if (!$result.ok) { throw "Telegram chưa xác nhận $Method." }
    $result.result
}

$bot = Invoke-BotApi getMe
$registration = Invoke-BotApi getWebhookInfo
if ($registration.url) { throw 'Bot đã có webhook. Kiểm tra lại đúng bot thử.' }
$updates = Invoke-BotApi getUpdates @{ allowed_updates = @('message'); timeout = 0 }
$command = "/start@$($bot.username) sejoy-test"
$updates | Where-Object {
    $_.message.chat.type -in @('group', 'supergroup') -and $_.message.text -eq $command
} | ForEach-Object {
    [pscustomobject]@{
        Group = $_.message.chat.title
        ChatId = $_.message.chat.id
        ReviewerId = $_.message.from.id
    }
}
```

Đối chiếu tên nhóm và đúng tài khoản trước khi lưu hai ID. Nếu chưa thấy tin nhắn, chạy `getUpdates` một lần để chọn loại sự kiện, rồi gửi lại lệnh trong nhóm.

### Nối webhook HTTPS

1. Tạo chuỗi bí mật ngẫu nhiên cho `TELEGRAM_WEBHOOK_SECRET`. Ví dụ dùng `[guid]::NewGuid().ToString('N')` trên máy. Lưu trong `.env` của Automation và chạy lại lệnh `docker compose … up -d` ở mục 2 để nạp các biến Telegram. `WEBHOOK_V2_TOKEN` dùng chung cho Content Studio, n8n và Automation.
2. Import và bật [workflow duyệt MP4](n8n/Content%20Studio%20-%20Telegram%20Video%20Review%20v2.json) trong n8n. Gateway ở cổng 5679 phục vụ các đường dẫn webhook v2. Dùng URL HTTPS hướng tới gateway, chẳng hạn chạy `cloudflared tunnel --url http://127.0.0.1:5679` để thử tạm thời. Giữ tunnel chạy khi cần duyệt. Nếu URL tạm thay đổi, đăng ký lại webhook cho bot thử. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
3. Trong cùng cửa sổ PowerShell, dùng hàm `Invoke-BotApi` ở trên để đăng ký. Thay tên miền bằng địa chỉ HTTPS thật của gateway.

```powershell
$callback = 'https://your-webhook-host.example/webhook/telegram-video-callback-v2'
Invoke-BotApi setWebhook @{
    url = $callback
    secret_token = (Read-AutomationSetting TELEGRAM_WEBHOOK_SECRET)
    allowed_updates = @('callback_query')
}
Invoke-BotApi getWebhookInfo |
    Select-Object url, allowed_updates, pending_update_count, last_error_message
```

Đối chiếu `url` và `allowed_updates`. n8n chuyển tiếp header xác thực đến Automation. Automation đối chiếu bí mật, nhóm, người duyệt, tin nhắn và phiên bản MP4 trước khi ghi quyết định. [Đăng ký webhook Telegram](https://core.telegram.org/bots/api#setwebhook).

### Gửi và nhận quyết định

Tại Bước 7, bấm **Lưu nội dung vào Notion** để có biên nhận prompt. Bấm **Tải MP4 lên** để tải và xem trước tệp tối đa 45 MB, rồi bấm **Gửi video để duyệt trên Telegram**. Khi Telegram nhận clip, Notion chuyển sang `PENDING_REVIEW`. Chọn **Duyệt video** hoặc **Cần sửa** trong nhóm rồi bấm **Cập nhật trạng thái duyệt** ở web để đồng bộ.

Khi gửi phiên bản MP4 thay thế, nút trong tin nhắn cũ hết hiệu lực. Phiên bản mới cần quyết định riêng. Kiểm thử v2 với database thử. Workflow lập lịch và đăng v1 phục vụ database v1. [Bàn giao đăng TikTok](../../docs/HANDOFF_CONTENT_STUDIO_V2.md#6-bàn-giao-để-đăng-tiktok).
