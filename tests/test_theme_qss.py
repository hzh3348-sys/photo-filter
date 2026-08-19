"""UI 主题 QSS 一致性测试 — 守护圆角 token / 关键选择器 / 括号平衡 (v5.3.1)。

不依赖 Qt 实例化，纯文件级校验，防止后续改动破坏两套主题的细节对齐。
"""

from pathlib import Path

THEMES_DIR = Path(__file__).resolve().parent.parent / "resources" / "themes"


def _load(name: str) -> str:
    return (THEMES_DIR / f"{name}.qss").read_text(encoding="utf-8")


def test_qss_brace_balance():
    """两套主题的大括号必须配对，防止样式表被截断。"""
    for name in ("dark", "light"):
        qss = _load(name)
        assert qss.count("{") == qss.count("}"), f"{name}.qss 括号不平衡"


def test_radius_tokens_aligned():
    """圆角 token 对齐：卡片/表格/分组框 12px，常规控件 8px，预览 10px。"""
    for name in ("dark", "light"):
        qss = _load(name)
        assert "border-radius: 12px;" in qss, f"{name}.qss 缺少 12px 大圆角"
        assert "border-radius: 8px;" in qss, f"{name}.qss 缺少 8px 控件圆角"
        assert "border-radius: 10px;" in qss, f"{name}.qss 缺少 10px 预览圆角"
        assert "padding: 6px;" in qss, f"{name}.qss 缺少预览框内边距"


def test_key_selectors_present():
    """v5.3.1 新增/调整的关键选择器必须存在。"""
    for name in ("dark", "light"):
        qss = _load(name)
        for sel in (
            "QFrame#card",
            "QFrame#card:hover",
            "QTableWidget",
            "QHeaderView::section:first",
            "QHeaderView::section:last",
            "QLabel#previewBox",
            "QLabel#emptyHint",
            "QComboBox QFrame",
            "QComboBox QAbstractItemView::item:selected",
            'QLabel#hint[state="run"]',
            'QLabel#hint[state="ok"]',
            'QLabel#hint[state="err"]',
            "QProgressBar::chunk",
        ):
            assert sel in qss, f"{name}.qss 缺少选择器 {sel}"


def test_stat_card_hover_inline_style():
    """汇总卡片的 hover 边框色已内联到主窗口样式。"""
    src = (Path(__file__).resolve().parent.parent / "gui" / "main_window.py")         .read_text(encoding="utf-8")
    assert 'QFrame#statCard:hover' in src, "主窗口缺少 statCard hover 样式"