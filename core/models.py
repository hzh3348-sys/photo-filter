"""
数据结构 — PhotoResult 和 DetectionConfig。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from utils.constants import (
    DEFAULT_EAR_THRESHOLD,
    DEFAULT_OVEREXPOSURE_RATIO,
    DEFAULT_UNDEREXPOSURE_RATIO,
    DEFAULT_BLUR_THRESHOLD,
    DEFAULT_CLARITY_THRESHOLD,
    DEFAULT_DUPLICATE_HAMMING,
    DEFAULT_EXPRESSION_SMILE_THRESHOLD,
    DEFAULT_RED_EYE_THRESHOLD,
)


@dataclass
class PhotoResult:
    """单张照片的检测结果。"""
    path: Path

    # 曝光
    exposure_ok: bool = False
    exposure_score: float = 0.0

    # 肤色
    skin_ok: bool = False
    skin_score: float = 0.0

    # 睁眼
    eyes_open: bool = False
    eye_score: float = 0.0

    # 人脸
    face_detected: bool = False
    face_count: int = 0             # 检测到的人脸数量

    # 构图水平
    level_ok: bool = True
    level_score: float = 1.0

    # 模糊
    blur_ok: bool = True
    blur_score: float = 1.0

    # 人脸清晰度
    clarity_ok: bool = True
    clarity_score: float = 1.0

    # 重复
    is_duplicate_of: Optional[Path] = None
    duplicate_group: int = -1

    # ── v5.0 新增 ──
    # 表情（笑容/自然度）
    expression_ok: bool = True
    expression_score: float = 1.0
    expression_detail: str = ""     # 多人脸时的汇总，如 "3人不笑, 1人张嘴"

    # 红眼
    red_eye_ok: bool = True
    red_eye_score: float = 1.0
    red_eye_count: int = 0          # 红眼人脸数

    # 合照模式信息
    face_count_fail: int = 0        # 不合格人脸数（仅 face_mode="all" 时有意义）
    face_count_total: int = 0       # 总人脸数
    face_detail: str = ""           # 详细描述，如 "1人闭眼, 2人肤色异常"

    # 检测开关标记
    level_enabled: bool = False
    blur_enabled: bool = False
    clarity_enabled: bool = False
    duplicate_enabled: bool = False
    expression_enabled: bool = False
    red_eye_enabled: bool = False

    # 合照模式
    face_mode: str = "best"         # "best" 或 "all"

    # 错误
    error: Optional[str] = None

    # 提示（非错误）：如"未检测到人脸"、"人脸检测已关闭"——不影响通过判定，
    # 也不会作为失败原因展示
    note: Optional[str] = None

    @property
    def all_pass(self) -> bool:
        """综合判断是否通过所有启用的检测。"""
        if self.error and "异常" in self.error:
            return False
        # 重复照片直接不合格
        if self.is_duplicate_of:
            return False

        ok = True

        # 曝光（始终检测）
        ok = ok and self.exposure_ok

        if self.face_detected:
            # 有人脸：睁眼 + 肤色
            ok = ok and self.eyes_open and self.skin_ok
            # 可选：清晰度
            if self.clarity_enabled:
                ok = ok and self.clarity_ok
            # 可选：表情
            if self.expression_enabled:
                ok = ok and self.expression_ok
            # 可选：红眼
            if self.red_eye_enabled:
                ok = ok and self.red_eye_ok

        # 可选检测
        if self.level_enabled:
            ok = ok and self.level_ok
        if self.blur_enabled:
            ok = ok and self.blur_ok

        return ok

    @property
    def fail_reason(self) -> str:
        """人类可读的不合格原因。"""
        reasons = []

        # v5.2: 有错误（检测未完成）时只显示错误本身，
        # 不再叠加默认字段（如曝光 False 导致的"曝光异常"误显示）
        if self.error:
            reasons.append(self.error)
            if self.is_duplicate_of:
                reasons.append(f"重复({self.is_duplicate_of.name})")
            return ", ".join(reasons)

        if self.is_duplicate_of:
            reasons.append(f"重复({self.is_duplicate_of.name})")

        if not self.face_detected:
            if not self.exposure_ok:
                reasons.append("曝光异常")
            if self.level_enabled and not self.level_ok:
                reasons.append("构图倾斜")
            if self.blur_enabled and not self.blur_ok:
                reasons.append("模糊")
            if not reasons:
                reasons.append("无人脸(曝光通过)")
        else:
            if not self.eyes_open:
                if self.face_mode == "all" and self.face_detail:
                    reasons.append(f"闭眼({self.face_detail})")
                else:
                    reasons.append("闭眼")
            if not self.skin_ok:
                if self.face_mode == "all" and self.face_detail:
                    reasons.append(f"肤色异常({self.face_detail})")
                else:
                    reasons.append("肤色异常")
            if not self.exposure_ok:
                reasons.append("曝光异常")
            if self.level_enabled and not self.level_ok:
                reasons.append("构图倾斜")
            if self.blur_enabled and not self.blur_ok:
                reasons.append("模糊")
            if self.clarity_enabled and not self.clarity_ok:
                reasons.append("人脸模糊")
            if self.expression_enabled and not self.expression_ok:
                if self.expression_detail:
                    reasons.append(f"表情({self.expression_detail})")
                else:
                    reasons.append("表情欠佳")
            if self.red_eye_enabled and not self.red_eye_ok:
                reasons.append(f"红眼({self.red_eye_count}人)")

        return ", ".join(reasons) if reasons else "通过"


@dataclass
class DetectionConfig:
    """运行时检测配置（从 GUI 传入）。默认值统一来自 utils/constants.py（单一数据源）。"""
    ear_threshold: float = DEFAULT_EAR_THRESHOLD            # 0.20
    over_threshold: float = DEFAULT_OVEREXPOSURE_RATIO      # 0.50（v5.0 只拦极端过曝）
    under_threshold: float = DEFAULT_UNDEREXPOSURE_RATIO    # 0.50（v5.0 只拦极端欠曝）
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD          # 40.0
    clarity_threshold: float = DEFAULT_CLARITY_THRESHOLD    # 0.5
    duplicate_hamming: int = DEFAULT_DUPLICATE_HAMMING      # 5

    # 人脸检测
    enable_face_detection: bool = True       # 人脸检测总开关（关闭则仅检曝光）
    enable_eyes: bool = True                 # 睁眼检测（v5.3 设置中可独立开关）
    enable_skin: bool = True                 # 肤色检测（v5.3 设置中可独立开关）
    enable_yunet: bool = True                # OpenCV YuNet 双引擎补检（v5.3 设置中可开关）

    # 合照模式: "best" 取最优人脸 / "all" 所有人脸通过才算合格
    face_mode: str = "best"

    # 表情检测（笑容/自然度）
    enable_expression: bool = False
    expression_smile_threshold: float = DEFAULT_EXPRESSION_SMILE_THRESHOLD  # 0.25

    # 红眼检测
    enable_red_eye: bool = False
    red_eye_threshold: float = 0.08          # 眼部红色像素占比阈值

    # 构图检测
    enable_level: bool = False
    level_method: str = "horizon"
    level_angle_tolerance: float = 5.0

    prefer_raw: bool = True               # 重复时优先保留 RAW

    enable_blur: bool = False
    enable_clarity: bool = False
    enable_duplicate: bool = False
