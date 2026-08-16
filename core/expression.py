"""
表情/笑容检测 — 基于 MediaPipe Blendshapes。
v5.0: 利用 FaceLandmarker 输出的 52 种 blendshape 系数，
检测笑容程度、张嘴（说话/打哈欠）、表情自然度。
"""

from utils.constants import (
    BLENDSHAPE_SMILE_KEYS,
    BLENDSHAPE_MOUTH_OPEN_KEYS,
    BLENDSHAPE_NEUTRAL_KEY,
    EXPRESSION_MOUTH_OPEN_LIMIT,
    EXPRESSION_NEUTRAL_LIMIT,
)


def _get_blendshape_score(categories, name: str) -> float:
    """从 blendshape categories 列表中查找指定名称的分数。"""
    for cat in categories:
        if cat.category_name == name:
            return float(cat.score)
    return 0.0


def check_expression_single(
    categories,
    smile_threshold: float = 0.25,
) -> tuple[bool, float, dict]:
    """
    检查单张人脸的表情质量。

    参数:
        categories: MediaPipe blendshape Classifications.categories 列表（52项）
        smile_threshold: 笑容分数阈值（低于此值视为表情欠佳）

    返回:
        (是否合格, 综合分数, 详情字典)
        详情: {smile, mouth_open, neutral, is_smiling, is_mouth_open}
    """
    # 提取关键 blendshape 分数
    smile_scores = [_get_blendshape_score(categories, k) for k in BLENDSHAPE_SMILE_KEYS]
    mouth_open_scores = [_get_blendshape_score(categories, k) for k in BLENDSHAPE_MOUTH_OPEN_KEYS]
    neutral = _get_blendshape_score(categories, BLENDSHAPE_NEUTRAL_KEY)

    smile_avg = sum(smile_scores) / len(smile_scores) if smile_scores else 0.0
    mouth_open = sum(mouth_open_scores) / len(mouth_open_scores) if mouth_open_scores else 0.0

    # 笑容判断：笑容分数 >= 阈值
    is_smiling = smile_avg >= smile_threshold

    # 张嘴判断：张嘴 > 0.3 视为可能在说话或打哈欠（过于夸张的表情）
    is_mouth_open = mouth_open > EXPRESSION_MOUTH_OPEN_LIMIT

    # 综合：笑容足够 + 不过度张嘴 = 合格
    # 如果表情过于中立（neutral > 0.9）且不笑 → 可能是板着脸，也不合格
    is_too_neutral = neutral > EXPRESSION_NEUTRAL_LIMIT and smile_avg < smile_threshold

    ok = is_smiling and not (is_mouth_open or is_too_neutral)

    # 综合分数：笑容在 [0, 2×threshold] 区间线性映射到 [0, 1]
    # （threshold 处得 0.5，2×threshold 处满分），再减去张嘴/僵硬惩罚。
    # 有区分度：笑得多得分高，而不是几乎恒为 1。
    if smile_threshold > 0:
        score = smile_avg / (smile_threshold * 2.0)
    else:
        score = smile_avg
    if is_mouth_open:
        score -= 0.3 * mouth_open   # 张嘴惩罚
    if is_too_neutral:
        score -= 0.2                # 太僵硬的惩罚

    # 归一化到 [0, 1]
    score = max(0.0, min(1.0, score))

    detail = {
        "smile": round(smile_avg, 3),
        "mouth_open": round(mouth_open, 3),
        "neutral": round(neutral, 3),
        "is_smiling": is_smiling,
        "is_mouth_open": is_mouth_open,
    }
    return ok, score, detail


def check_expression_multi(
    face_blendshapes_list,
    smile_threshold: float = 0.25,
    face_mode: str = "best",
) -> tuple[bool, float, str, int, int]:
    """
    检查多张人脸的表情质量。

    参数:
        face_blendshapes_list: MediaPipe FaceLandmarkerResult.face_blendshapes 列表
                               (每个元素是一个 Classifications，.categories 是 52 项 blendshape)
        smile_threshold: 笑容阈值
        face_mode: "best" 取最优人脸 / "all" 所有人脸通过才算合格

    返回:
        (是否合格, 综合分数, 详情字符串, 不合格人脸数, 总人脸数)
    """
    if not face_blendshapes_list:
        return True, 1.0, "", 0, 0

    total = len(face_blendshapes_list)
    results = []
    for blendshapes in face_blendshapes_list:
        ok, score, detail = check_expression_single(
            blendshapes.categories, smile_threshold)
        results.append((ok, score, detail))

    if face_mode == "best":
        # 取最优人脸（笑容最高）
        best_score = max(r[1] for r in results) if results else 1.0
        best_result = max(results, key=lambda r: r[1]) if results else (True, 1.0, {})
        fail_count = sum(1 for r in results if not r[0])

        # 详情：统计不笑/张嘴的人数
        not_smiling = sum(1 for r in results if not r[2].get("is_smiling", True))
        mouth_open = sum(1 for r in results if r[2].get("is_mouth_open", False))
        detail_parts = []
        if not_smiling > 0:
            detail_parts.append(f"{not_smiling}人不笑")
        if mouth_open > 0:
            detail_parts.append(f"{mouth_open}人张嘴")

        return best_result[0], best_score, ", ".join(detail_parts), fail_count, total

    else:
        # face_mode == "all": 所有人脸都通过才合格
        all_ok = all(r[0] for r in results)
        worst_score = min(r[1] for r in results) if results else 1.0
        fail_count = sum(1 for r in results if not r[0])

        not_smiling = sum(1 for r in results if not r[2].get("is_smiling", True))
        mouth_open = sum(1 for r in results if r[2].get("is_mouth_open", False))
        detail_parts = []
        if not_smiling > 0:
            detail_parts.append(f"{not_smiling}人不笑")
        if mouth_open > 0:
            detail_parts.append(f"{mouth_open}人张嘴")

        return all_ok, worst_score, ", ".join(detail_parts), fail_count, total
