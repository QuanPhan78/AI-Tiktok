"""Persist an MP4 separately from its immutable, approved prompt bundle."""

import hashlib
import os
import struct
from pathlib import Path
from urllib.parse import urlsplit

import httpx


MAX_BYTES = 45 * 1024 * 1024


def boxes(file, start, end):
    while start < end:
        file.seek(start)
        size, kind = struct.unpack(">I4s", file.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", file.read(8))[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            raise ValueError("Tệp MP4 có cấu trúc không hợp lệ.")
        yield kind, start + header, start + size
        start += size


def contains_video(file, movie):
    for kind, start, end in boxes(file, *movie):
        if kind != b"trak":
            continue
        for kind, start, end in boxes(file, start, end):
            if kind != b"mdia":
                continue
            for kind, start, end in boxes(file, start, end):
                if kind == b"hdlr" and end - start >= 12:
                    file.seek(start + 8)
                    if file.read(4) == b"vide":
                        return True
    return False


def save_mp4(source, path):
    size = 0
    digest = hashlib.sha256()
    with path.open("xb") as target:
        while chunk := source.read(256 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                raise OverflowError("Tệp MP4 tối đa 45 MB.")
            digest.update(chunk)
            target.write(chunk)
    with path.open("rb") as target:
        movie = None
        ftyp = media = False
        try:
            for index, (kind, start, end) in enumerate(boxes(target, 0, size)):
                if index == 0 and kind == b"ftyp" and end - start >= 8:
                    ftyp = True
                if kind == b"mdat" and end > start:
                    media = True
                if kind == b"moov":
                    movie = (start, end)
            if ftyp and media and movie and contains_video(target, movie):
                return {"size": size, "sha256": digest.hexdigest()}
        except struct.error:
            pass
    raise ValueError("Cần tệp MP4 có một luồng hình ảnh hợp lệ.")


def review_request(session, video, method):
    base = os.getenv("VIDEO_REVIEW_API_URL", "http://127.0.0.1:8000").rstrip("/")
    url = urlsplit(base)
    token = os.getenv("WEBHOOK_V2_TOKEN", "").strip()
    loopback = url.hostname in ("127.0.0.1", "localhost", "::1")
    if (not token or not url.hostname or url.username or url.password or url.query or url.fragment or
            not (url.scheme == "https" or (loopback and url.scheme == "http"))):
        raise ValueError("Cần cấu hình VIDEO_REVIEW_API_URL và WEBHOOK_V2_TOKEN để gửi duyệt video.")
    request_id = session["request_id"]
    fields = {"revision": video["bundle_revision"], "version": video["version"], "sha256": video["sha256"]}
    endpoint = f"{base}/api/v2/content/{request_id}/video-review"
    with httpx.Client(timeout=150, trust_env=False, follow_redirects=False,
                      headers={"X-Content-Token": token}) as client:
        if method == "POST":
            with Path(video["path"]).open("rb") as file:
                response = client.post(endpoint, data=fields, files={"file": ("video.mp4", file, "video/mp4")})
        else:
            response = client.get(endpoint, params=fields)
    if not response.is_success:
        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
            detail = body.get("detail") or (body.get("error") or {}).get("message")
            if isinstance(detail, str):
                raise ValueError(detail)
        raise ValueError(f"Hệ thống chưa xác nhận yêu cầu duyệt video trên Telegram (HTTP {response.status_code}).")
    result = response.json().get("data") or {}
    if result.get("request_id") != request_id or any(result.get(key) != value for key, value in fields.items()):
        raise ValueError("Biên nhận video không khớp phiên bản đã gửi.")
    if result.get("status") not in ("PENDING_REVIEW", "APPROVED", "NEEDS_REVISION"):
        raise ValueError("Hệ thống chưa xác nhận đã gửi video để duyệt trên Telegram.")
    return result
