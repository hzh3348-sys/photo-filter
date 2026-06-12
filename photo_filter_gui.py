#!/usr/bin/env python3
"""
照片自动筛选工具 v3.0 - 图形化界面
向后兼容入口：委托给 main.py 启动。
"""

import sys
import os as _os

# ── 确保项目根目录在 sys.path 中（打包和直接运行兼容）──
_project_root = _os.path.dirname(_os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Windows 打包后需要手动指定 Qt 插件路径 ──
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    _os.environ['QT_PLUGIN_PATH'] = _os.path.join(
        _os.path.dirname(sys.executable), '_internal', 'PySide6', 'plugins')

from main import main

if __name__ == "__main__":
    main()
