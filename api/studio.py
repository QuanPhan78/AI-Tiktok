import hashlib
import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image
from studio.ai import characters
from studio.models import Action, Product, STEP_NAMES
from studio.output import CHAR_DIR, character_asset, markdown, build_bundle
from studio.service import Studio
from studio.store import Store, Conflict
from studio.video import save_mp4

router = APIRouter(prefix="/api/v2", tags=["Content Studio"])
workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio")


@lru_cache(maxsize=1)
def get_store():
    return Store()


def get_studio():
    return Studio(get_store())


def lookup(sid):
    try:
        return get_store().get(sid)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy phiên.")


def public_session(s):
    s["step_name"] = STEP_NAMES[s["step"] - 1]
    s["pending_action"] = "Xuất gói hoặc gửi sang Long" if s["step"] == 7 else f"Duyệt bước {s['step']}: {s['step_name']}"
    return s


@router.get("/characters")
def list_characters():
    return [{**c, "image_url": f"/api/v2/characters/{c['id']}/image"} for c in characters()]


@router.get("/characters/{cid}/image")
def character_image(cid: str):
    char = next((c for c in characters() if c["id"] == cid), None)
    if not char:
        raise HTTPException(404, "Không tìm thấy nhân vật.")
    return Response(portrait_thumbnail(char["image_filename"]), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


@lru_cache(maxsize=16)
def portrait_thumbnail(filename):
    # Keep original reference images in ZIP; the character picker needs only previews.
    out = io.BytesIO()
    with Image.open(CHAR_DIR / filename) as image:
        image = image.convert("RGB")
        image.thumbnail((384, 688))
        image.save(out, format="JPEG", quality=85)
    return out.getvalue()


@router.post("/assets", status_code=201)
async def upload_asset(file: UploadFile = File(...)):
    content = bytearray()
    while chunk := await file.read(65536):
        content.extend(chunk)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "Ảnh tối đa 10 MB.")
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.width * im.height > 25_000_000 or im.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError()
            kind = {"PNG": (".png", "image/png"), "JPEG": (".jpg", "image/jpeg"), "WEBP": (".webp", "image/webp")}[im.format]
            im.verify()
    except Exception:
        raise HTTPException(400, "Chỉ nhận ảnh PNG/JPEG/WebP hợp lệ, tối đa 25 megapixel.")
    aid = str(uuid.uuid4())
    folder = get_store().path.parent / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (aid + kind[0])
    path.write_bytes(content)
    meta = {"id": aid, "filename": Path((file.filename or "image").replace("\\", "/")).name[:150],
            "path": str(path.resolve()), "size": len(content), "sha256": hashlib.sha256(content).hexdigest(), "media_type": kind[1]}
    get_store().save_asset(meta)
    return {k: v for k, v in meta.items() if k != "path"}


@router.get("/assets/{aid}")
def asset_file(aid: str):
    try:
        meta = get_store().asset(aid)
        return FileResponse(meta["path"], media_type=meta["media_type"])
    except KeyError:
        raise HTTPException(404, "Không tìm thấy ảnh.")


@router.post("/sessions", status_code=201)
def create_session(product: Product):
    if product.asset_id:
        try:
            get_store().asset(product.asset_id)
        except KeyError:
            raise HTTPException(400, "Ảnh sản phẩm không tồn tại.")
    return public_session(get_store().create(product.model_dump()))


@router.get("/sessions")
def list_sessions():
    return [{k: s[k] for k in ("id", "request_id", "revision", "step", "status", "product", "updated_at")} for s in get_store().list()]


@router.get("/sessions/{sid}")
def get_session(sid: str):
    return public_session(lookup(sid))


@router.get("/sessions/{sid}/history")
def session_history(sid: str):
    lookup(sid)
    result = []
    for r in get_store().history(sid):
        result.append({"id": r["id"], "created": r["created"], "operation": json.loads(r["operation"]), "snapshot": json.loads(r["body"])})
    return result


@router.post("/sessions/{sid}/actions", status_code=202)
def session_action(sid: str, action: Action):
    req = action.model_dump()
    try:
        before, claimed = get_store().claim(sid, req)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy phiên.")
    except Conflict as exc:
        raise HTTPException(409, str(exc))
    if claimed:
        try:
            workers.submit(get_studio().execute, sid, req, before)
        except Exception:
            get_store().finish(sid, req["operation_id"], error="Không khởi tạo được tác vụ. Hãy thử lại.")
    return public_session(lookup(sid))


@router.post("/sessions/{sid}/videos", status_code=201)
def upload_video(sid: str, revision: int = Form(...), file: UploadFile = File(...)):
    lookup(sid)
    store = get_store()
    meta = {"id": uuid.uuid4().hex,
            "filename": Path((file.filename or "video.mp4").replace("\\", "/")).name[:150]}
    path = store.video_path(meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = False
    try:
        meta.update(save_mp4(file.file, path))
        session, kept = store.attach_video(sid, revision, meta)
        return public_session(session)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(413, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    finally:
        if not kept:
            path.unlink(missing_ok=True)


@router.get("/sessions/{sid}/videos/{version}")
def preview_video(sid: str, version: int):
    s = lookup(sid)
    video = s.get("video") or {}
    bundle = s.get("bundle") or {}
    if (s["step"] != 7 or video.get("version") != version or
            video.get("bundle_revision") != bundle.get("revision")):
        raise HTTPException(404, "Không có video của phiên bản hiện tại.")
    path = get_store().video_path(video)
    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp MP4.")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "private, no-store"})


@router.get("/sessions/{sid}/export/{fmt}")
def export_session(sid: str, fmt: str):
    s = lookup(sid)
    if s["step"] != 7 or not s.get("bundle") or s["status"] == "processing":
        raise HTTPException(409, "Cần hoàn tất và duyệt bước 6 trước khi xuất.")
    try:
        if build_bundle(s, get_store(), s["bundle"]["revision"]) != s["bundle"]:
            raise ValueError("Nội dung không trùng bản đã duyệt.")
    except Exception as exc:
        raise HTTPException(409, "Không thể xuất: " + str(exc))
    bundle = s["bundle"]
    name = s["request_id"] + f"_r{bundle['revision']}"
    raw = json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")
    md = markdown(bundle).encode("utf-8")
    if fmt == "json":
        content, media, ext = raw, "application/json", "json"
    elif fmt == "markdown":
        content, media, ext = md, "text/markdown; charset=utf-8", "md"
    elif fmt == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("handoff.json", raw)
            z.writestr("prompts.md", md)
            assets = [("product", get_store().asset(s["product"]["asset_id"])),
                      ("character", character_asset(s["approved"]["3"]["character"], get_store()))]
            for role, meta in assets:
                z.write(meta["path"], role + Path(meta["path"]).suffix)
        content, media, ext = buf.getvalue(), "application/zip", "zip"
    else:
        raise HTTPException(404, "Định dạng không hỗ trợ.")
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})
