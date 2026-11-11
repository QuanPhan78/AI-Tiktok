import hashlib
import json
import re
from pathlib import Path
from contracts.handoff_v2 import HandoffV2
from knowledge_base.validator import validate_script
from studio.models import CTA, REFERENCE, TAIL

CHAR_DIR = Path(__file__).resolve().parents[1] / "knowledge_base" / "characters" / "images"


def asset_info(meta):
    return {k: meta[k] for k in ("id", "filename", "sha256", "size", "media_type")}


def character_asset(character, store):
    if character.get("asset_id"):
        return store.asset(character["asset_id"])
    path = CHAR_DIR / character["image_filename"]
    content = path.read_bytes()
    return {"id": character["id"], "filename": path.name, "path": str(path),
            "sha256": hashlib.sha256(content).hexdigest(), "size": len(content), "media_type": "image/png"}


def compile_prompt(character, scene, analysis, plan, dialogue, audio_mode):
    product = (analysis["product_description_en"] + ", exactly as in the attached reference photo, same shape, colors and proportions"
               if scene["product_visible"] else "no product visible in this clip")
    block = character["consistency_block"].replace("[PRODUCT]", product)
    if audio_mode == "voiceover":
        block = re.sub(r"Voice:.*?Product:", "Product:", block)
        sound = "The character does not speak. No dialogue, no voice-over, only quiet natural sounds."
    else:
        who = "He" if character["gender"] == "male" else "She"
        sound = who + " says the line in Vietnamese, once, clearly, at a calm pace, and starts speaking after half a second."
    direction = scene["direction_en"]
    tail = TAIL
    if scene.get("shot_en", "").strip():
        direction = (f"Cinematography: {scene['shot_en']}\nStart: {scene['start_en']}\n"
                     f"Action: {direction}\nEnd: {scene['end_en']}\n"
                     "Natural blinking and relaxed gestures.")
        if audio_mode == "speaking":
            timing = "Start speaking around 0.3 seconds and finish before the last 0.7 seconds."
            if scene["id"] == "4":
                timing = "Start speaking around 0.2 seconds with a natural, slightly brisk pace."
            sound = f"{who} says the line once in Vietnamese, warmly and naturally. {timing}"
        sound += "\nAmbient noise: soft quiet room tone."
        tail = TAIL.replace("Stable pose for the first and last half second.", "Use the same lighting, color tone and camera style across scenes.")
    parts = [block, REFERENCE, "Lighting: " + plan["lighting_en"], "(a) " + direction + " " + sound]
    if audio_mode == "speaking":
        parts.append('(b) "' + dialogue + '"')
    parts.append(tail)
    return "\n".join(parts)


def build_bundle(s, store, revision):
    approved = s["approved"]
    plan = approved["4"]
    char = approved["3"]["character"]
    pub = approved["6"]
    product = s["product"]
    if not product.get("asset_id"):
        raise ValueError("Thiếu ảnh sản phẩm. Quay lại Bước 1 để tải ảnh.")
    try:
        p_asset = store.asset(product["asset_id"])
        c_asset = character_asset(char, store)
    except (KeyError, OSError):
        raise ValueError("Thiếu ảnh tham chiếu. Kiểm tra ảnh sản phẩm ở Bước 1 và nhân vật ở Bước 3.")
    warnings = ["Mỗi clip dự kiến 8 giây; cần kiểm tra giọng nói trong clip thật, đặc biệt câu chốt đơn."]
    warnings.extend(s["quality"].get("warnings", []))
    scenes = []
    for i, scene in enumerate(plan["scenes"], 1):
        line = s["dialogues"][scene["id"]]
        words = len(line.split())
        planned = bool(scene.get("shot_en", "").strip())
        if planned:
            needs_timing_check = scene["id"] != "4" and not 18 <= words <= 24
        else:
            # Reconstruct the exact warnings in previously exported bundles.
            needs_timing_check = not 20 <= words <= 26 or bool(re.search(r"\d", line))
        if needs_timing_check:
            warnings.append(f"Cảnh {scene['id']}: {words} từ, cần kiểm tra nhịp đọc.")
        scenes.append({"id": scene["id"], "order": i, "duration_seconds": 8,
                       "part": scene["part"], "action_vi": scene["action_vi"], "dialogue_vi": line,
                       "prompt_en": compile_prompt(char, scene, approved["1"], plan, line, s["audio_mode"]),
                       "overlay_text": pub["overlay_scene2"] if scene["id"] == "2" else product["price"] if scene["id"] == "4" else ""})
    old_metadata = s.get("bundle", {}).get("metadata", {})
    metadata = {"created_at": s["created_at"], "model_used": s.get("model_used", old_metadata.get("model_used", "unknown")),
                "session_id": s["id"]}
    if "models_by_step" in s:
        metadata["models_by_step"] = dict(s["models_by_step"])
    data = {"schema_version": "2.0", "request_id": s["request_id"], "revision": revision, "status": "success",
            "product": {**{k: product[k] for k in ("name", "uses", "price", "product_link")}, "images": [asset_info(p_asset)]},
            "character": {**{k: char[k] for k in ("id", "name", "age", "gender", "voice", "setting", "outfit", "consistency_block")},
                          "image": asset_info(c_asset), "audio_mode": s["audio_mode"]},
            "scenes": scenes, "publishing": {k: pub[k] for k in ("slogans", "captions", "selected_caption", "hashtags", "pinned_comment")},
            "qc": {"qc_score": s["quality"]["qc_score"], "passed": True, "feedback": s["quality"]["feedback"],
                   "warnings": warnings, "rules_version": "bao-7steps-v2"},
            "metadata": metadata}
    bundle = HandoffV2.model_validate(data).model_dump()
    # Scan rendered/ad copy, not metadata, URLs or diagnostic messages.
    review = {"scenes": [{"dialogue": x["dialogue_vi"], "visual": x["action_vi"], "prompt": x["prompt_en"]} for x in scenes],
              "hashtags": pub["hashtags"], "post_caption": "\n".join(pub["captions"]), "slogans": "\n".join(pub["slogans"]),
              "pinned_comment": pub["pinned_comment"].replace(product["product_link"], ""), "text_on_screen": pub["overlay_scene2"]}
    check = validate_script(review)
    if not check["is_valid"]:
        raise ValueError("Nội dung cần sửa: " + "; ".join(f"{v['field']}: {v['word']}" for v in check["violations"]))
    for meta in (p_asset, c_asset):
        path = Path(meta["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError("Ảnh tham chiếu bị thiếu hoặc thay đổi. Vui lòng tải lại.")
    return bundle


def markdown(bundle):
    lines = ["# Bộ prompt đã duyệt", "", "Sản phẩm: " + bundle["product"]["name"],
             "Mã yêu cầu: " + bundle["request_id"], f"Phiên bản: {bundle['revision']}", ""]
    for s in bundle["scenes"]:
        lines += [f"## Cảnh {s['id']} — {s['part']} — 8 giây", "", "```text", s["prompt_en"], "```", ""]
        if bundle["character"]["audio_mode"] == "voiceover":
            lines += ["Lời thuyết minh riêng: " + s["dialogue_vi"], ""]
        if s["overlay_text"]:
            lines += ["Chữ thêm khi dựng: " + s["overlay_text"], ""]
    pub = bundle["publishing"]
    lines += ["## Caption", "```text", "\n\n".join(pub["captions"]), "```", "", "## Hashtag", "```text",
              " ".join(pub["hashtags"]), "```", "", "## Bình luận ghim và slogan", "```text", pub["pinned_comment"],
              "\n".join(pub["slogans"]), "```", "", "## Lưu ý", *["- " + w for w in bundle["qc"]["warnings"]],
              "", "Mang các prompt cảnh sang công cụ tạo video cùng ảnh nhân vật và ảnh sản phẩm. Chưa có video MP4 được tạo bởi ứng dụng này."]
    return "\n".join(lines)
