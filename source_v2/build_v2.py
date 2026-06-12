"""v2.0 打包脚本 —— 生成单个 exe 文件"""
import subprocess, sys, os, shutil

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 清理旧产物
for d in ["build", "dist"]:
    p = os.path.join(os.getcwd(), d)
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
for f in ["照片筛选GUI_by_HZH.spec"]:
    fp = os.path.join(os.getcwd(), f)
    if os.path.exists(fp): os.remove(fp)

env = os.environ.copy()
env["PYTHONPATH"] = os.path.join(os.getcwd(), "build_pkgs")

model_file = os.path.join(os.getcwd(), "face_landmarker.task")
plugins_dir = os.path.join(os.getcwd(), "build_pkgs", "PySide6", "plugins")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir", "--windowed",
    "--name", "照片筛选GUI_v2.0_by_HZH",
    "--icon", os.path.join(os.getcwd(), "app_icon.ico"),
    "--add-data", f"{model_file};.",
    "--add-data", f"{plugins_dir}/platforms;PySide6/plugins/platforms",
    "--add-data", f"{plugins_dir}/styles;PySide6/plugins/styles",
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
    "--exclude-module", "tkinter",
    "--exclude-module", "jupyter",
    "--exclude-module", "IPython",
    "--exclude-module", "pandas",
    "--exclude-module", "sympy",
    "--exclude-module", "sqlalchemy",
    "--exclude-module", "numba",
    "--exclude-module", "llvmlite",
    "--exclude-module", "mkl",
    "photo_filter_gui.py",
]

print("=" * 50)
print("  打包 v2.0 (--onefile 单文件模式)")
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
    folder_src = os.path.join(os.getcwd(), "dist", "照片筛选GUI_v2.0_by_HZH")
    folder_dst = os.path.join(os.getcwd(), "照片筛选GUI_v2.0_by_HZH")
    zip_dst = os.path.join(os.getcwd(), "照片筛选GUI_v2.0_by_HZH.zip")

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

    # 清理
    for d in ["build", "dist"]:
        p = os.path.join(os.getcwd(), d)
        if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
    print("   临时文件已清理")
