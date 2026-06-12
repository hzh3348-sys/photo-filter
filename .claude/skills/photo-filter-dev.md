---
name: photo-filter-dev
description: 照片自动筛选工具 GUI 开发规范。当用户提到这个项目、修改筛选逻辑、打包发布时要参考此技能。
metadata:
  type: project
---

# 照片自动筛选工具 - 开发指南 (v3.0)

## 项目信息

- 作者：HZH
- 仓库：https://github.com/hzh3348-sys/photo-filter
- 工作区：`F:\Claude工程\照片筛选程序`
- 版本：v3.0

## 架构概览

```
main.py  →  gui/main_window.py  →  gui/worker.py  →  core/pipeline.py
                (UI层)              (多线程处理)        (检测编排器)
                                                        ↓
                                   core/{exposure, skin_tone, eyes,
                                         level, blur, clarity}.py
```

三层分离：
- **core/** — 纯算法层，零 Qt 依赖，可独立测试
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
- 配置持久化：`utils/config.py` → `AppConfig` 类
- 人脸检测参数：`core/pipeline.py` → `MediaPipeManager._create_landmarker()`
- 并行线程数：`utils/constants.py` → `DEFAULT_MAX_WORKERS`
- 彩蛋：`gui/main_window.py` → `_on_finished()` 魏老师点评
- 主题文件：`resources/themes/light.qss`, `dark.qss`
- 模型路径：`core/pipeline.py` → `_get_model_path()`

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

1. 不能排除 `matplotlib`（MediaPipe 内部依赖）
2. 不能排除 `PIL`（matplotlib 依赖）
3. 必须加 `--collect-binaries mediapipe`
4. 必须加 `--collect-submodules mediapipe`
5. Qt 插件路径：pip 安装的 PySide6 有 `plugins/`
6. 中文路径：已用 `model_asset_buffer` 内存加载绕过
7. `--onedir` 模式（非 `--onefile`）
8. 构建用 PYPI 纯净 numpy（不含 MKL）

## 添加新检测器

1. 在 `core/` 下创建新模块（如 `new_detector.py`）
2. 实现检测函数，返回 `(bool, float)` 元组
3. 在 `core/models.py` 的 `PhotoResult` 中添加对应字段
4. 在 `core/pipeline.py` 的 `detect_single_photo()` 中集成
5. 在 `gui/main_window.py` 的选项组中添加复选框
6. 在 `utils/constants.py` 中添加默认阈值
