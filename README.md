# 照片自动筛选工具 v3.0

自动筛选照片：曝光正确 + 肤色正常 + 睁眼 + 构图水平（可选）+ 模糊检测（可选）+ 重复检测（可选）

by HZH

## 新功能 (v3.0)

- **🏎️ 多线程并行处理**：大幅提升大批量照片处理速度
- **🔍 模糊检测**：Laplacian 方差法，自动识别模糊照片
- **👤 人脸清晰度评分**：检测人脸区域的锐度和对比度
- **📋 重复照片检测**：dHash 感知哈希 + 汉明距离，找出相似/重复照片
- **👥 合照多人脸优选**：多人脸时取最优人脸评估
- **🌙 深色模式**：一键切换浅色/深色主题
- **💾 设置持久化**：自动记住阈值、目录、窗口布局
- **🖱️ 拖拽导入**：直接拖拽文件夹到窗口
- **🖼️ 双击预览**：双击结果行用系统默认程序打开原图
- **🧩 模块化架构**：core/gui/utils 分层设计，便于扩展

## 功能

- **曝光检测**：分析直方图，识别过曝/欠曝照片
- **肤色检测**：MediaPipe 面部关键点采样，LAB 色彩空间判断肤色是否自然
- **睁眼检测**：Eye Aspect Ratio (EAR) 算法，识别闭眼照片
- **构图水平检测**（可选）：Canny + 霍夫变换，智能识别倾斜照片（透视构图不误判）
- **模糊检测**（可选）：Laplacian 方差法 + 分区域评估
- **重复检测**（可选）：dHash 感知哈希，识别相似/重复照片
- **人脸清晰度**：专注人脸区域的局部锐度评估

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
├── main.py                    # v3.0 主入口
├── photo_filter_gui.py        # 向后兼容入口（委托给 main.py）
├── photo_filter.py            # 命令行版 v1.0（不再维护）
├── build_v2.py                # Windows 打包脚本
├── macos/build_mac.py         # macOS 打包脚本
├── core/                      # 检测算法层（零 Qt 依赖）
│   ├── pipeline.py            #   检测编排器 + MediaPipe 管理
│   ├── models.py              #   数据模型 (PhotoResult, DetectionConfig)
│   ├── exposure.py            #   曝光检测
│   ├── skin_tone.py           #   肤色检测
│   ├── eyes.py                #   睁眼检测 (EAR)
│   ├── level.py               #   构图水平检测
│   ├── blur.py                #   模糊检测 [NEW]
│   ├── clarity.py             #   人脸清晰度 [NEW]
│   └── duplicate.py           #   重复检测 (dHash) [NEW]
├── gui/                       # 界面层
│   ├── main_window.py         #   主窗口
│   ├── worker.py              #   多线程处理
│   ├── theme_manager.py       #   主题管理器 [NEW]
│   ├── widgets/
│   │   └── image_preview.py   #   缩略图预览 [NEW]
│   └── dialogs/
│       └── settings_dialog.py #   设置对话框 [NEW]
├── utils/                     # 工具层
│   ├── constants.py           #   默认阈值常量
│   ├── config.py              #   QSettings 配置持久化
│   └── image_io.py            #   图片加载（Unicode 路径兼容）
├── resources/themes/          # 主题 QSS [NEW]
│   ├── light.qss
│   └── dark.qss
├── tests/                     # 单元测试 [NEW]
│   ├── test_exposure.py
│   ├── test_eyes.py
│   ├── test_blur.py
│   └── test_duplicate.py
├── app_icon.ico               # 程序图标
├── face_landmarker.task       # MediaPipe 人脸关键点模型
└── 测试GUI.bat                 # 开发测试启动器 (Windows)
```

## 开发

```bash
# 运行测试
pip install pytest
python -m pytest tests/ -v

# 开发测试
双击 测试GUI.bat

# Windows 打包
python build_v2.py
```
