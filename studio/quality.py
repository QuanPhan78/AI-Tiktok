"""Ground blocking QC findings in the exact text being reviewed."""
from studio.models import CTA


def review_fields(session, publishing):
    fields = {"dialogues." + sid: text for sid, text in session["dialogues"].items()}
    for key in ("slogans", "captions", "hashtags"):
        fields.update({f"publishing.{key}.{i}": text for i, text in enumerate(publishing[key])})
    for key in ("pinned_comment", "overlay_scene2"):
        fields["publishing." + key] = publishing[key]
    # Preserve the source URL and price with deterministic checks, not semantic
    # ad-copy review. Surrounding pinned-comment prose still needs full QC.
    fields["publishing.pinned_comment"] = publishing["pinned_comment"].replace(
        session["product"]["product_link"], "")
    fields["analysis.product_description_en"] = session["approved"]["1"]["product_description_en"]
    fields["character.consistency_block"] = session["approved"]["3"]["character"]["consistency_block"]
    plan = session["approved"]["4"]
    fields["plan.style_vi"] = plan["style_vi"]
    fields["plan.lighting_en"] = plan["lighting_en"]
    for scene in plan["scenes"]:
        for key in ("action_vi", "idea_vi", "direction_en", "shot_en", "start_en", "end_en"):
            if scene.get(key):
                fields[f"scenes.{scene['id']}.{key}"] = scene[key]
    return fields


def field_label(field):
    parts = field.split(".")
    if parts[0] == "dialogues":
        return "Lời thoại cảnh " + parts[1]
    if parts[0] == "scenes":
        return "Kế hoạch cảnh " + parts[1]
    if parts[:2] == ["publishing", "captions"]:
        return "Caption " + str(int(parts[2]) + 1)
    if parts[:2] == ["publishing", "slogans"]:
        return "Slogan " + str(int(parts[2]) + 1)
    if parts[:2] == ["publishing", "hashtags"]:
        return "Hashtag " + str(int(parts[2]) + 1)
    return {"publishing.pinned_comment": "Bình luận ghim", "publishing.overlay_scene2": "Chữ dựng cảnh 2",
            "publishing.overlay_scene4": "Giá cảnh cuối", "analysis.product_description_en": "Mô tả sản phẩm tiếng Anh",
            "character.consistency_block": "Khối nhân vật", "plan.style_vi": "Phong cách chung",
            "plan.lighting_en": "Ánh sáng"}.get(field, field)


def classify_quality(quality, fields):
    warnings = list(quality.get("warnings", []))
    blocking = []
    for issue in quality["issues"]:
        field, quote = issue["field"], issue["quote"]
        if issue["category"] in ("style", "length"):
            if field == "dialogues.4" and fields.get(field) == CTA:
                warnings.append("Cảnh 4 dùng câu chốt cố định; giữ nguyên và kiểm tra nhịp nói trong clip thật.")
            else:
                warnings.append((field_label(field) + ": " if field in fields else "") + issue["message"])
            continue
        if field not in fields or not quote.strip() or quote not in fields[field]:
            raise ValueError("Kết quả kiểm tra nội dung cần có trích đoạn khớp với cảnh hoặc mục được báo lỗi. Hãy kiểm tra lại trước khi chốt.")
        blocking.append({**issue, "label": field_label(field)})
    return blocking, list(dict.fromkeys(warnings))
