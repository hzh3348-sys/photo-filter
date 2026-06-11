# 照片自动筛选工具 v2.0

自动筛选照片：曝光正确 + 肤色正常 + 睁眼 + 构图水平（可选）

by HZH

## 功能

- **曝光检测**：分析直方图，识别过曝/欠曝照片
- **肤色检测**：MediaPipe 面部关键点采样，LAB 色彩空间判断肤色是否自然
- **睁眼检测**：Eye Aspect Ratio (EAR) 算法，识别闭眼照片
- **构图水平检测**（可选）：Canny + 霍夫变换，智能识别倾斜照片（透视构图不误判）

## 使用方式

### Windows 用户

从 [Releases](../../releases) 下载 `照片筛选GUI_v2.0_by_HZH.zip`，解压后双击 exe 即用。

### macOS 用户

```bash
pip install opencv-python mediapipe PySide6
python photo_filter_gui.py
```

如需打包成 .app：
```bash
python build_mac.py
```

### Linux 用户

```bash
pip install opencv-python mediapipe PySide6
python photo_filter_gui.py
```

## 项目结构

```
├── photo_filter_gui.py        # GUI 版源码 v2.0（跨平台）
├── photo_filter.py            # 命令行版源码 v1.0
├── build_v2.py                # Windows 打包脚本
├── build_mac.py               # macOS 打包脚本
├── app_icon.ico               # 程序图标
├── face_landmarker.task       # MediaPipe 人脸关键点模型
└── 测试GUI.bat                 # 开发测试启动器 (Windows)
```
