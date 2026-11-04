"""Browser QA only: fake AI, isolated data, no Notion or model requests.

Run: python -m tests.preview_studio
This is not a real product acceptance or a production startup command.
"""
import os
from pathlib import Path
import uvicorn
from tests.studio_fixtures import FakeGateway


class PreviewGateway(FakeGateway):
    def generate(self, kind, context, schema):
        if kind == "quality":
            name = context["product"]["name"]
            if "QC lỗi API" in name:
                raise RuntimeError("Browser QA simulated outage")
            if "QC chặn" in name:
                return {"qc_score": 8, "feedback": "Kiểm thử lỗi có bằng chứng.", "warnings": [],
                        "issues": [{"field": "dialogues.2", "quote": context["dialogues"]["2"][:35],
                                    "message": "Cần xác nhận căn cứ cho câu này.", "category": "content"}]}
            return {"qc_score": 8, "feedback": "Kiểm thử cảnh báo, không sửa lời thoại.", "issues": [],
                    "warnings": ["Kiểm tra tốc độ nói khi tạo clip thật."]}
        return super().generate(kind, context, schema)

if __name__ == "__main__":
    qa = Path(os.getenv("STUDIO_QA_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "browser-qa")))
    os.environ["STUDIO_DATA_DIR"] = str(qa)
    from api.main import app
    import api.studio as routes
    from studio.service import Studio
    store = routes.get_store()
    routes.get_studio = lambda: Studio(store, PreviewGateway(), lambda url: {
        "status": "unavailable", "message": "Kiểm thử giao diện: không đọc link bên ngoài.", "text": ""})
    print("BROWSER QA ONLY · Fake AI · http://127.0.0.1:8002/app", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
