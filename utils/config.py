"""
应用配置管理 — 基于 QSettings 的设置持久化。
"""

from PySide6.QtCore import QSettings

from .constants import (
    DEFAULT_EAR_THRESHOLD, DEFAULT_OVEREXPOSURE_RATIO, DEFAULT_UNDEREXPOSURE_RATIO,
    DEFAULT_BLUR_THRESHOLD, DEFAULT_DUPLICATE_HAMMING, DEFAULT_MAX_WORKERS,
    DEFAULT_EXPRESSION_SMILE_THRESHOLD, DEFAULT_RED_EYE_THRESHOLD,
)


class AppConfig:
    """应用配置单例，封装 QSettings 读写。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = QSettings("PhotoFilter", "PhotoFilterApp")
        return cls._instance

    # ── 阈值 ──────────────────────────────────────────────

    @property
    def ear_threshold(self) -> float:
        return float(self._settings.value("thresholds/ear", DEFAULT_EAR_THRESHOLD))

    @ear_threshold.setter
    def ear_threshold(self, value: float):
        self._settings.setValue("thresholds/ear", value)

    @property
    def over_threshold(self) -> float:
        return float(self._settings.value("thresholds/over", DEFAULT_OVEREXPOSURE_RATIO))

    @over_threshold.setter
    def over_threshold(self, value: float):
        self._settings.setValue("thresholds/over", value)

    @property
    def under_threshold(self) -> float:
        return float(self._settings.value("thresholds/under", DEFAULT_UNDEREXPOSURE_RATIO))

    @under_threshold.setter
    def under_threshold(self, value: float):
        self._settings.setValue("thresholds/under", value)

    @property
    def blur_threshold(self) -> float:
        return float(self._settings.value("thresholds/blur", DEFAULT_BLUR_THRESHOLD))

    @blur_threshold.setter
    def blur_threshold(self, value: float):
        self._settings.setValue("thresholds/blur", value)

    @property
    def duplicate_hamming(self) -> int:
        return int(self._settings.value("thresholds/duplicate", DEFAULT_DUPLICATE_HAMMING))

    @duplicate_hamming.setter
    def duplicate_hamming(self, value: int):
        self._settings.setValue("thresholds/duplicate", value)

    # ── 目录 ──────────────────────────────────────────────

    @property
    def input_dir(self) -> str:
        return self._settings.value("paths/input_dir", "")

    @input_dir.setter
    def input_dir(self, value: str):
        self._settings.setValue("paths/input_dir", value)

    @property
    def output_dir(self) -> str:
        return self._settings.value("paths/output_dir", "")

    @output_dir.setter
    def output_dir(self, value: str):
        self._settings.setValue("paths/output_dir", value)

    # ── 检测选项 ──────────────────────────────────────────

    @property
    def enable_face_detection(self) -> bool:
        return bool(self._settings.value("options/face_detection", True))

    @enable_face_detection.setter
    def enable_face_detection(self, value: bool):
        self._settings.setValue("options/face_detection", value)

    @property
    def enable_level(self) -> bool:
        return bool(self._settings.value("options/level", False))

    @enable_level.setter
    def enable_level(self, value: bool):
        self._settings.setValue("options/level", value)

    @property
    def level_method(self) -> str:
        return self._settings.value("options/level_method", "horizon")

    @level_method.setter
    def level_method(self, value: str):
        self._settings.setValue("options/level_method", value)

    @property
    def level_angle_tolerance(self) -> float:
        return float(self._settings.value("options/level_angle", 5.0))

    @level_angle_tolerance.setter
    def level_angle_tolerance(self, value: float):
        self._settings.setValue("options/level_angle", value)

    @property
    def prefer_raw(self) -> bool:
        return bool(self._settings.value("options/prefer_raw", True))

    @prefer_raw.setter
    def prefer_raw(self, value: bool):
        self._settings.setValue("options/prefer_raw", value)

    # ── 合照模式 ──────────────────────────────────────────

    @property
    def face_mode(self) -> str:
        return self._settings.value("options/face_mode", "best")

    @face_mode.setter
    def face_mode(self, value: str):
        self._settings.setValue("options/face_mode", value)

    # ── 表情检测 ──────────────────────────────────────────

    @property
    def enable_expression(self) -> bool:
        return bool(self._settings.value("options/expression", False))

    @enable_expression.setter
    def enable_expression(self, value: bool):
        self._settings.setValue("options/expression", value)

    @property
    def expression_smile_threshold(self) -> float:
        return float(self._settings.value("thresholds/expression_smile",
                                          DEFAULT_EXPRESSION_SMILE_THRESHOLD))

    @expression_smile_threshold.setter
    def expression_smile_threshold(self, value: float):
        self._settings.setValue("thresholds/expression_smile", value)

    # ── 红眼检测 ──────────────────────────────────────────

    @property
    def enable_red_eye(self) -> bool:
        return bool(self._settings.value("options/red_eye", False))

    @enable_red_eye.setter
    def enable_red_eye(self, value: bool):
        self._settings.setValue("options/red_eye", value)

    @property
    def red_eye_threshold(self) -> float:
        return float(self._settings.value("thresholds/red_eye", DEFAULT_RED_EYE_THRESHOLD))

    @red_eye_threshold.setter
    def red_eye_threshold(self, value: float):
        self._settings.setValue("thresholds/red_eye", value)

    @property
    def enable_blur(self) -> bool:
        return bool(self._settings.value("options/blur", False))

    @enable_blur.setter
    def enable_blur(self, value: bool):
        self._settings.setValue("options/blur", value)

    @property
    def blur_threshold(self) -> float:
        return float(self._settings.value("thresholds/blur", 40.0))

    @blur_threshold.setter
    def blur_threshold(self, value: float):
        self._settings.setValue("thresholds/blur", value)

    @property
    def enable_duplicate(self) -> bool:
        return bool(self._settings.value("options/duplicate", False))

    @enable_duplicate.setter
    def enable_duplicate(self, value: bool):
        self._settings.setValue("options/duplicate", value)

    @property
    def copy_mode(self) -> bool:
        # 默认复制
        return bool(self._settings.value("options/copy_mode", True))

    @copy_mode.setter
    def copy_mode(self, value: bool):
        self._settings.setValue("options/copy_mode", value)

    # ── 首次启动 ──────────────────────────────────────────

    @property
    def first_run(self) -> bool:
        return bool(self._settings.value("ui/first_run", True))

    @first_run.setter
    def first_run(self, value: bool):
        self._settings.setValue("ui/first_run", value)

    # ── UI ──────────────────────────────────────────────────

    @property
    def theme(self) -> str:
        return self._settings.value("ui/theme", "auto")  # 默认跟随系统

    @theme.setter
    def theme(self, value: str):
        self._settings.setValue("ui/theme", value)

    @property
    def window_geometry(self) -> bytes:
        return self._settings.value("ui/window_geometry", b"")

    @window_geometry.setter
    def window_geometry(self, value: bytes):
        self._settings.setValue("ui/window_geometry", value)

    @property
    def window_state(self) -> bytes:
        return self._settings.value("ui/window_state", b"")

    @window_state.setter
    def window_state(self, value: bytes):
        self._settings.setValue("ui/window_state", value)

    # ── 工作线程 ──────────────────────────────────────────

    @property
    def max_workers(self) -> int:
        return int(self._settings.value("performance/max_workers", DEFAULT_MAX_WORKERS))

    @max_workers.setter
    def max_workers(self, value: int):
        self._settings.setValue("performance/max_workers", value)

    def reset_all(self):
        """恢复所有设置为默认值。"""
        self._settings.clear()
