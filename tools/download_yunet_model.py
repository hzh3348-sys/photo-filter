"""下载 YuNet 人脸检测模型到项目根目录（约 232KB，需联网）。

用法:  python tools/download_yunet_model.py
放好后自动启用 MediaPipe + YuNet 双引擎；缺失时程序自动降级为纯 MediaPipe。
"""
import sys
import urllib.request
from pathlib import Path

URL = ("https://github.com/opencv/opencv_zoo/raw/main/"
       "models/face_detection_yunet/face_detection_yunet_2023mar.onnx")
DEST = Path(__file__).resolve().parent.parent / "face_detection_yunet_2023mar.onnx"


def main() -> int:
    print(f"下载: {URL}")
    try:
        urllib.request.urlretrieve(URL, DEST)
    except Exception as e:
        print(f"下载失败: {e}", file=sys.stderr)
        return 1
    print(f"已保存: {DEST} ({DEST.stat().st_size} bytes)")
    print("重启程序后自动启用 YuNet 双引擎。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
