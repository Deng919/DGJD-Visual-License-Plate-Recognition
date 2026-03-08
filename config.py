# config.py - 系统配置常量
import re

# ====================== 基础识别配置 ======================
CAMERA_TYPE = "USB"  # 摄像头类型: "USB" 或 "ESP32CAM"
CAMERA_INDEX = 0  # USB摄像头索引
ESP32CAM_URL = "http://192.168.43.31:81/stream"  # ESP32CAM流地址
FRAME_WIDTH = 600

# ========== 摄像头画质配置 ==========
# USB摄像头分辨率 (宽, 高)
USB_CAM_RESOLUTION = (1920, 1080)  # 可选：1920x1080, 1280x720, 800x600, 640x480
USB_CAM_FPS = 30  # 帧率

# ESP32CAM配置
ESP32CAM_FPS = 15  # ESP32CAM帧率（建议10-20）
ESP32CAM_BUFFER_SIZE = 1  # 缓冲区大小（减小延迟）

# 车牌检测参数
MIN_ASPECT_RATIO = 2.5
MAX_ASPECT_RATIO = 6.0
MIN_AREA = 1000
DETECT_COUNTER_THRESH = 1
RECOGNIZE_INTERVAL = 5
CLEAR_CACHE_INTERVAL = 30  # 缓存清空间隔（秒）

# 串口通信配置
SERIAL_PORT = "COM6"
BAUD_RATE = 9600
SERIAL_TIMEOUT = 1
ALLOW_PASS_CMD = "ALLOW"
DENY_PASS_CMD = "DENY"
SERIAL_DELIMITER = ","

# 车牌颜色检测（蓝牌）
LOWER_BLUE = (95, 30, 30)
UPPER_BLUE = (135, 255, 255)

# 车牌格式校验
PROVINCE_CODES = {"京", "津", "沪", "渝", "冀", "豫", "云", "辽", "黑", "湘", "皖", "鲁",
                  "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋", "蒙", "陕", "吉", "闽",
                  "贵", "粤", "青", "藏", "川", "宁", "琼"}
PLATE_PATTERN = re.compile(r'^(' + '|'.join(PROVINCE_CODES) + r')[A-Z]{1}[A-Z0-9]{5,6}$')

# 默认白名单
DEFAULT_WHITELIST = {"京A84523", "沪B67890", "粤GSB250", "京AD12345"}

# ====================== 计时收费配置 ======================
# 基础计费规则
BASE_MINUTES = 60  # 基础时长（分钟）
BASE_FEE = 5.0     # 基础费用（元）
UNIT_PRICE = 5.0   # 超时单价（元/60分钟）
UNIT_MINUTES = 60  # 计费单位（分钟）
MAX_FEE_PER_DAY = 100.0  # 单日最高费用（元）

# 自动模式防抖配置
RECOGNIZE_DEBOUNCE = 3  # 识别防抖时间（秒）

# ====================== 画面增强配置 ======================
ENABLE_SHARPEN = None          # 是否开启锐化
SHARPEN_AMOUNT = 0.3           # 锐化强度 0~1.0（0.3为自然值）
SATURATION_FACTOR = 1.2        # 饱和度（明艳）0.8~2.0（1.2为自然值）
CONTRAST_FACTOR = 1.05         # 对比度 0.9~1.5（1.05为自然值）
BRIGHTNESS_FACTOR = 1.0        # 亮度 0.9~1.1（1.0为默认）