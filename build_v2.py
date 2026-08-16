"""v2.0 打包脚本 —— 生成便携版文件夹 + zip"""
import subprocess, sys, os, shutil

# ── 强制 UTF-8 输出（v5.1 修复）──
# CI 的 cmd 控制台默认 cp1252，print 中文路径/提示会 UnicodeEncodeError 直接崩
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.chdir(os.path.dirname(os.path.abspath(__file__)))
IS_CI = os.environ.get("CI") == "true"

# 清理旧产物
for d in ["build", "dist"]:
    p = os.path.join(os.getcwd(), d)
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)
for f in ["照片筛选GUI_by_HZH.spec"]:
    fp = os.path.join(os.getcwd(), f)
    if os.path.exists(fp): os.remove(fp)

# 直接用系统已安装的包（保证版本与开发环境一致）
# Anaconda: Qt 插件在 <prefix>/Library/plugins，pip: 在 PySide6/plugins/
import PySide6 as _ps
_ps_dir = os.path.dirname(_ps.__file__)
pip_plugins = os.path.join(_ps_dir, "plugins")
conda_plugins = os.path.join(sys.prefix, "Library", "plugins")
plugins_dir = pip_plugins if os.path.exists(pip_plugins) else conda_plugins
env = os.environ.copy()

model_file = os.path.join(os.getcwd(), "face_landmarker.task")
themes_dir = os.path.join(os.getcwd(), "resources", "themes")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir", "--windowed",
    "--name", "照片筛选GUI_v5.2_by_HZH",
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
print("  打包 v5.2 (--onedir 便携模式)")
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
    folder_src = os.path.join(os.getcwd(), "dist", "照片筛选GUI_v5.2_by_HZH")
    folder_dst = os.path.join(os.getcwd(), "照片筛选GUI_v5.2_by_HZH")
    zip_dst = os.path.join(os.getcwd(), "照片筛选GUI_v5.2_by_HZH.zip")

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
