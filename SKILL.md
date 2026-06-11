# 照片筛选工具 - 开发指南

## 项目信息

- **仓库**: https://github.com/hzh3348-sys/photo-filter
- **工作区**: `F:\Claude工程\照片筛选程序`
- **作者**: HZH

## 项目结构

```
├── photo_filter_gui.py          # 主源码 v2.x (GUI 版)
├── photo_filter.py              # 命令行版 v1.0
├── build_v2.py                  # Windows 本地打包
├── macos/build_mac.py           # macOS 本地打包
├── .github/workflows/build.yml  # CI 自动构建 (Win+Mac)
├── face_landmarker.task         # AI 模型
├── app_icon.ico                 # 图标
├── source_v2/                   # v2.0 源码归档
└── 测试GUI.bat                   # 本地开发测试
```

## 开发流程

### 1. 本地修改

```bash
cd "F:\Claude工程\照片筛选程序"
```
编辑 `photo_filter_gui.py`，改完双击 `测试GUI.bat` 验证。

### 2. 本地测试打包

```bash
python build_v2.py
```
产物在 `照片筛选GUI_v2.0_by_HZH/`，约 287MB。

### 3. 提交到 GitHub

确认功能正常后：
```bash
git add photo_filter_gui.py  [改动的文件]
git commit -m "描述你的改动"
git pull origin master       # 先拉取远程更新
git push origin master
```

### 4. 发布新版本

```bash
git tag v2.X -m "版本说明"
git push origin v2.X
```
推送 tag 后 GitHub Actions 自动构建 Windows + macOS 双平台包，发布到 Releases。

## 核心配置

### 检测阈值 (`photo_filter_gui.py`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_EAR` | 0.20 | 睁眼灵敏度 (越小越宽容) |
| `DEFAULT_OVER` | 0.05 | 过曝容忍度 |
| `DEFAULT_UNDER` | 0.15 | 欠曝容忍度 |
| `LEVEL_ANGLE_TOLERANCE` | 9.0 | 构图倾斜容忍度 (°) |
| `LEVEL_CONSISTENCY_THRESHOLD` | 15.0 | 线条一致性阈值 |
| `SKIN_L_MIN/MAX` | 25/230 | 肤色亮度范围 |
| `SKIN_A_MIN/MAX` | 3/35 | 肤色红绿范围 |
| `SKIN_B_MIN/MAX` | 3/45 | 肤色黄蓝范围 |

### MediaPipe 人脸检测阈值

| 参数 | v1.0 | v2.0 |
|------|------|------|
| `min_face_detection_confidence` | 0.5 | 0.4 |
| `min_face_presence_confidence` | 0.5 | 0.3 |
| 图片最大边长 | 1920 | 2400 |

## 常见问题

### 打包后 exe 闪退
1. `matplotlib` 不能排除（MediaPipe 依赖）
2. `PIL` 不能排除
3. 必须 `--collect-binaries mediapipe` 保证 libmediapipe.dll 被打包
4. 中文路径问题：代码已用 `model_asset_buffer` 绕过

### 开发过程出现缓存问题
删除 `__pycache__`、`build`、`dist`、`*.spec` 后重试。

### 每次打包前确保
```bash
rm -rf build_pkgs build dist *.spec
```

## 文件大小参考

| 版本 | Windows 本地 | CI Windows zip | CI macOS zip |
|------|-------------|---------------|-------------|
| v2.x | ~287MB | ~125MB | ~420MB |
