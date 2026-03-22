import cv2
import numpy as np
import imutils

def nothing(x):
    pass

# 选择摄像头类型
camera_type = "USB"  # "ESP32CAM"
usb_index = 0
esp32_url = "http://192.168.43.31:81/stream"

# 打开摄像头
if camera_type == "USB":
    cap = cv2.VideoCapture(usb_index)
else:
    cap = cv2.VideoCapture(esp32_url)

# 创建窗口和滑块
cv2.namedWindow("HSV调试")
cv2.createTrackbar("H_min", "HSV调试", 25, 179, nothing)
cv2.createTrackbar("H_max", "HSV调试", 90, 179, nothing)
cv2.createTrackbar("S_min", "HSV调试", 40, 255, nothing)
cv2.createTrackbar("S_max", "HSV调试", 255, 255, nothing)
cv2.createTrackbar("V_min", "HSV调试", 40, 255, nothing)
cv2.createTrackbar("V_max", "HSV调试", 255, 255, nothing)

print("提示：调整滑块，直到绿色车牌在右侧窗口中显示为白色高亮，背景为黑色")
print("按 'q' 键退出，退出后会显示最终的HSV范围")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = imutils.resize(frame, width=600)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 获取滑块当前值
    h_min = cv2.getTrackbarPos("H_min", "HSV调试")
    h_max = cv2.getTrackbarPos("H_max", "HSV调试")
    s_min = cv2.getTrackbarPos("S_min", "HSV调试")
    s_max = cv2.getTrackbarPos("S_max", "HSV调试")
    v_min = cv2.getTrackbarPos("V_min", "HSV调试")
    v_max = cv2.getTrackbarPos("V_max", "HSV调试")

    # 生成掩膜
    lower_green = np.array([h_min, s_min, v_min])
    upper_green = np.array([h_max, s_max, v_max])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    # 拼接显示
    mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    combined = np.hstack((frame, mask_colored, result))
    cv2.imshow("HSV调试", combined)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 输出最终范围
print("\n最终HSV范围（请复制到config.py）：")
print(f"LOWER_GREEN = ({h_min}, {s_min}, {v_min})")
print(f"UPPER_GREEN = ({h_max}, {s_max}, {v_max})")

cap.release()
cv2.destroyAllWindows()