#!/usr/bin/env python3
"""
自动筛选照片：曝光正确 + 肤色正常 + 睁眼
双击运行后根据提示输入即可，也可以命令行传参:
  python photo_filter.py <照片文件夹> [--output <输出文件夹>] [--copy]
"""

import os
import sys
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# ── 模型文件路径（兼容 exe 打包和直接运行） ──────────────────
def _get_model_path() -> Path:
    """获取模型文件路径，兼容 PyInstaller 打包和直接运行。"""
    # PyInstaller 打包后，数据文件在 sys._MEIPASS 中
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "face_landmarker.task"

MODEL_PATH = _get_model_path()

# ── 配置常量 ──────────────────────────────────────────────
OVEREXPOSURE_RATIO_THRESHOLD = 0.05
UNDEREXPOSURE_RATIO_THRESHOLD = 0.15

SKIN_L_MIN, SKIN_L_MAX = 50, 220
SKIN_A_MIN, SKIN_A_MAX = 5, 30
SKIN_B_MIN, SKIN_B_MAX = 5, 40

EAR_THRESHOLD = 0.20

# 左眼关键点索引: 33, 133, 157, 158, 159, 160, 161, 173
LEFT_EYE_IDX  = [33, 133, 157, 158, 159, 160, 161, 173]
# 右眼关键点索引: 362, 263, 384, 385, 386, 387, 388, 398
RIGHT_EYE_IDX = [362, 263, 384, 385, 386, 387, 388, 398]

# 肤色采样区域（额头、脸颊、下巴等避开眼嘴的区域）
FACE_SKIN_IDX = [
    10, 67, 69, 108, 109, 151, 299, 337, 338,           # 额头
    50, 101, 117, 118, 119, 123, 126, 142, 187, 203, 205, 206, 207,  # 左脸颊
    280, 329, 330, 346, 347, 348, 355, 371, 411, 423, 425, 426, 427,  # 右脸颊
    152, 169, 170, 199, 200, 201, 208, 210, 211,         # 下巴
]


# ── 数据结构 ──────────────────────────────────────────────
@dataclass
class PhotoResult:
    path: Path
    exposure_ok: bool = False
    exposure_score: float = 0.0
    skin_ok: bool = False
    skin_score: float = 0.0
    eyes_open: bool = False
    eye_score: float = 0.0
    face_detected: bool = False
    error: Optional[str] = None

    @property
    def all_pass(self) -> bool:
        if self.face_detected:
            # 有人脸：曝光 + 肤色 + 睁眼 全部通过
            return self.exposure_ok and self.skin_ok and self.eyes_open
        else:
            # 无人脸：只看曝光
            return self.exposure_ok


# ── 曝光检测 ──────────────────────────────────────────────
def check_exposure(img: np.ndarray) -> tuple[bool, float]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    total = gray.size
    over_ratio = np.sum(gray > 250) / total
    under_ratio = np.sum(gray < 15) / total

    ok = (over_ratio < OVEREXPOSURE_RATIO_THRESHOLD and
          under_ratio < UNDEREXPOSURE_RATIO_THRESHOLD)

    over_penalty = max(0, 1 - over_ratio / OVEREXPOSURE_RATIO_THRESHOLD)
    under_penalty = max(0, 1 - under_ratio / UNDEREXPOSURE_RATIO_THRESHOLD)
    score = min(over_penalty, under_penalty)
    return ok, score


# ── 肤色检测 ──────────────────────────────────────────────
def check_skin_tone(img: np.ndarray, face_landmarks) -> tuple[bool, float]:
    """
    face_landmarks: list of NormalizedLandmark (新版 API 直接就是 list)
    """
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

    skin_pixels = []
    for idx in FACE_SKIN_IDX:
        if idx < len(face_landmarks):
            lm = face_landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            if 0 <= x < w and 0 <= y < h:
                skin_pixels.append(lab[y, x])

    if len(skin_pixels) < 5:
        return False, 0.0

    skin = np.array(skin_pixels)
    L_mean, A_mean, B_mean = np.mean(skin[:, 0]), np.mean(skin[:, 1]), np.mean(skin[:, 2])

    l_ok = SKIN_L_MIN <= L_mean <= SKIN_L_MAX
    a_ok = SKIN_A_MIN <= A_mean <= SKIN_A_MAX
    b_ok = SKIN_B_MIN <= B_mean <= SKIN_B_MAX
    skin_ok = l_ok and a_ok and b_ok

    l_center = (SKIN_L_MIN + SKIN_L_MAX) / 2
    a_center = (SKIN_A_MIN + SKIN_A_MAX) / 2
    b_center = (SKIN_B_MIN + SKIN_B_MAX) / 2
    l_score = max(0, 1 - abs(L_mean - l_center) / ((SKIN_L_MAX - SKIN_L_MIN) / 2))
    a_score = max(0, 1 - abs(A_mean - a_center) / ((SKIN_A_MAX - SKIN_A_MIN) / 2))
    b_score = max(0, 1 - abs(B_mean - b_center) / ((SKIN_B_MAX - SKIN_B_MIN) / 2))
    score = (l_score + a_score + b_score) / 3

    return skin_ok, score


# ── 睁眼检测 ──────────────────────────────────────────────
def eye_aspect_ratio(eye_points: np.ndarray) -> float:
    v1 = np.linalg.norm(eye_points[1] - eye_points[7])
    v2 = np.linalg.norm(eye_points[2] - eye_points[6])
    v3 = np.linalg.norm(eye_points[3] - eye_points[5])
    h = np.linalg.norm(eye_points[0] - eye_points[4])
    if h < 1e-7:
        return 0.0
    return (v1 + v2 + v3) / (3.0 * h)


def check_eyes_open(face_landmarks, img_shape) -> tuple[bool, float]:
    h, w = img_shape[:2]

    def get_eye_points(indices):
        pts = []
        for i in indices:
            lm = face_landmarks[i]
            pts.append([lm.x * w, lm.y * h])
        return np.array(pts)

    left_ear = eye_aspect_ratio(get_eye_points(LEFT_EYE_IDX))
    right_ear = eye_aspect_ratio(get_eye_points(RIGHT_EYE_IDX))
    avg_ear = (left_ear + right_ear) / 2

    eyes_open = (left_ear >= EAR_THRESHOLD) and (right_ear >= EAR_THRESHOLD)
    return eyes_open, avg_ear


# ── 主处理流程 ─────────────────────────────────────────────
def process_photo(img_path: Path, landmarker, mp_image_cls, mp_image_format) -> PhotoResult:
    """处理单张照片，返回完整检测结果。"""
    result = PhotoResult(path=img_path)

    # imdecode 支持中文路径（cv2.imread 在 Windows 上不支持 Unicode）
    with open(img_path, 'rb') as f:
        img_bytes = f.read()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        result.error = "无法读取图片"
        return result

    h, w = img.shape[:2]
    max_dim = 1920
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    # 1. 曝光检测
    result.exposure_ok, result.exposure_score = check_exposure(img)

    # 2. 人脸检测（新版 API）
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp_image_cls(image_format=mp_image_format.SRGB, data=rgb)
    face_result = landmarker.detect(mp_image)

    if not face_result.face_landmarks:
        result.error = "未检测到人脸"
        return result

    result.face_detected = True
    face_landmarks = face_result.face_landmarks[0]  # 取第一张脸

    # 3. 睁眼检测
    result.eyes_open, result.eye_score = check_eyes_open(face_landmarks, img.shape)

    # 4. 肤色检测
    result.skin_ok, result.skin_score = check_skin_tone(img, face_landmarks)

    return result


# ── 创建 MediaPipe FaceLandmarker ──────────────────────────
def create_landmarker():
    """初始化新版 MediaPipe FaceLandmarker。"""
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
    from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

    if not MODEL_PATH.exists():
        print(f"\n[错误] 找不到模型文件: {MODEL_PATH}")
        print("请确保 face_landmarker.task 与 photo_filter.py 在同一目录。")
        safe_input("\n按 Enter 键退出...")
        sys.exit(1)

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    return FaceLandmarker.create_from_options(options)


# ── 交互式输入 ─────────────────────────────────────────────
def safe_input(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n已取消。")
        sys.exit(0)
    return val if val else default


def interactive_main():
    print("=" * 50)
    print("  照片自动筛选工具")
    print("  曝光正确 + 肤色正常 + 睁眼")
    print("=" * 50)
    print()

    # 1. 输入文件夹
    while True:
        folder = safe_input("请输入照片文件夹路径: ").strip('"').strip("'")
        input_dir = Path(folder)
        if input_dir.is_dir():
            break
        print(f"  [错误] '{folder}' 不是有效文件夹，请重新输入。\n")

    # 2. 阈值设置
    print()
    print("-- 检测阈值设置（直接回车使用默认值）--")

    global EAR_THRESHOLD, OVEREXPOSURE_RATIO_THRESHOLD, UNDEREXPOSURE_RATIO_THRESHOLD

    ear_str = safe_input(f"  睁眼灵敏度 (0.15~0.25, 默认 {EAR_THRESHOLD}, 越小越宽容): ")
    if ear_str:
        try:
            EAR_THRESHOLD = float(ear_str)
        except ValueError:
            print(f"    输入无效，使用默认值 {EAR_THRESHOLD}")

    over_str = safe_input(f"  过曝容忍度 (0.01~0.20, 默认 {OVEREXPOSURE_RATIO_THRESHOLD}, 越大越宽容): ")
    if over_str:
        try:
            OVEREXPOSURE_RATIO_THRESHOLD = float(over_str)
        except ValueError:
            print(f"    输入无效，使用默认值 {OVEREXPOSURE_RATIO_THRESHOLD}")

    under_str = safe_input(f"  欠曝容忍度 (0.05~0.40, 默认 {UNDEREXPOSURE_RATIO_THRESHOLD}, 越大越宽容): ")
    if under_str:
        try:
            UNDEREXPOSURE_RATIO_THRESHOLD = float(under_str)
        except ValueError:
            print(f"    输入无效，使用默认值 {UNDEREXPOSURE_RATIO_THRESHOLD}")

    # 3. 输出设置
    print()
    output_folder = safe_input("输出合格照片到文件夹? (直接回车跳过): ").strip('"').strip("'")
    do_copy = False
    if output_folder:
        choice = safe_input("复制(c)还是移动(m)? 默认复制: ").lower()
        do_copy = choice != "m"

    # 4. 扫描照片
    extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
    photo_paths = sorted([
        p for p in input_dir.iterdir()
        if p.suffix.lower() in extensions and p.is_file()
    ])

    if not photo_paths:
        print(f"\n[错误] 在 '{input_dir}' 中未找到照片文件")
        safe_input("\n按 Enter 键退出...")
        sys.exit(1)

    print(f"\n找到 {len(photo_paths)} 张照片，开始分析...\n")

    # 5. 初始化 MediaPipe
    print("正在加载 AI 模型...")
    landmarker = create_landmarker()
    import mediapipe as mp
    from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat
    print("模型加载完成!\n")

    # 6. 逐张处理
    results = []
    for i, p in enumerate(photo_paths, 1):
        try:
            result = process_photo(p, landmarker, MPImage, ImageFormat)
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = PhotoResult(path=p, error=f'处理异常: {e}')

        status = "[OK]" if result.all_pass else "[NG]"
        details = []
        if not result.face_detected:
            details.append("无人脸(仅检曝光)")
        else:
            details.append(f"EAR={result.eye_score:.3f}({'睁' if result.eyes_open else '闭'})")
            details.append(f"肤色={result.skin_score:.2f}")
        details.append(f"曝光={result.exposure_score:.2f}({'OK' if result.exposure_ok else 'NG'})")
        if result.error:
            details.append(result.error)
        print(f"  [{i:4d}/{len(photo_paths)}] {status} {p.name}  |  {', '.join(details)}")

        results.append(result)

    landmarker.close()

    # 7. 汇总
    passed = [r for r in results if r.all_pass]
    failed = [r for r in results if not r.all_pass]
    no_face = [r for r in results if not r.face_detected]
    no_face_pass = [r for r in no_face if r.all_pass]
    no_face_fail = [r for r in no_face if not r.all_pass]
    has_face_closed_eyes = [r for r in results if r.face_detected and not r.eyes_open]
    has_face_bad_skin = [r for r in results if r.face_detected and not r.skin_ok]
    bad_exposure = [r for r in results if not r.exposure_ok]

    print()
    print("=" * 50)
    print("  筛选结果")
    print("=" * 50)
    print(f"  总计: {len(results)} 张")
    if len(results) > 0:
        print(f"  [合格] {len(passed)} 张 ({len(passed)/len(results)*100:.1f}%)")
        print(f"  [不合格] {len(failed)} 张")
        if no_face:
            print(f"     +-- 无人脸(仅检曝光): {len(no_face_pass)} 合格 / {len(no_face_fail)} 不合格")
        print(f"     +-- 闭眼:         {len(has_face_closed_eyes)} 张")
        print(f"     +-- 肤色异常:     {len(has_face_bad_skin)} 张")
        print(f"     +-- 曝光异常:     {len(bad_exposure)} 张")

    # 8. 不合格详情
    if failed:
        print()
        print("-" * 50)
        print("  不合格照片详情:")
        for r in failed:
            reasons = []
            if not r.face_detected:
                reasons.append("无人脸")
            else:
                if not r.eyes_open:
                    reasons.append(f"闭眼(EAR={r.eye_score:.3f})")
                if not r.skin_ok:
                    reasons.append(f"肤色异常(得分={r.skin_score:.2f})")
            if not r.exposure_ok:
                reasons.append(f"曝光异常(得分={r.exposure_score:.2f})")
            if r.error:
                reasons.append(r.error)
            print(f"  {r.path.name}: {', '.join(reasons)}")

    # 9. 输出合格照片
    if output_folder and passed:
        out_dir = Path(output_folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        transfer = shutil.copy2 if do_copy else shutil.move
        action_word = "复制" if do_copy else "移动"
        print(f"\n正在{action_word} {len(passed)} 张合格照片到 '{out_dir}'...")
        for r in passed:
            dest = out_dir / r.path.name
            if dest.exists():
                dest = out_dir / f"{r.path.stem}_filtered{r.path.suffix}"
            transfer(str(r.path), str(dest))
        print("完成!")

    print()
    safe_input("按 Enter 键退出...")


# ── 入口 ──────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser(description="自动筛选照片")
        parser.add_argument("input_dir", type=str)
        parser.add_argument("--output", "-o", type=str, default=None)
        parser.add_argument("--copy", action="store_true")
        parser.add_argument("--ear-threshold", type=float, default=EAR_THRESHOLD)
        parser.add_argument("--over", type=float, default=OVEREXPOSURE_RATIO_THRESHOLD)
        parser.add_argument("--under", type=float, default=UNDEREXPOSURE_RATIO_THRESHOLD)
        args = parser.parse_args()

        EAR_THRESHOLD = args.ear_threshold
        OVEREXPOSURE_RATIO_THRESHOLD = args.over
        UNDEREXPOSURE_RATIO_THRESHOLD = args.under

        input_dir = Path(args.input_dir)
        if not input_dir.is_dir():
            print(f"错误: '{input_dir}' 不是有效文件夹")
            sys.exit(1)

        extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
        photo_paths = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in extensions and p.is_file()])
        if not photo_paths:
            print(f"在 '{input_dir}' 中未找到照片文件")
            sys.exit(1)

        print(f"找到 {len(photo_paths)} 张照片，开始分析...\n")
        landmarker = create_landmarker()
        import mediapipe as mp
        from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat

        results = []
        for i, p in enumerate(photo_paths, 1):
            try:
                result = process_photo(p, landmarker, MPImage, ImageFormat)
            except Exception as e:
                import traceback
                traceback.print_exc()
                result = PhotoResult(path=p, error="处理异常: {}".format(e))
            status = "[OK]" if result.all_pass else "[NG]"
            details = []
            if not result.face_detected:
                details.append("无人脸(仅检曝光)")
            else:
                details.append(f"EAR={result.eye_score:.3f}({'睁' if result.eyes_open else '闭'})")
                details.append(f"肤色={result.skin_score:.2f}")
            details.append(f"曝光={result.exposure_score:.2f}")
            print(f"  [{i}/{len(photo_paths)}] {status} {p.name}  |  {', '.join(details)}")
            results.append(result)
        landmarker.close()

        passed = [r for r in results if r.all_pass]
        print(f"\n合格: {len(passed)}/{len(results)}")
        if args.output and passed:
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            transfer = shutil.copy2 if args.copy else shutil.move
            for r in passed:
                dest = out_dir / r.path.name
                if dest.exists():
                    dest = out_dir / f"{r.path.stem}_filtered{r.path.suffix}"
                transfer(str(r.path), str(dest))
            print(f"已输出到 '{out_dir}'")
    else:
        interactive_main()
