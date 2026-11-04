"""Bounded public-page lookup; never fetch loopback/private network resources."""
import ipaddress
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import httpx


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def public_url(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Link không hợp lệ.")
    if p.port not in (None, 80, 443):
        raise ValueError("Chỉ hỗ trợ cổng web công khai.")
    addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Không đọc địa chỉ mạng nội bộ.")


def read_product_link(url):
    failure = {"status": "unavailable", "message": "Không mở được link, chỉ dùng thông tin bạn nhập và phần bổ sung được bạn duyệt.", "text": ""}
    try:
        started = time.monotonic()
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            for _ in range(3):
                public_url(url)
                with client.stream("GET", url, headers={"User-Agent": "ContentStudio/2.0"}) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers["location"])
                        continue
                    response.raise_for_status()
                    if "text/html" not in response.headers.get("content-type", ""):
                        return failure
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started > 10:
                            return failure
                        body.extend(chunk)
                        if len(body) > 1_000_000:
                            return failure
                    parser = TextParser()
                    parser.feed(bytes(body).decode(response.encoding or "utf-8", errors="replace"))
                    text = " ".join(parser.parts)[:12000]
                    if len(text) < 80:
                        return failure
                    return {"status": "read", "message": "Đã đọc được link; nội dung trang cần bạn kiểm tra.", "text": text}
    except Exception:
        pass
    return failure
