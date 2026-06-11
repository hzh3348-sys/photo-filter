"""macOS 打包脚本 —— 生成 .app 应用程序"""
import subprocess, sys, os, shutil

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 回到项目根目录

# 确认在 macOS 上运行
if sys.platform != 'darwin':
    print("错误: 此脚本仅在 macOS 上运行")
    print("Windows 用户请使用 build_v2.py")
    sys.exit(1)

# 清理旧产物
for d in ["build", "dist"]:
    p = os.path.join(os.getcwd(), d)
    if os.path.exists(p):
        shutil.rmtree(p, ignore_errors=True)
for f in os.listdir(os.getcwd()):
    if f.endswith('.spec'):
        os.remove(os.path.join(os.getcwd(), f))

# 安装依赖
pkg_dir = os.path.join(os.getcwd(), "build_pkgs_mac")
if os.path.exists(pkg_dir):
    shutil.rmtree(pkg_dir)
os.makedirs(pkg_dir)

print("正在安装依赖（首次运行需几分钟）...")
subprocess.run([sys.executable, "-m", "pip", "install",
                "--target", pkg_dir,
                "opencv-python", "mediapipe", "PySide6", "pyinstaller", "--quiet"],
               check=True)

env = os.environ.copy()
env["PYTHONPATH"] = pkg_dir

model_file = os.path.join(os.getcwd(), "face_landmarker.task")
icon_file = os.path.join(os.getcwd(), "app_icon.ico")
# macOS 用 .icns 格式更佳，没有的话用 .ico 也能凑合

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir", "--windowed",
    "--name", "照片筛选工具",
    "--add-data", f"{model_file}:.",
]
if os.path.exists(icon_file):
    cmd += ["--icon", icon_file]

cmd += [
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "PySide6",
    "--hidden-import", "mediapipe",
    "--collect-submodules", "mediapipe",
    "--collect-binaries", "mediapipe",
    "--exclude-module", "scipy",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PIL",
    "--exclude-module", "matplotlib",
    "--exclude-module", "mkl",
    "photo_filter_gui.py",
]

print("\n正在构建 .app ...")
result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    print('\n'.join(lines[-10:]))
if result.stderr and result.returncode != 0:
    print("错误:", result.stderr[-1000:])

if result.returncode != 0:
    print("\n构建失败")
    sys.exit(1)

# 产物位置
app_path = os.path.join(os.getcwd(), "dist", "照片筛选工具.app")
if os.path.exists(app_path):
    # 计算大小
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(app_path) for f in fs)
    print(f"\n构建成功!")
    print(f"App: {app_path}")
    print(f"大小: {total / 1024 / 1024:.0f} MB")
    print(f"\n分享方式:")
    print(f"  1. 右键 {os.path.basename(app_path)} → 压缩")
    print(f"  2. 把 zip 发给别人")
    print(f"  3. 对方解压后双击即用")
else:
    print("\n构建可能失败，未找到 .app")
    sys.exit(1)

# 清理临时文件
shutil.rmtree(pkg_dir, ignore_errors=True)
for d in ["build"]:
    p = os.path.join(os.getcwd(), d)
    if os.path.exists(p):
        shutil.rmtree(p, ignore_errors=True)
print("完成")
