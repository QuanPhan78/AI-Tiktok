"""SQLite transactions guard revisions and operation IDs before any AI call."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def data_dir():
    return Path(os.getenv("STUDIO_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "studio.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, body TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations(session_id TEXT, id TEXT, request TEXT, status TEXT,
              before_body TEXT, error TEXT, PRIMARY KEY(session_id,id));
            CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,session_id TEXT,operation TEXT,created TEXT,body TEXT);
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,body TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def dump(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def create(self, product):
        sid = str(uuid.uuid4())
        s = {"id": sid, "request_id": "vid_" + sid.replace("-", ""), "revision": 0,
             "step": 1, "status": "awaiting_input", "product": product, "draft": None,
             "approved": {}, "dialogues": {}, "scene_cursor": 0, "audio_mode": "speaking",
             "warnings": [], "validation": [], "handoff": None, "created_at": now(), "updated_at": now()}
        with self.db() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (sid, self.dump(s), s["updated_at"]))
        return s

    def get(self, sid):
        with self.db() as db:
            row = db.execute("SELECT body FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            raise KeyError(sid)
        return json.loads(row[0])

    def list(self):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM sessions ORDER BY updated DESC LIMIT 200")]

    def claim(self, sid, request):
        encoded = self.dump(request)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                raise KeyError(sid)
            s = json.loads(row[0])
            op = db.execute("SELECT request FROM operations WHERE session_id=? AND id=?", (sid, request["operation_id"])).fetchone()
            if op:
                if op[0] != encoded:
                    raise Conflict("Mã thao tác đã được dùng cho nội dung khác.")
                return s, False
            if request["revision"] != s["revision"]:
                raise Conflict("Phiên đã thay đổi. Hãy tải lại trước khi thao tác.")
            if s["status"] == "processing":
                raise Conflict("Phiên đang xử lý một tác vụ. Vui lòng đợi.")
            before = self.dump(s)
            s.update(status="processing", error=None, active_operation=request["operation_id"], updated_at=now())
            s["revision"] += 1
            db.execute("INSERT INTO operations VALUES(?,?,?,?,?,NULL)", (sid, request["operation_id"], encoded, "running", before))
            db.execute("INSERT INTO history(session_id,operation,created,body) VALUES(?,?,?,?)", (sid, encoded, now(), before))
            db.execute("UPDATE sessions SET body=?,updated=? WHERE id=?", (self.dump(s), now(), sid))
        return json.loads(before), True

    def finish(self, sid, opid, result=None, error=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            op = db.execute("SELECT before_body,status FROM operations WHERE session_id=? AND id=?", (sid, opid)).fetchone()
            if not op or op[1] != "running":
                return
            old = json.loads(op[0])
            s = result if result is not None else old
            s.update(revision=old["revision"] + 1, updated_at=now())
            s.pop("active_operation", None)
            if error:
                s.update(status="error", error=error)
            db.execute("UPDATE sessions SET body=?,updated=? WHERE id=?", (self.dump(s), now(), sid))
            db.execute("UPDATE operations SET status=?,error=? WHERE session_id=? AND id=?", ("failed" if error else "done", error, sid, opid))

    def recover(self):
        with self.db() as db:
            pending = db.execute("SELECT session_id,id FROM operations WHERE status='running'").fetchall()
        for r in pending:
            self.finish(r[0], r[1], error="Tác vụ bị gián đoạn khi server dừng. Nội dung đã duyệt được giữ nguyên; hãy thử lại.")

    def history(self, sid):
        self.get(sid)
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT id,operation,created,body FROM history WHERE session_id=? ORDER BY id", (sid,))]

    def asset(self, aid):
        with self.db() as db:
            row = db.execute("SELECT body FROM assets WHERE id=?", (aid,)).fetchone()
        if not row:
            raise KeyError(aid)
        return json.loads(row[0])

    def save_asset(self, meta):
        with self.db() as db:
            db.execute("INSERT INTO assets VALUES(?,?)", (meta["id"], self.dump(meta)))

    def attach_video(self, sid, expected_revision, meta):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                raise KeyError(sid)
            s = json.loads(row[0])
            if (s["revision"] != expected_revision or s["status"] == "processing" or
                    s["step"] != 7 or not s.get("bundle")):
                raise Conflict("Cần mở đúng phiên đã chốt Bước 7. Hãy tải lại trang trước khi gắn video.")
            current = s.get("video") or {}
            bundle_revision = s["bundle"]["revision"]
            if (current.get("bundle_revision") == bundle_revision and current.get("sha256") == meta["sha256"]
                    and self.video_path(current).is_file()):
                return s, False
            stamp = now()
            db.execute("INSERT INTO history(session_id,operation,created,body) VALUES(?,?,?,?)",
                       (sid, self.dump({"action": "attach_video"}), stamp, row[0]))
            s.update(video={**meta, "version": current.get("version", 0) + 1,
                            "bundle_revision": bundle_revision, "status": "ATTACHED"},
                     revision=s["revision"] + 1, updated_at=stamp, status="ready", error=None)
            db.execute("UPDATE sessions SET body=?,updated=? WHERE id=?", (self.dump(s), stamp, sid))
        return s, True

    def video_path(self, video):
        return self.path.parent / "videos" / (video["id"] + ".mp4")
