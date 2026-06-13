"""
所有默认阈值常量。
从 photo_filter_gui.py 提取，保持数值不变。
"""

# ── 曝光检测 ──────────────────────────────────────────────
DEFAULT_OVEREXPOSURE_RATIO = 0.05   # 过曝像素占比阈值
DEFAULT_UNDEREXPOSURE_RATIO = 0.15  # 欠曝像素占比阈值
OVEREXPOSURE_PIXEL_THRESHOLD = 250  # 过曝像素灰度值
UNDEREXPOSURE_PIXEL_THRESHOLD = 15  # 欠曝像素灰度值

# ── 肤色检测 (LAB 色彩空间) ───────────────────────────────
# v3.0: 大幅放宽范围，仅拒绝极端异常（极黑/极亮），避免深色皮肤误判
SKIN_L_MIN, SKIN_L_MAX = 15, 245    # 仅拒绝严重欠曝(极黑)或严重过曝(极亮)的人脸
SKIN_A_MIN, SKIN_A_MAX = 0, 40      # 红-绿轴，极宽范围
SKIN_B_MIN, SKIN_B_MAX = 0, 50      # 蓝-黄轴，极宽范围

# ── 睁眼检测 (EAR) ──────────────────────────────────────
DEFAULT_EAR_THRESHOLD = 0.20
EAR_MIN, EAR_MAX = 0.15, 0.25       # 滑块范围

# ── 构图水平检测 ──────────────────────────────────────────
LEVEL_ANGLE_TOLERANCE = 9.0         # 通用方法：偏离轴线中位数 < 9° 算合格
LEVEL_MIN_LINES = 5                 # 通用方法：至少检测到 N 条线才做判断
LEVEL_CONSISTENCY_THRESHOLD = 20.0  # 通用方法：v3.0 放宽到20°，减少复杂场景误判

# 地平线检测法 (推荐)
DEFAULT_HORIZON_ANGLE_TOLERANCE = 5.0   # 地平线允许倾斜角度（越小越严格）
HORIZON_MIN_LINE_RATIO = 0.30           # 线段长度至少占图宽的30%才算地平线候选
HORIZON_CLUSTER_ANGLE_RANGE = 4.0       # 角度聚类范围 ±4°
HORIZON_MIN_CLUSTER_SIZE = 3            # 至少3条线形成聚类才判定为地平线

LEVEL_METHODS = {
    "horizon": "地平线检测（推荐）",
    "general": "通用检测",
}

# ── 人脸关键点索引 ──────────────────────────────────────
# MediaPipe 468 关键点模型

LEFT_EYE_IDX  = [33, 133, 157, 158, 159, 160, 161, 173]
RIGHT_EYE_IDX = [362, 263, 384, 385, 386, 387, 388, 398]

FACE_SKIN_IDX = [
    10, 67, 69, 108, 109, 151, 299, 337, 338,           # 额头
    50, 101, 117, 118, 119, 123, 126, 142, 187, 203, 205, 206, 207,  # 左脸颊
    280, 329, 330, 346, 347, 348, 355, 371, 411, 423, 425, 426, 427,  # 右脸颊
    152, 169, 170, 199, 200, 201, 208, 210, 211,         # 下巴
]

# ── 图片处理 ──────────────────────────────────────────────
MAX_IMAGE_DIM = 3600               # v3.5: 大幅提升以保留小脸细节 (1920→2400→3600)
FACE_DETECT_DIM = 4800              # 人脸检测使用更高分辨率，不参与后续分析
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

# RAW 照片格式（v3.5）
RAW_EXTENSIONS = {
    '.cr2', '.cr3',   # Canon
    '.nef', '.nrw',   # Nikon
    '.arw', '.srf',   # Sony
    '.dng',           # Adobe / 手机
    '.raf',           # Fujifilm
    '.orf',           # Olympus
    '.rw2',           # Panasonic
    '.pef',           # Pentax
    '.srw',           # Samsung
    '.3fr',           # Hasselblad
    '.mef', '.mrw',   # Minolta / Konica
    '.x3f',           # Sigma
    '.erf',           # Epson
    '.kdc', '.dcr',   # Kodak
    '.mos',           # Leaf
    '.raw',           # 通用
}
ALL_SUPPORTED_EXTENSIONS = SUPPORTED_EXTENSIONS | RAW_EXTENSIONS

# ── MediaPipe ────────────────────────────────────────────
MIN_FACE_DETECTION_CONFIDENCE = 0.15   # v3.5: 进一步降低提升敏感度 (0.4→0.25→0.15)
MIN_FACE_PRESENCE_CONFIDENCE = 0.15    # v3.5: 降低 (0.3→0.2→0.15)
MIN_TRACKING_CONFIDENCE = 0.3          # v3.5: 降低 (0.5→0.3)

# ── 性能 ──────────────────────────────────────────────────
DEFAULT_MAX_WORKERS = 2             # 并行处理线程数

# ── 新增检测 (Phase 3) ──────────────────────────────────
DEFAULT_BLUR_THRESHOLD = 40.0       # Laplacian 方差阈值（v3.0: 降低避免误判，默认使用加权ROI法）
DEFAULT_CLARITY_THRESHOLD = 0.5     # 人脸清晰度综合评分阈值
DEFAULT_DUPLICATE_HAMMING = 5       # dHash 汉明距离阈值

# ── 滑块范围 ──────────────────────────────────────────────
OVER_SLIDER_RANGE = (0.01, 0.20, 0.01)   # (min, max, step)
UNDER_SLIDER_RANGE = (0.05, 0.40, 0.01)
EAR_SLIDER_RANGE = (0.15, 0.25, 0.01)
BLUR_SLIDER_RANGE = (10.0, 200.0, 5.0)   # v3.0: 降低上限，默认40，越小越严格

# 构图严格度滑块 — 地平线方法
LEVEL_HORIZON_SLIDER_RANGE = (2.0, 12.0, 0.5)  # 允许倾斜角度，越小越严格
# 构图严格度滑块 — 通用方法
LEVEL_GENERAL_SLIDER_RANGE = (4.0, 20.0, 1.0)  # 允许倾斜角度，越小越严格
