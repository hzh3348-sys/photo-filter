#!/usr/bin/env python3
"""
照片自动筛选工具 v5.2 — 主入口。
"""

import sys
import os as _os

# ── Windows 打包后需要手动指定 Qt 插件路径（macOS 无需）──
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    _os.environ['QT_PLUGIN_PATH'] = _os.path.join(
        _os.path.dirname(sys.executable), '_internal', 'PySide6', 'plugins')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from gui.main_window import MainWindow, create_splash
from utils.config import AppConfig


def main():
    """启动 GUI 应用。"""
    app = QApplication(sys.argv)
    app.setApplicationName("照片筛选工具 v5.2")

    # 高 DPI 适配
    try:
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    # 显示闪屏
    splash = create_splash()
    splash.show()
    app.processEvents()
    splash.showMessage("正在初始化界面...", Qt.AlignHCenter | Qt.AlignBottom, QColor("#888"))
    app.processEvents()

    # 创建主窗口
    window = MainWindow()

    # 首次启动弹出欢迎引导
    config = AppConfig()
    if config.first_run:
        from gui.dialogs.welcome_dialog import WelcomeDialog
        welcome = WelcomeDialog(window)
        welcome.exec()

    splash.showMessage("就绪!", Qt.AlignHCenter | Qt.AlignBottom, QColor("#4CAF50"))
    app.processEvents()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        import traceback
        _log = _os.path.join(_os.path.expanduser("~"), "Desktop", "photo_filter_crash.log")
        with open(_log, "w", encoding="utf-8") as _f:
            _f.write(traceback.format_exc())
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "程序崩溃",
                               f"发生错误，日志已保存到:\n{_log}\n\n{_e}")
        except Exception:
            pass
        raise
