"""
数据结构 — PhotoResult 和 DetectionConfig。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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

    # 检测开关标记
    level_enabled: bool = False
    blur_enabled: bool = False
    clarity_enabled: bool = False
    duplicate_enabled: bool = False

    # 错误
    error: Optional[str] = None

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

        if self.error:
            reasons.append(self.error)
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
                reasons.append("闭眼")
            if not self.skin_ok:
                reasons.append("肤色异常")
            if not self.exposure_ok:
                reasons.append("曝光异常")
            if self.level_enabled and not self.level_ok:
                reasons.append("构图倾斜")
            if self.blur_enabled and not self.blur_ok:
                reasons.append("模糊")
            if self.clarity_enabled and not self.clarity_ok:
                reasons.append("人脸模糊")

        return ", ".join(reasons) if reasons else "通过"


@dataclass
class DetectionConfig:
    """运行时检测配置（从 GUI 传入）。"""
    ear_threshold: float = 0.20
    over_threshold: float = 0.05
    under_threshold: float = 0.15
    blur_threshold: float = 40.0
    clarity_threshold: float = 0.5
    duplicate_hamming: int = 5

    # 人脸检测
    enable_face_detection: bool = True       # 启用人脸检测（睁眼+肤色），关闭则仅检曝光

    # 构图检测
    enable_level: bool = False
    level_method: str = "horizon"
    level_angle_tolerance: float = 5.0

    prefer_raw: bool = True               # 重复时优先保留 RAW

    enable_blur: bool = False
    enable_clarity: bool = False
    enable_duplicate: bool = False
