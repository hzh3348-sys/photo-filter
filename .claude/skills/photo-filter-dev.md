---
name: photo-filter-dev
description: 照片自动筛选工具 GUI 开发规范。当用户提到这个项目、修改筛选逻辑、打包发布时要参考此技能。
metadata:
  type: project
---

# 照片自动筛选工具 - 开发指南 (v4.0)

## 项目信息

- 作者：HZH
- 仓库：https://github.com/hzh3348-sys/photo-filter
- 版本：v4.0

## 架构概览

```
main.py (入口) → gui/main_window.py (UI) → gui/worker.py (多线程)
                       ↓                         ↓
                  gui/theme_manager.py     core/pipeline.py (编排器)
                  gui/dialogs/                  ↓
                  gui/widgets/          core/{exposure, skin_tone, eyes,
                                              level, blur, clarity, duplicate}.py

utils/{constants, config, image_io}.py  ← 被所有层引用
resources/themes/{light, dark}.qss      ← theme_manager 加载
```

三层分离：
- **core/** — 纯算法层，零 Qt 依赖，可独立测试（29 个 pytest）
- **gui/** — PySide6 界面层
- **utils/** — 工具层（配置、常量、图片I/O）

## 文件职责

### 核心检测 (core/)
| 文件 | 功能 | 关键函数 |
|------|------|----------|
| `pipeline.py` | 编排器 + MediaPipe 管理 | `detect_single_photo()`, `MediaPipeManager` |
| `models.py` | 数据模型 | `PhotoResult`, `DetectionConfig` |
| `exposure.py` | 曝光检测 | `check_exposure(img, over_th, under_th)` |
| `skin_tone.py` | 肤色检测 (LAB中位数) | `check_skin_tone(img, landmarks)` |
| `eyes.py` | 睁眼检测 (EAR) | `check_eyes_open(landmarks, shape, ear_th)` |
| `level.py` | 构图水平 (地平线/通用) | `check_level(img, method, angle)` — method="horizon"(推荐) 或 "general" |
| `blur.py` | 模糊检测 (Laplacian) | `check_blur(img, threshold)` |
| `clarity.py` | 人脸清晰度 | `check_face_clarity(img, landmarks, threshold)` |
| `duplicate.py` | 重复检测 (dHash) | `compute_dhash()`, `find_duplicates()` |

### GUI (gui/)
| 文件 | 功能 |
|------|------|
| `main_window.py` | 主窗口，所有 UI 控件和槽函数 |
| `worker.py` | 多线程处理 (ThreadPoolExecutor) |
| `theme_manager.py` | 浅色/深色主题切换 |
| `widgets/image_preview.py` | 缩略图预览组件 |
| `dialogs/settings_dialog.py` | 设置对话框 |

### 工具 (utils/)
| 文件 | 功能 |
|------|------|
| `constants.py` | 所有默认阈值和配置常量 |
| `config.py` | QSettings 持久化封装 (AppConfig 单例) |
| `image_io.py` | Unicode 路径兼容的图片加载 |

## 关键代码位置

- 检测阈值常量：`utils/constants.py`
- 配置持久化：`utils/config.py` → `AppConfig` 单例类
- 人脸检测参数：`core/pipeline.py` → `MediaPipeManager._create_landmarker()` (min_face_detection_confidence=0.25)
- 小脸两轮检测：`core/pipeline.py` → `_detect_faces()` (首轮原图，次轮放大到 1200px)
- 人脸检测开关：`DetectionConfig.enable_face_detection` → 关闭时跳过 MediaPipe
- 模糊算法：`core/blur.py` → 4×4 网格 + 取前 25% 最清晰区域均值（浅景深不误判）
- 地平线检测：`core/level.py` → `check_level_horizon()` (只找长水平线，聚类判断)
- 并行线程数：`utils/constants.py` → `DEFAULT_MAX_WORKERS` (=2)
- 苹果拨动开关：`gui/widgets/toggle_switch.py` → `ToggleSwitch` (动画 + 仅44px可点击)
- 欢迎引导：`gui/dialogs/welcome_dialog.py` → 首次启动弹出 (AppConfig.first_run)
- 实时预览：`gui/main_window.py` → `preview_label` (处理中右侧显示)
- 汇总卡片：`gui/main_window.py` → `summary_cards` (绿/红/橙三色统计)
- 彩蛋：`gui/main_window.py` → `_on_finished()` → 有人脸时合格率 <30% 或 >80% 弹魏老师点评
- 主题文件：`resources/themes/light.qss`, `dark.qss`
- 跟随系统主题：`gui/theme_manager.py` → `_detect_system_theme()` (Qt ColorScheme)
- 模型路径：`core/pipeline.py` → `_get_model_path()` (frozen 模式兼容 PyInstaller)
- 退出确认：`gui/main_window.py` → `closeEvent()` (分析中关闭弹确认框)

## 开发流程

### 第一步：本地改代码
编辑对应模块文件 → 双击 `测试GUI.bat` 验证。

### 第二步：运行测试
```bash
python -m pytest tests/ -v
```

### 第三步：本地打包验证
```bash
python build_v2.py
```
产物在 `照片筛选GUI_v3.0_by_HZH/`（需更新 build_v2.py 中的名称）。

### 第四步：提交 + 发布
```bash
git add <改动文件>
git commit -m "描述改动"
git tag v3.X -m "版本说明"
git push origin master
git push origin v3.X
```

## 打包注意事项

1. **入口**：用 `main.py`（非 `photo_filter_gui.py`），PyInstaller 自动追踪所有导入
2. **不要**加 `--hidden-import` 给自定义模块（冗余且可能导致 CI 失败），PyInstaller 会追踪 `main.py` 的导入链
3. **资源文件**：`--add-data "resources/themes;resources/themes"` (Win) 或 `:resources/themes` (Mac)
4. 不能排除 `matplotlib`（MediaPipe 内部依赖），不能排除 `PIL`
5. 必须加 `--collect-binaries mediapipe` 和 `--collect-submodules mediapipe`
6. Qt 插件路径：pip 安装的 PySide6 有 `plugins/`，Anaconda 的没有
7. 中文路径：已用 `model_asset_buffer` 内存加载绕过 MediaPipe C++ 路径问题
8. `--onedir` 模式（`--onefile` 有 DLL 加载问题）
9. 构建用 PYPI 纯净 numpy（不含 MKL），否则体积暴增 250MB+
10. CI 构建失败常见原因：`--hidden-import` 冗余/错误、资源路径不存在、入口文件不对

## 添加新检测器

1. 在 `core/` 下创建新模块（如 `new_detector.py`）
2. 实现检测函数，返回 `(bool, float)` 元组
3. 在 `core/models.py` 的 `PhotoResult` 中添加对应字段
4. 在 `core/pipeline.py` 的 `detect_single_photo()` 中集成
5. 在 `gui/main_window.py` 的选项组中添加复选框
6. 在 `utils/constants.py` 中添加默认阈值
