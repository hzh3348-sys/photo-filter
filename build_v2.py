"""v2.0 打包脚本 —— 生成便携版文件夹 + zip"""
import subprocess, sys, os, shutil

os.chdir(os.path.dirname(os.path.abspath(__file__)))
IS_CI = os.environ.get("CI") == "true"

# 清理旧产物
for d in ["build", "dist"]:
    p = os.path.join(os.getcwd(), d)
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
for f in ["照片筛选GUI_by_HZH.spec"]:
    fp = os.path.join(os.getcwd(), f)
    if os.path.exists(fp): os.remove(fp)

# 准备依赖包目录
pkg_dir = os.path.join(os.getcwd(), "build_pkgs")
if IS_CI:
    # CI 环境：复用已安装的系统包，直接找 PySide6 插件位置
    import PySide6 as _ps
    plugins_dir = os.path.join(os.path.dirname(_ps.__file__), "plugins")
    env = os.environ.copy()
else:
    # 本地：安装纯净包到 build_pkgs 避免 Anaconda MKL 膨胀
    if os.path.exists(pkg_dir): shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir)
    subprocess.run([sys.executable, "-m", "pip", "install", "--target", pkg_dir,
                    "opencv-python", "mediapipe", "PySide6", "pyinstaller", "--quiet"],
                   check=True)
    plugins_dir = os.path.join(pkg_dir, "PySide6", "plugins")
    env = os.environ.copy()
    env["PYTHONPATH"] = pkg_dir

model_file = os.path.join(os.getcwd(), "face_landmarker.task")
themes_dir = os.path.join(os.getcwd(), "resources", "themes")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir", "--windowed",
    "--name", "照片筛选GUI_v4.0_by_HZH",
    "--icon", os.path.join(os.getcwd(), "app_icon.ico"),
    "--add-data", f"{model_file};.",
    "--add-data", f"{themes_dir};resources/themes",
    "--add-data", f"{plugins_dir}/platforms;PySide6/plugins/platforms",
    "--add-data", f"{plugins_dir}/styles;PySide6/plugins/styles",
    "--hidden-import", "cv2",
    "--hidden-import", "numpy",
    "--hidden-import", "PySide6",
    "--hidden-import", "mediapipe",
    "--hidden-import", "rawpy",
    "--collect-submodules", "mediapipe",
    "--collect-binaries", "mediapipe",
    "--collect-binaries", "rawpy",
    "--exclude-module", "scipy",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide2",
    "--exclude-module", "tkinter",
    "--exclude-module", "jupyter",
    "--exclude-module", "IPython",
    "--exclude-module", "pandas",
    "--exclude-module", "sympy",
    "--exclude-module", "sqlalchemy",
    "--exclude-module", "numba",
    "--exclude-module", "llvmlite",
    "--exclude-module", "mkl",
    "main.py",
]

print("=" * 50)
print("  打包 v4.0 (--onedir 便携模式)")
print("=" * 50)
print(f"  模型: {model_file}")
print(f"  插件: {plugins_dir}")
print()

result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    print('\n'.join(lines[-12:]))

if result.stderr:
    err = result.stderr.strip().split('\n')
    print('\n'.join(err[-5:]))

print(f"\n构建{'成功' if result.returncode == 0 else '失败'} (exit: {result.returncode})")

if result.returncode == 0:
    folder_src = os.path.join(os.getcwd(), "dist", "照片筛选GUI_v4.0_by_HZH")
    folder_dst = os.path.join(os.getcwd(), "照片筛选GUI_v4.0_by_HZH")
    zip_dst = os.path.join(os.getcwd(), "照片筛选GUI_v4.0_by_HZH.zip")

    # 清理旧版
    if os.path.exists(folder_dst): shutil.rmtree(folder_dst, ignore_errors=True)
    if os.path.exists(zip_dst): os.remove(zip_dst)

    shutil.move(folder_src, folder_dst)

    # 计算大小
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(folder_dst) for f in fs)
    print(f"\n[SUCCESS] 程序文件夹: {folder_dst}")
    print(f"   大小: {total / 1024 / 1024:.0f} MB")

    # 打包成 zip
    print("   正在压缩 zip...")
    import zipfile
    with zipfile.ZipFile(zip_dst, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_dst):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, os.getcwd())
                zf.write(full, arcname)
    zip_size = os.path.getsize(zip_dst) / 1024 / 1024
    print(f"   zip 大小: {zip_size:.0f} MB")
    print(f"   zip 路径: {zip_dst}")

    # 清理（CI 模式下跳过）
    if not IS_CI:
        for d in ["build", "dist", "build_pkgs"]:
            p = os.path.join(os.getcwd(), d)
            if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
        print("   临时文件已清理")
