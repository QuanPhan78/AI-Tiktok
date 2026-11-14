from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CTA = "Sản phẩm có ngay trên TikTok Shop, bấm vào giỏ hàng bên dưới góc trái màn hình để tham khảo sản phẩm bên chúng tôi nhé!"
STEP_NAMES = ["Sản phẩm", "Tình huống", "Nhân vật", "Kế hoạch cảnh", "Lời thoại", "Tổng hợp", "Tạo và duyệt video"]
REFERENCE = "Reference images: the attached product photo shows the product, and the attached character image shows the character. Keep the product and the character exactly as shown in these images."
TAIL = "Aspect ratio 9:16. Stable pose for the first and last half second. No music. No watermark, no logo, no icons, no on-screen text, no subtitles."


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Product(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    uses: str = Field(min_length=1, max_length=6000)
    price: str = Field(min_length=1, max_length=100)
    product_link: str = Field(min_length=1, max_length=2000)
    asset_id: str | None = None

    @model_validator(mode="after")
    def required_text(self):
        if any(not getattr(self, k).strip() for k in ("name", "uses", "price", "product_link")):
            raise ValueError("Cần đủ tên, công dụng, giá và link sản phẩm.")
        if not self.product_link.startswith(("https://", "http://")):
            raise ValueError("Link sản phẩm phải bắt đầu bằng http:// hoặc https://.")
        return self


class Character(StrictModel):
    id: str = Field(pattern=r"^NV[1-9][0-9]*$")
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=18, le=100)
    gender: Literal["female", "male"]
    voice: str = Field(min_length=1, max_length=500)
    setting: str = Field(min_length=1, max_length=2000)
    outfit: str = Field(min_length=1, max_length=1000)
    suitable_for: str = Field(min_length=1, max_length=1000)
    consistency_block: str = Field(min_length=50, max_length=6000)
    image_filename: str = ""
    asset_id: str | None = None


class Analysis(StrictModel):
    summary: str = Field(min_length=1, max_length=2500)
    suggestions: list[str] = Field(default_factory=list, max_length=8)
    product_description_en: str = Field(min_length=1, max_length=1200)


class Situation(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=600)
    emotion: str = Field(min_length=1, max_length=200)


class Situations(StrictModel):
    items: list[Situation] = Field(min_length=4, max_length=4)


class Recommendation(StrictModel):
    character_id: str = Field(pattern=r"^NV[1-8]$")
    backup_id: str = Field(pattern=r"^NV[1-8]$")
    reason: str = Field(min_length=1, max_length=1000)


class ScenePlan(StrictModel):
    id: Literal["1", "2", "3", "3A", "3B", "4"]
    part: str = Field(min_length=1, max_length=150)
    action_vi: str = Field(min_length=1, max_length=1500)
    idea_vi: str = Field(min_length=1, max_length=1000)
    direction_en: str = Field(min_length=1, max_length=3000)
    product_visible: bool
    shot_en: str = Field(default="", max_length=500)
    start_en: str = Field(default="", max_length=1000)
    end_en: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def complete_direction(self):
        fields = (self.shot_en.strip(), self.start_en.strip(), self.end_en.strip())
        if any(fields) and not all(fields):
            raise ValueError("Nhập đủ cỡ cảnh, trạng thái đầu và trạng thái cuối.")
        return self


class Plan(StrictModel):
    style_vi: str = Field(min_length=1, max_length=2000)
    lighting_en: str = Field(min_length=1, max_length=300)
    scenes: list[ScenePlan] = Field(min_length=4, max_length=5)

    @model_validator(mode="after")
    def ordered(self):
        ids = [s.id for s in self.scenes]
        if ids not in (["1", "2", "3", "4"], ["1", "2", "3A", "3B", "4"]):
            raise ValueError("Thứ tự cảnh phải là 1,2,3,4 hoặc 1,2,3A,3B,4.")
        return self


class Dialogue(StrictModel):
    text: str = Field(min_length=1, max_length=2000)


class Publishing(StrictModel):
    slogans: list[str] = Field(min_length=5, max_length=5)
    captions: list[str] = Field(min_length=3, max_length=3)
    hashtags: list[str] = Field(min_length=8, max_length=10)
    pinned_comment: str = Field(min_length=1, max_length=3000)
    overlay_scene2: str = Field(min_length=1, max_length=500)
    overlay_scene4: str = Field(min_length=1, max_length=100)
    selected_caption: int = Field(default=0, ge=0, le=2)


class QualityIssue(StrictModel):
    field: str = Field(min_length=1, max_length=160)
    quote: str = Field(min_length=1, max_length=3000)
    message: str = Field(min_length=1, max_length=1500)
    category: Literal["content", "style", "length"] = "content"


class Quality(StrictModel):
    qc_score: float = Field(ge=0, le=10)
    feedback: str = Field(max_length=3000)
    issues: list[QualityIssue] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)


class Action(StrictModel):
    revision: int = Field(ge=0)
    operation_id: str = Field(min_length=1, max_length=100)
    action: Literal["generate", "approve", "revise", "reopen", "handoff", "submit_video_review", "refresh_video_review"]
    data: dict = Field(default_factory=dict)
