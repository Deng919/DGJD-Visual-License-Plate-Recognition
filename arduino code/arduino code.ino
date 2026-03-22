#include <Wire.h>
#include <RSCG12864B.h>
#include <Servo.h>  // 加入舵机库

// ==================== 配置 ====================
#define GATE_PIN            8
#define GATE_OPEN_TIME      5000
#define BUZZER_PIN          3   // 蜂鸣器 D3
#define SERVO_PIN           5   // 舵机 D5

#define SERVO_OPEN_ANGLE    90  // 开门角度（可自行调整）
#define SERVO_CLOSE_ANGLE   0   // 关门角度

// ==================== 全局对象 ====================
Servo gateServo;                // 舵机对象
unsigned long servoTimer = 0;
bool servoNeedClose = false;

// ==================== 全局变量 ====================
String inputBuffer = "";
String cmd = "";

unsigned long lastSecond = 0;
int sec = 0, min = 0, hour = 9;
int day = 22, month = 3, year = 2026;
bool showWelcomeFlag = true;

// ==================== 中文（GB2312）====================
char str_welcome[] = {0xBB,0xB6,0xD3,0xAD,0xB9,0xE2,0xC1,0xD9, 0x00}; // 欢迎光临
char str_car[]     = {0xB3,0xB5,0xC5,0xC6,0x3A,0x00};               // 车牌:
char str_allow[]   = {0xD4,0xCA,0xD0,0xED,0xCD,0xA8,0xD0,0xD0, 0x00};// 允许通行
char str_deny[]    = {0xBD,0xFB,0xD6,0xB9,0xCD,0xA8,0xD0,0xD0, 0x00};// 禁止通行

// ==================== 省份GB2312 硬编码映射（确认正确） ====================
void getProvinceGB2312(String c, char *out) {
  if (c == "京") { out[0] = 0xBE; out[1] = 0xA9; }
  else if (c == "津") { out[0] = 0xBD; out[1] = 0xF2; }
  else if (c == "沪") { out[0] = 0xBB; out[1] = 0xA6; }
  else if (c == "渝") { out[0] = 0xD3; out[1] = 0xE5; }
  else if (c == "冀") { out[0] = 0xBC; out[1] = 0xBD; }
  else if (c == "晋") { out[0] = 0xBD; out[1] = 0xF8; }
  else if (c == "辽") { out[0] = 0xC1; out[1] = 0xC9; }
  else if (c == "吉") { out[0] = 0xBC; out[1] = 0xAA; }
  else if (c == "黑") { out[0] = 0xBA; out[1] = 0xDA; }
  else if (c == "苏") { out[0] = 0xD5; out[1] = 0xBC; }
  else if (c == "浙") { out[0] = 0xD5; out[1] = 0xE3; }
  else if (c == "皖") { out[0] = 0xCD; out[1] = 0xEB; }
  else if (c == "闽") { out[0] = 0xC3; out[1] = 0xF6; }
  else if (c == "赣") { out[0] = 0xB8; out[1] = 0xD3; }
  else if (c == "鲁") { out[0] = 0xC2; out[1] = 0xB3; }
  else if (c == "豫") { out[0] = 0xD4; out[1] = 0xA1; }
  else if (c == "鄂") { out[0] = 0xB6; out[1] = 0xAD; }
  else if (c == "湘") { out[0] = 0xCF; out[1] = 0xE6; }
  else if (c == "粤") { out[0] = 0xD4; out[1] = 0xC1; }
  else if (c == "桂") { out[0] = 0xB9; out[1] = 0xF0; }
  else if (c == "琼") { out[0] = 0xC7; out[1] = 0xED; }
  else if (c == "川") { out[0] = 0xB4; out[1] = 0xA8; }
  else if (c == "贵") { out[0] = 0xB9; out[1] = 0xF3; }
  else if (c == "云") { out[0] = 0xD4; out[1] = 0xC6; }
  else if (c == "藏") { out[0] = 0xB2; out[1] = 0xD8; }
  else if (c == "陕") { out[0] = 0xC9; out[1] = 0xC2; }
  else if (c == "甘") { out[0] = 0xB8; out[1] = 0xCA; }
  else if (c == "青") { out[0] = 0xC7; out[1] = 0xE0; }
  else if (c == "宁") { out[0] = 0xC4; out[1] = 0xFE; }
  else if (c == "新") { out[0] = 0xD0; out[1] = 0xC2; }
  else { out[0] = 0x20; out[1] = 0x20; }
}

// ==================== 核心修复：正确处理UTF-8中文省份 ====================
void convertPlate(String input, char *output) {
  memset(output, 0, 50);
  int idx = 0;

  if (input.length() == 0) return;

  // 【关键修复】UTF-8中文占3字节，取前3个字节作为省份
  String pro = input.substring(0, 3);
  char gb[3];
  getProvinceGB2312(pro, gb);
  
  output[idx++] = gb[0];
  output[idx++] = gb[1];

  // 【关键修复】后面从第3个字节开始取
  for (int i = 3; i < input.length(); i++) {
    output[idx++] = input[i];
  }
  output[idx] = 0;
}

// ==================== 计算宽度 ====================
int getStr16Width(char *s) {
  int w = 0;
  for (int i = 0; s[i]; i++) {
    if ((s[i] & 0x80) != 0) { w += 16; i++; }
    else w += 8;
  }
  return w;
}
int getStr12Width(char *s) {
  return strlen(s) * 12;
}

// ==================== 显示函数 ====================
void print16_Center(int y, char *s) {
  int w = getStr16Width(s);
  int x = (128 - w) / 2;
  RSCG12864B.print_string_16_xy(x, y, s);
}
void print12_Center(int y, char *s) {
  int w = getStr12Width(s);
  int x = (128 - w) / 2;
  RSCG12864B.print_string_12_xy(x, y, s);
}
void printPlateLine_Center(int y, char *prefix, char *plate) {
  int w1 = getStr16Width(prefix);
  int w2 = getStr16Width(plate);
  int total = w1 + w2;
  int x = (128 - total) / 2;
  RSCG12864B.print_string_16_xy(x, y, prefix);
  RSCG12864B.print_string_16_xy(x + w1, y, plate);
}

// ==================== 蜂鸣器函数 ====================
void beep(int ms = 100) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(ms);
  digitalWrite(BUZZER_PIN, LOW);
}
void beepTwice() {
  beep(100);
  delay(100);
  beep(100);
}

// ==================== 舵机控制 ====================
void openGate() {
  gateServo.write(SERVO_OPEN_ANGLE);
  digitalWrite(GATE_PIN, HIGH);
  servoNeedClose = true;
  servoTimer = millis();
}

void closeGate() {
  gateServo.write(SERVO_CLOSE_ANGLE);
  digitalWrite(GATE_PIN, LOW);
  servoNeedClose = false;
}

// ==================== 函数声明 ====================
void runClock();
void showWelcomeScreen();
void parseSerialData(String data);

// ==================== setup ====================
void setup() {
  Wire.begin();
  RSCG12864B.begin();
  RSCG12864B.brightness(180);
  RSCG12864B.clear();

  // 初始化舵机
  gateServo.attach(SERVO_PIN);
  gateServo.write(SERVO_CLOSE_ANGLE);

  // 初始化IO
  pinMode(GATE_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(GATE_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.begin(9600);
}

void loop() {
  runClock();

  // 自动关门（非阻塞）
  if (servoNeedClose && millis() - servoTimer >= GATE_OPEN_TIME) {
    closeGate();
  }

  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 1) parseSerialData(inputBuffer);
      inputBuffer = "";
    } else inputBuffer += c;
  }

  if (cmd == "" && showWelcomeFlag) {
    showWelcomeScreen();
    showWelcomeFlag = false;
  }
}

void runClock() {
  if (millis() - lastSecond >= 1000) {
    lastSecond = millis();
    sec++;
    if (sec >= 60) { sec = 0; min++; }
    if (min >= 60) { min = 0; hour++; }
    if (hour >= 24) hour = 0;
    showWelcomeFlag = true;
  }
}

// ==================== 欢迎界面 ====================
void showWelcomeScreen() {
  RSCG12864B.clear();
  print16_Center(10, str_welcome);

  char dateBuf[20];
  sprintf(dateBuf, "%04d-%02d-%02d", year, month, day);
  int w = getStr12Width(dateBuf);
  int x = (128 - w) / 2 + 30;
  RSCG12864B.print_string_12_xy(x, 30, dateBuf);

  char timeBuf[20];
  sprintf(timeBuf, "%02d:%02d:%02d", hour, min, sec);
  print16_Center(48, timeBuf);
}

// ==================== 解析指令 ====================
void parseSerialData(String data) {
  cmd = "";
  String plateStr = "";
  int spacePos = data.indexOf(' ');

  if (spacePos != -1) {
    cmd = data.substring(0, spacePos);
    plateStr = data.substring(spacePos + 1);
  }

  char plateBuf[50];
  convertPlate(plateStr, plateBuf);

  RSCG12864B.clear();
  printPlateLine_Center(12, str_car, plateBuf);

  if (cmd == "ALLOW") {
    beep();               // 滴一声
    print16_Center(36, str_allow);
    openGate();           // 舵机开门
    delay(2000);
  } 
  else if (cmd == "DENY") {
    beepTwice();          // 滴两声
    print16_Center(36, str_deny);
    delay(2000);
  }

  cmd = "";
  showWelcomeFlag = true;
}