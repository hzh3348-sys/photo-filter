"""
图片预览组件 — 异步加载和显示缩略图。
"""

from pathlib import Path

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QImage

from utils.image_io import load_thumbnail


class ThumbnailLoader(QThread):
    """后台加载缩略图的线程。"""
    loaded = Signal(Path, QPixmap)  # original_path, thumbnail

    def __init__(self, path: Path, size: int = 64):
        super().__init__()
        self._path = path
        self._size = size

    def run(self):
        try:
            rgb = load_thumbnail(self._path, self._size)
            if rgb is None:
                return
            h, w = rgb.shape[:2]
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self.loaded.emit(self._path, pixmap)
        except Exception:
            pass


class ThumbnailLabel(QLabel):
    """可显示照片缩略图的标签控件。"""

    def __init__(self, size: int = 64, parent=None):
        super().__init__(parent)
        self._size = size
        self._loader = None
        self._path = None
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ddd; background: #f0f0f0;")
        self.setText("📷")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    @property
    def photo_path(self) -> Path:
        return self._path

    def load_thumbnail(self, path: Path):
        """异步加载指定路径的缩略图。"""
        self._path = path
        if self._loader and self._loader.isRunning():
            self._loader.terminate()
            self._loader.wait()

        self._loader = ThumbnailLoader(path, self._size)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, path: Path, pixmap: QPixmap):
        """缩略图加载完成，更新显示。"""
        if path == self._path:
            scaled = pixmap.scaled(
                self._size, self._size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.setText("")
            self.setStyleSheet("border: 1px solid #ddd; background: transparent;")
