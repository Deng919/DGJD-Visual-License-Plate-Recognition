# plate_recognition_core.py - 车牌识别核心逻辑
import cv2
import numpy as np
import imutils
import time
import serial
from config import *

# 高版本NumPy兼容补丁
np.int = int
np.float = float
np.bool = bool

# 导入车牌识别库（异常处理放到主程序）
try:
    from hyperlpr import HyperLPR_plate_recognition
except ImportError:
    HyperLPR_plate_recognition = None


class PlateRecognitionCore:
    def __init__(self):
        # 识别状态变量
        self.sent_plates = set()
        self.last_cache_clear = time.time()
        self.arduino_serial = None

    def init_serial(self, port=SERIAL_PORT, baud_rate=BAUD_RATE, timeout=SERIAL_TIMEOUT):
        """初始化串口"""
        try:
            self.arduino_serial = serial.Serial(port, baud_rate, timeout=timeout)
            return True, f"串口打开成功：{port}"
        except Exception as e:
            return False, f"串口打开失败：{str(e)}"

    def close_serial(self):
        """关闭串口"""
        if self.arduino_serial and self.arduino_serial.is_open:
            self.arduino_serial.close()
            return "串口已关闭"
        return "串口未打开"

    def preprocess_for_ocr(self, plate_roi):
        """车牌ROI预处理（用于OCR识别）"""
        if plate_roi is None or plate_roi.size == 0:
            return None
        plate = imutils.resize(plate_roi, width=280)
        gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def recognize_plate_number(self, processed_plate):
        """识别车牌号"""
        if processed_plate is None or HyperLPR_plate_recognition is None:
            return ""
        try:
            result = HyperLPR_plate_recognition(processed_plate)
            if result:
                plate_num, confidence, _ = result[0]
                plate_num = plate_num.strip().replace(" ", "").upper()
                return plate_num if confidence > 0.5 else ""
            return ""
        except Exception:
            return ""

    def is_plate_authorized(self, plate_str, whitelist):
        """校验车牌是否在白名单且格式合法"""
        if not plate_str:
            return False
        if not PLATE_PATTERN.match(plate_str):
            return False
        return plate_str in whitelist

    def send_serial_data(self, plate_num, pass_allowed, auto_mode=False):
        """发送串口指令（自动模式下不限制重复发送）"""
        if not self.arduino_serial or not self.arduino_serial.is_open or not plate_num:
            return False, "串口未就绪或车牌为空"

        # 非自动模式下，同一车牌只发送一次
        if not auto_mode and plate_num in self.sent_plates:
            return False, f"车牌{plate_num}已发送过指令，跳过"

        cmd = ALLOW_PASS_CMD if pass_allowed else DENY_PASS_CMD
        send_data = f"{cmd}{SERIAL_DELIMITER}{plate_num}\n".encode("utf-8")

        try:
            self.arduino_serial.write(send_data)
            if not auto_mode:
                self.sent_plates.add(plate_num)
            return True, f"串口发送：{cmd} {plate_num}"
        except Exception as e:
            return False, f"串口发送失败：{str(e)}"

    def clear_plate_cache(self):
        """清空已发送车牌缓存"""
        self.sent_plates.clear()
        self.last_cache_clear = time.time()
        return f"已清空车牌缓存，当前时间：{time.time():.1f}s"

    def clear_sent_plates_cache_auto(self):
        """自动清理缓存（定期）"""
        current_time = time.time()
        if current_time - self.last_cache_clear > CLEAR_CACHE_INTERVAL:
            self.clear_plate_cache()

    def preprocess_image(self, frame):
        """原始图像预处理（边缘检测）"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        return cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)

    def filter_blue_plate_region(self, frame):
        """过滤蓝色车牌区域"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(LOWER_BLUE), np.array(UPPER_BLUE))
        return cv2.dilate(mask, None, iterations=2)

    def find_license_plate_contours(self, edged, mask, frame):
        """查找车牌轮廓"""
        combined = cv2.bitwise_and(edged, edged, mask=mask)
        cnts = cv2.findContours(combined.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:20]

        best_plate = None
        best_location = None
        for c in cnts:
            if cv2.contourArea(c) < MIN_AREA:
                continue
            perimeter = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.03 * perimeter, True)
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)
            if 4 <= len(approx) <= 6 and MIN_ASPECT_RATIO <= aspect_ratio <= MAX_ASPECT_RATIO:
                best_plate = frame[y:y + h, x:x + w]
                best_location = (x, y, w, h)
                break
        return best_plate, best_location

    def validate_plate(self, plate_roi):
        """校验车牌ROI有效性"""
        if plate_roi is None:
            return False
        h, w = plate_roi.shape[:2]
        if w < 50 or h < 15:
            return False
        gray_plate = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        _, binary_plate = cv2.threshold(gray_plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary_plate == 255) / binary_plate.size
        return 0.10 < white_ratio < 0.70

    def detect_and_recognize(self, frame, frame_counter, recognize_interval=RECOGNIZE_INTERVAL):
        """单帧图像的车牌检测与识别"""
        # 预处理
        edged = self.preprocess_image(frame)
        blue_mask = self.filter_blue_plate_region(frame)

        # 查找车牌轮廓
        plate_roi, plate_loc = self.find_license_plate_contours(edged, blue_mask, frame)
        is_valid = self.validate_plate(plate_roi)

        # 防抖逻辑
        detect_counter = 1 if is_valid else 0
        is_plate_detected = detect_counter >= DETECT_COUNTER_THRESH

        # 识别逻辑
        current_plate = ""
        if is_plate_detected and plate_roi is not None and frame_counter % recognize_interval == 0:
            processed_plate = self.preprocess_for_ocr(plate_roi)
            current_plate = self.recognize_plate_number(processed_plate)

        return {
            "plate_detected": is_plate_detected,
            "plate_loc": plate_loc,
            "plate_num": current_plate,
            "frame": frame  # 返回处理后的帧（用于绘制）
        }