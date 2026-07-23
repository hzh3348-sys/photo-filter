"""
所有默认阈值常量。
从 photo_filter_gui.py 提取，保持数值不变。
"""

# ── 曝光检测 ──────────────────────────────────────────────
# 理念：照片可以后期，只拦截真正不可用的极端情况。
# 默认阈值极高，仅当照片绝大多数像素都过曝/欠曝时才拦截。
DEFAULT_OVEREXPOSURE_RATIO = 0.50   # 50%以上像素过曝才拦
DEFAULT_UNDEREXPOSURE_RATIO = 0.50  # 50%以上像素欠曝才拦
OVEREXPOSURE_PIXEL_THRESHOLD = 250  # 过曝像素灰度值
UNDEREXPOSURE_PIXEL_THRESHOLD = 15  # 欠曝像素灰度值

# ── 肤色检测 (LAB 色彩空间) ───────────────────────────────
# v5.0: 极致放宽，只拦截明显不是肤色的情况（如纯蓝、纯绿、纯紫等极端色偏）
# 配合区域采样算法，正常肤色几乎都能通过
SKIN_L_MIN, SKIN_L_MAX = 10, 250    # 几乎不拦亮度（仅全黑/全白不可）
SKIN_A_MIN, SKIN_A_MAX = -5, 50     # 绿-红轴，覆盖所有人类肤色
SKIN_B_MIN, SKIN_B_MAX = -5, 60     # 蓝-黄轴，覆盖所有人类肤色

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

# ── 合照模式 ──────────────────────────────────────────
FACE_MODE_BEST = "best"             # 取最优人脸
FACE_MODE_ALL = "all"               # 所有人脸通过才算合格
FACE_MODES = {
    FACE_MODE_BEST: "最优人脸（推荐生活照）",
    FACE_MODE_ALL: "所有人脸（推荐会议合照）",
}

# ── 表情检测 (MediaPipe Blendshapes) ───────────────────
DEFAULT_EXPRESSION_SMILE_THRESHOLD = 0.25   # smile blendshape 阈值（低于此值视为表情欠佳）
BLENDSHAPE_SMILE_KEYS = [                   # 笑容相关 blendshape 名称
    "mouthSmileLeft",
    "mouthSmileRight",
]
BLENDSHAPE_MOUTH_OPEN_KEYS = [              # 张嘴（说话/打哈欠）
    "jawOpen",
]
BLENDSHAPE_EYE_OPEN_KEYS = [                # 眼睛睁开度
    "eyeOpenLeft",
    "eyeOpenRight",
]
BLENDSHAPE_NEUTRAL_KEY = "_neutral"         # 表情中立度
# 表情宽容度: 低于此阈值会有提示
EXPRESSION_SMILE_MIN = 0.0                  # 滑块最小值
EXPRESSION_SMILE_MAX = 0.6                  # 滑块最大值
EXPRESSION_SMILE_STEP = 0.05                # 滑块步长
# 表情滑块范围
EXPRESSION_SMILE_SLIDER_RANGE = (0.0, 0.6, 0.05)

# ── 红眼检测 ──────────────────────────────────────────
DEFAULT_RED_EYE_THRESHOLD = 0.08            # 眼部红色像素占比阈值
RED_EYE_HUE_MIN = 0                         # 红色色调范围（HSV）: 0°~10° 和 170°~180°
RED_EYE_HUE_MAX = 10
RED_EYE_HUE_MIN2 = 170                      # 第二段红色范围
RED_EYE_HUE_MAX2 = 180
RED_EYE_SATURATION_MIN = 40                 # 最低饱和度（排除灰白像素）
RED_EYE_VALUE_MIN = 40                      # 最低明度（排除纯黑瞳孔）
# 滑块范围
RED_EYE_SLIDER_RANGE = (0.02, 0.25, 0.01)   # 红眼阈值滑块 (min, max, step)

# ── 滑块范围 ──────────────────────────────────────────────
# 范围 0.20~0.80，默认 0.50（只拦极端情况）
OVER_SLIDER_RANGE = (0.20, 0.80, 0.05)   # (min, max, step)
UNDER_SLIDER_RANGE = (0.20, 0.80, 0.05)
EAR_SLIDER_RANGE = (0.15, 0.25, 0.01)
BLUR_SLIDER_RANGE = (10.0, 200.0, 5.0)   # v3.0: 降低上限，默认40，越小越严格

# 构图严格度滑块 — 地平线方法
LEVEL_HORIZON_SLIDER_RANGE = (2.0, 12.0, 0.5)  # 允许倾斜角度，越小越严格
# 构图严格度滑块 — 通用方法
LEVEL_GENERAL_SLIDER_RANGE = (4.0, 20.0, 1.0)  # 允许倾斜角度，越小越严格
