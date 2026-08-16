"""
异步缩略图加载 — 把大图/RAW 解码从主线程移到后台线程池 (v5.1)。

背景：原实现直接在主线程 QPixmap(str(path)) 解码，几千像素大图
或 RAW 文件会卡住界面数秒。此模块用 QRunnable + QThreadPool 在
后台解码（经 utils.image_io.load_thumbnail，RAW 走内嵌 JPEG 快路径），
完成后通过信号把 QImage 交回主线程。
"""

import numpy as np

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Qt
from PySide6.QtGui import QImage

from utils.image_io import load_thumbnail


class PreviewSignals(QObject):
    """预览加载完成信号（跨线程）。"""
    # request_id: 用于丢弃过期请求；path: 文件路径；image: QImage
    loaded = Signal(int, str, object)
    failed = Signal(int, str)


class PreviewLoader(QRunnable):
    """后台缩略图加载任务。"""

    def __init__(self, request_id: int, path: str, size: int = 240):
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.size = size
        self.signals = PreviewSignals()

    def run(self):
        try:
            img = load_thumbnail(self.path, size=self.size)
            if img is None:
                self.signals.failed.emit(self.request_id, self.path)
                return
            img = np.ascontiguousarray(img)
            h, w = img.shape[:2]
            qimg = QImage(img.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self.signals.loaded.emit(self.request_id, self.path, qimg)
        except Exception:
            self.signals.failed.emit(self.request_id, self.path)


class PreviewManager(QObject):
    """
    预览管理器：串行线程池 + 请求序号，保证只显示最新请求的预览。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)   # 最多两个解码线程，避免争抢分析线程
        self._request_id = 0
        # 保活表：QRunnable 默认 autoDelete，任务结束即被删除，其信号对象随之销毁，
        # 跨线程排队中的信号回调可能被丢弃。这里持有引用直到派发完成（v5.1 修复）。
        self._loaders = {}

    def request_preview(self, path: str, size: int = 240, on_loaded=None, on_failed=None):
        """请求异步加载预览。返回 request_id。"""
        self._request_id += 1
        rid = self._request_id
        loader = PreviewLoader(rid, path, size)
        loader.setAutoDelete(False)
        self._loaders[rid] = loader
        loader.signals.loaded.connect(
            lambda r, p, img: self._dispatch(rid, r, p, img, on_loaded))
        loader.signals.failed.connect(
            lambda r, p: self._dispatch_fail(rid, r, p, on_failed))
        self._pool.start(loader)
        return rid

    def _dispatch(self, rid, r, path, img, callback):
        """只回调最新请求（rid 匹配）。"""
        self._loaders.pop(rid, None)
        if callback and rid == r:
            callback(path, img)

    def _dispatch_fail(self, rid, r, path, callback):
        self._loaders.pop(rid, None)
        if callback and rid == r:
            callback(path)
