"""
睁眼检测 — Eye Aspect Ratio (EAR) 算法。
"""

import numpy as np

from utils.constants import LEFT_EYE_IDX, RIGHT_EYE_IDX


def eye_aspect_ratio(eye_points: np.ndarray) -> float:
    """
    计算单只眼睛的 EAR 值。
    eye_points: shape (8, 2)，按 MediaPipe 关键点顺序排列。
    """
    v1 = np.linalg.norm(eye_points[1] - eye_points[7])
    v2 = np.linalg.norm(eye_points[2] - eye_points[6])
    v3 = np.linalg.norm(eye_points[3] - eye_points[5])
    h_val = np.linalg.norm(eye_points[0] - eye_points[4])

    if h_val < 1e-7:
        return 0.0
    return float((v1 + v2 + v3) / (3.0 * h_val))


def check_eyes_open(face_landmarks, img_shape, ear_th: float) -> tuple:
    """
    检测双眼是否睁开。
    face_landmarks: MediaPipe FaceLandmarkerResult.face_landmarks[0]
    返回 (是否睁眼: bool, 平均EAR: float)。
    """
    h, w = img_shape[:2]

    def get_pts(indices):
        return np.array([[face_landmarks[i].x * w, face_landmarks[i].y * h]
                         for i in indices])

    left_ear = eye_aspect_ratio(get_pts(LEFT_EYE_IDX))
    right_ear = eye_aspect_ratio(get_pts(RIGHT_EYE_IDX))

    eyes_open = bool(left_ear >= ear_th and right_ear >= ear_th)
    return eyes_open, float((left_ear + right_ear) / 2)
