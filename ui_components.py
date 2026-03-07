# ui_components.py - TKinter界面组件
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import cv2
import imutils
import numpy as np
import threading
import time
import csv
from datetime import datetime
from PIL import Image, ImageTk
from config import *
from plate_recognition_core import PlateRecognitionCore


# 静默输出重定向（可选）
class QuietStream:
    def write(self, text):
        pass

    def flush(self):
        pass


class LicensePlateRecognitionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("车牌识别计时收费控制系统（全自动版）")
        self.root.geometry("1400x900")
        self.root.resizable(True, True)

        # 核心识别实例
        self.recognition_core = PlateRecognitionCore()

        # 系统状态
        self.is_running = False
        self.camera_thread = None
        self.cap = None

        # 配置变量
        self.config = {
            "camera_index": CAMERA_INDEX,
            "serial_port": SERIAL_PORT,
            "baud_rate": BAUD_RATE,
            "plate_whitelist": DEFAULT_WHITELIST.copy()
        }

        # 计时收费相关
        self.parking_config = {
            "base_minutes": BASE_MINUTES,
            "base_fee": BASE_FEE,
            "unit_price": UNIT_PRICE,
            "max_fee_per_day": MAX_FEE_PER_DAY
        }
        self.parking_records = {}  # 在场车辆 {车牌: {in_time, in_datetime}}
        self.payment_records = []  # 收费记录
        self.current_fee_result = None  # 当前计费结果

        # 自动模式相关
        self.auto_in_out_enabled = tk.BooleanVar(value=True)
        self.last_recognized_plate = ""
        self.last_recognize_time = 0

        # 创建界面
        self.create_notebook_widgets()

        # 窗口关闭回调
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_notebook_widgets(self):
        """创建标签页界面"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 标签页1：基础控制
        control_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(control_frame, text="基础控制")
        self.create_control_widgets(control_frame)

        # 标签页2：计时收费
        payment_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(payment_frame, text="计时收费")
        self.create_payment_widgets(payment_frame)

        # 配置权重
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

    def create_control_widgets(self, parent):
        """创建基础控制界面"""
        # 1. 参数配置区
        config_frame = ttk.LabelFrame(parent, text="参数配置", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        # 摄像头索引
        ttk.Label(config_frame, text="摄像头索引:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.camera_index_var = tk.StringVar(value=str(self.config["camera_index"]))
        ttk.Entry(config_frame, textvariable=self.camera_index_var, width=10).grid(row=0, column=1, padx=5, pady=3)

        # 串口配置
        ttk.Label(config_frame, text="串口端口:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=3)
        self.serial_port_var = tk.StringVar(value=self.config["serial_port"])
        ttk.Entry(config_frame, textvariable=self.serial_port_var, width=10).grid(row=0, column=3, padx=5, pady=3)

        ttk.Label(config_frame, text="波特率:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=3)
        self.baud_rate_var = tk.StringVar(value=str(self.config["baud_rate"]))
        ttk.Entry(config_frame, textvariable=self.baud_rate_var, width=10).grid(row=0, column=5, padx=5, pady=3)

        # 白名单
        ttk.Label(config_frame, text="白名单车牌(逗号分隔):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        whitelist_text = ", ".join(self.config["plate_whitelist"])
        self.whitelist_var = tk.StringVar(value=whitelist_text)
        ttk.Entry(config_frame, textvariable=self.whitelist_var, width=50).grid(row=1, column=1, columnspan=5, padx=5,
                                                                                pady=3)

        # 保存配置按钮
        ttk.Button(config_frame, text="保存配置", command=self.save_config).grid(row=2, column=0, columnspan=6, pady=5)

        # 2. 操作按钮区
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        self.start_btn = ttk.Button(button_frame, text="启动识别", command=self.start_recognition)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="停止识别", command=self.stop_recognition, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)

        # 自动模式开关
        auto_switch = ttk.Checkbutton(
            button_frame,
            text="自动出入场模式",
            variable=self.auto_in_out_enabled,
            command=self.on_auto_mode_switch
        )
        auto_switch.grid(row=0, column=2, padx=10)

        ttk.Button(button_frame, text="清空缓存", command=self.clear_plate_cache).grid(row=0, column=3, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_log).grid(row=0, column=4, padx=5)
        ttk.Button(button_frame, text="保存日志", command=self.save_log).grid(row=0, column=5, padx=5)

        # 3. 实时监控区
        monitor_frame = ttk.LabelFrame(parent, text="实时监控", padding="10")
        monitor_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 视频显示
        self.video_label = ttk.Label(monitor_frame)
        self.video_label.grid(row=0, column=0)

        # 状态显示
        status_frame = ttk.Frame(monitor_frame)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(status_frame, text="当前状态：").grid(row=0, column=0, sticky=tk.W)
        self.status_var = tk.StringVar(value="未运行")
        ttk.Label(status_frame, textvariable=self.status_var, foreground="red").grid(row=0, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="最后识别车牌：").grid(row=0, column=2, sticky=tk.W, padx=10)
        self.last_plate_var = tk.StringVar(value="无")
        ttk.Label(status_frame, textvariable=self.last_plate_var).grid(row=0, column=3, sticky=tk.W)

        # 4. 日志显示区
        log_frame = ttk.LabelFrame(parent, text="系统日志", padding="10")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, width=120, height=15, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置权重
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(3, weight=1)

    def create_payment_widgets(self, parent):
        """创建计时收费界面"""
        # 1. 收费规则配置区
        rule_frame = ttk.LabelFrame(parent, text="收费规则配置", padding="10")
        rule_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        # 基础时长
        ttk.Label(rule_frame, text="基础时长(分钟):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.base_minutes_var = tk.StringVar(value=str(self.parking_config["base_minutes"]))
        ttk.Entry(rule_frame, textvariable=self.base_minutes_var, width=10).grid(row=0, column=1, padx=5, pady=3)

        # 基础费用
        ttk.Label(rule_frame, text="基础费用(元):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=3)
        self.base_fee_var = tk.StringVar(value=str(self.parking_config["base_fee"]))
        ttk.Entry(rule_frame, textvariable=self.base_fee_var, width=10).grid(row=0, column=3, padx=5, pady=3)

        # 超时单价
        ttk.Label(rule_frame, text="超时单价(元/60分钟):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.unit_price_var = tk.StringVar(value=str(self.parking_config["unit_price"]))
        ttk.Entry(rule_frame, textvariable=self.unit_price_var, width=10).grid(row=1, column=1, padx=5, pady=3)

        # 单日最高费用
        ttk.Label(rule_frame, text="单日最高费用(元):").grid(row=1, column=2, sticky=tk.W, padx=5, pady=3)
        self.max_fee_var = tk.StringVar(value=str(self.parking_config["max_fee_per_day"]))
        ttk.Entry(rule_frame, textvariable=self.max_fee_var, width=10).grid(row=1, column=3, padx=5, pady=3)

        # 保存规则按钮
        ttk.Button(rule_frame, text="保存收费规则", command=self.save_parking_rules).grid(row=2, column=0, columnspan=4,
                                                                                          pady=5)

        # 2. 入场出场操作区
        op_frame = ttk.LabelFrame(parent, text="手动入场出场操作", padding="10")
        op_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        # 车牌输入
        ttk.Label(op_frame, text="车牌号码:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.plate_input_var = tk.StringVar()
        plate_entry = ttk.Entry(op_frame, textvariable=self.plate_input_var, width=20)
        plate_entry.grid(row=0, column=1, padx=5, pady=3)
        plate_entry.bind('<Return>', lambda e: self.register_entry())

        # 操作按钮
        ttk.Button(op_frame, text="手动入场", command=self.register_entry).grid(row=0, column=2, padx=5, pady=3)
        ttk.Button(op_frame, text="手动出场计费", command=self.calculate_fee).grid(row=0, column=3, padx=5, pady=3)
        ttk.Button(op_frame, text="完成缴费", command=self.confirm_payment).grid(row=0, column=4, padx=5, pady=3)

        # 3. 计费结果显示区
        result_frame = ttk.LabelFrame(parent, text="计费结果", padding="10")
        result_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)

        self.fee_result_text = scrolledtext.ScrolledText(result_frame, width=80, height=5, wrap=tk.WORD)
        self.fee_result_text.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=3)

        # 4. 在场车辆列表
        parking_frame = ttk.LabelFrame(parent, text="在场车辆", padding="10")
        parking_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.parking_tree = ttk.Treeview(parking_frame, columns=("plate", "in_time"), show="headings", height=8)
        self.parking_tree.heading("plate", text="车牌号码")
        self.parking_tree.heading("in_time", text="入场时间")
        self.parking_tree.column("plate", width=150)
        self.parking_tree.column("in_time", width=200)
        self.parking_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 右键菜单
        parking_menu = tk.Menu(self.root, tearoff=0)
        parking_menu.add_command(label="手动出场计费", command=self.on_parking_tree_select)
        self.parking_tree.bind("<Button-3>", lambda e: parking_menu.post(e.x_root, e.y_root))

        # 5. 收费记录列表
        record_frame = ttk.LabelFrame(parent, text="收费记录", padding="10")
        record_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.payment_tree = ttk.Treeview(record_frame,
                                         columns=("plate", "in_time", "out_time", "duration", "fee", "pay_status"),
                                         show="headings", height=10)
        self.payment_tree.heading("plate", text="车牌")
        self.payment_tree.heading("in_time", text="入场时间")
        self.payment_tree.heading("out_time", text="出场时间")
        self.payment_tree.heading("duration", text="停车时长(分钟)")
        self.payment_tree.heading("fee", text="费用(元)")
        self.payment_tree.heading("pay_status", text="支付状态")

        # 列宽
        self.payment_tree.column("plate", width=100)
        self.payment_tree.column("in_time", width=180)
        self.payment_tree.column("out_time", width=180)
        self.payment_tree.column("duration", width=120)
        self.payment_tree.column("fee", width=80)
        self.payment_tree.column("pay_status", width=100)

        self.payment_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 导出按钮
        ttk.Button(record_frame, text="导出收费记录", command=self.export_payment_records).grid(row=1, column=0, pady=5)

        # 配置权重
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(4, weight=1)
        parking_frame.columnconfigure(0, weight=1)
        parking_frame.rowconfigure(0, weight=1)
        record_frame.columnconfigure(0, weight=1)
        record_frame.rowconfigure(0, weight=1)

    # ========== 日志与状态管理 ==========
    def log_message(self, msg):
        """添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}\n"
        self.log_text.insert(tk.END, log_msg)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("日志已清空")

    def save_log(self):
        """保存日志到文件"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存日志"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get(1.0, tk.END))
                self.log_message(f"日志已保存到：{file_path}")
                messagebox.showinfo("成功", "日志保存成功！")
            except Exception as e:
                self.log_message(f"日志保存失败：{str(e)}")
                messagebox.showerror("错误", f"保存日志失败：{str(e)}")

    # ========== 配置管理 ==========
    def save_config(self):
        """保存基础配置"""
        try:
            self.config["camera_index"] = int(self.camera_index_var.get())
            self.config["serial_port"] = self.serial_port_var.get()
            self.config["baud_rate"] = int(self.baud_rate_var.get())

            # 更新白名单
            whitelist_str = self.whitelist_var.get().strip()
            if whitelist_str:
                self.config["plate_whitelist"] = set([plate.strip().upper() for plate in whitelist_str.split(",")])
            else:
                self.config["plate_whitelist"] = set()

            self.log_message("配置保存成功")
            messagebox.showinfo("成功", "配置已保存！")
        except Exception as e:
            self.log_message(f"配置保存失败：{str(e)}")
            messagebox.showerror("错误", f"保存配置失败：{str(e)}")

    def save_parking_rules(self):
        """保存收费规则"""
        try:
            self.parking_config["base_minutes"] = int(self.base_minutes_var.get())
            self.parking_config["base_fee"] = float(self.base_fee_var.get())
            self.parking_config["unit_price"] = float(self.unit_price_var.get())
            self.parking_config["max_fee_per_day"] = float(self.max_fee_var.get())

            self.log_message("收费规则保存成功")
            messagebox.showinfo("成功", "收费规则已保存！")
        except Exception as e:
            self.log_message(f"保存收费规则失败：{str(e)}")
            messagebox.showerror("错误", f"保存失败：{str(e)}")

    # ========== 自动模式 ==========
    def on_auto_mode_switch(self):
        """自动模式切换"""
        mode = "开启" if self.auto_in_out_enabled.get() else "关闭"
        self.log_message(f"自动出入场模式{mode}")
        if self.is_running:
            self.status_var.set(f"运行中 - 自动模式{mode}")

    # ========== 车牌缓存管理 ==========
    def clear_plate_cache(self):
        """清空车牌缓存"""
        result = self.recognition_core.clear_plate_cache()
        self.log_message(result)

    # ========== 计时收费核心逻辑 ==========
    def register_entry(self):
        """手动入场"""
        plate_num = self.plate_input_var.get().strip().upper()

        if not plate_num:
            messagebox.showwarning("警告", "请输入车牌号码！")
            return

        if not PLATE_PATTERN.match(plate_num):
            messagebox.showwarning("警告", "车牌格式不正确！")
            return

        if plate_num in self.parking_records:
            messagebox.showwarning("警告", f"车牌{plate_num}已在场，无需重复登记！")
            return

        # 记录入场信息
        current_time = time.time()
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.parking_records[plate_num] = {
            "in_time": current_time,
            "in_datetime": current_datetime
        }

        # 更新界面
        self.update_parking_tree()

        # 日志
        self.log_message(f"【手动入场】{plate_num}，时间：{current_datetime}")
        self.fee_result_text.insert(tk.END, f"【手动入场】{plate_num} - 入场时间：{current_datetime}\n")
        self.fee_result_text.see(tk.END)

        # 清空输入
        self.plate_input_var.set("")
        messagebox.showinfo("成功", f"车牌{plate_num}入场登记成功！")

    def auto_entry_exit(self, plate_num):
        """自动出入场"""
        # 防抖
        current_time = time.time()
        if plate_num == self.last_recognized_plate and current_time - self.last_recognize_time < RECOGNIZE_DEBOUNCE:
            return

        self.last_recognized_plate = plate_num
        self.last_recognize_time = current_time
        self.last_plate_var.set(plate_num)

        if not plate_num or not PLATE_PATTERN.match(plate_num):
            return

        # 自动入场
        if plate_num not in self.parking_records:
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.parking_records[plate_num] = {
                "in_time": current_time,
                "in_datetime": current_datetime
            }

            self.update_parking_tree()
            self.log_message(f"【自动入场】{plate_num}，时间：{current_datetime}")
            self.fee_result_text.insert(tk.END, f"【自动入场】{plate_num} - 入场时间：{current_datetime}\n")
            self.fee_result_text.see(tk.END)

            # 发送放行指令
            _, msg = self.recognition_core.send_serial_data(plate_num, True, self.auto_in_out_enabled.get())
            self.log_message(msg)

        # 自动出场
        else:
            fee_result, error = self.calculate_parking_fee(plate_num)
            if error:
                self.log_message(f"【自动出场失败】{plate_num} - {error}")
                return

            # 自动缴费
            fee_result["pay_status"] = "已支付"
            self.payment_records.append(fee_result)

            # 移除在场记录
            del self.parking_records[plate_num]

            # 更新界面
            self.update_parking_tree()
            self.update_payment_tree()

            # 日志
            log_msg = f"【自动出场】{plate_num} | 时长:{fee_result['duration']}分钟 | 费用:{fee_result['fee']}元"
            self.log_message(log_msg)
            self.fee_result_text.insert(tk.END, f"{log_msg}\n")
            self.fee_result_text.see(tk.END)

            # 发送放行指令
            _, msg = self.recognition_core.send_serial_data(plate_num, True, self.auto_in_out_enabled.get())
            self.log_message(msg)

    def calculate_parking_fee(self, plate_num):
        """计算停车费用"""
        if plate_num not in self.parking_records:
            return None, "车牌未在场，无法计费！"

        # 入场时间
        in_time = self.parking_records[plate_num]["in_time"]
        in_datetime = self.parking_records[plate_num]["in_datetime"]

        # 计算时长
        out_time = time.time()
        out_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration_seconds = out_time - in_time
        duration_minutes = round(duration_seconds / 60)

        # 计费逻辑
        base_minutes = self.parking_config["base_minutes"]
        base_fee = self.parking_config["base_fee"]
        unit_price = self.parking_config["unit_price"]
        unit_minutes = UNIT_MINUTES
        max_fee = self.parking_config["max_fee_per_day"]

        if duration_minutes <= base_minutes:
            fee = base_fee
        else:
            overtime_minutes = duration_minutes - base_minutes
            overtime_units = (overtime_minutes + unit_minutes - 1) // unit_minutes
            fee = base_fee + (overtime_units * unit_price)

        # 最高费用限制
        fee = min(fee, max_fee)
        fee = round(fee, 2)

        result = {
            "plate": plate_num,
            "in_time": in_datetime,
            "out_time": out_datetime,
            "duration": duration_minutes,
            "fee": fee,
            "pay_status": "未支付"
        }

        return result, None

    def calculate_fee(self):
        """手动计费"""
        plate_num = self.plate_input_var.get().strip().upper()

        if not plate_num:
            messagebox.showwarning("警告", "请输入车牌号码！")
            return

        fee_result, error = self.calculate_parking_fee(plate_num)

        if error:
            self.fee_result_text.insert(tk.END, f"【手动计费失败】{plate_num} - {error}\n")
            self.fee_result_text.see(tk.END)
            messagebox.showwarning("警告", error)
            return

        # 显示结果
        result_text = (
            f"【手动计费】{fee_result['plate']}\n"
            f"  入场时间：{fee_result['in_time']}\n"
            f"  出场时间：{fee_result['out_time']}\n"
            f"  停车时长：{fee_result['duration']} 分钟\n"
            f"  应付费用：{fee_result['fee']} 元\n"
            f"  支付状态：{fee_result['pay_status']}\n"
        )
        self.fee_result_text.insert(tk.END, result_text + "\n")
        self.fee_result_text.see(tk.END)

        # 暂存结果
        self.current_fee_result = fee_result

        self.log_message(f"【手动计费】{plate_num}，时长{fee_result['duration']}分钟，费用{fee_result['fee']}元")
        messagebox.showinfo("计费结果", result_text)

    def confirm_payment(self):
        """确认缴费"""
        if not hasattr(self, 'current_fee_result') or not self.current_fee_result:
            messagebox.showwarning("警告", "请先计算停车费用！")
            return

        plate_num = self.current_fee_result["plate"]
        self.current_fee_result["pay_status"] = "已支付"
        self.payment_records.append(self.current_fee_result)

        # 移除在场记录
        if plate_num in self.parking_records:
            del self.parking_records[plate_num]

        # 更新界面
        self.update_parking_tree()
        self.update_payment_tree()

        # 日志
        self.log_message(f"【手动缴费】{plate_num}，费用{self.current_fee_result['fee']}元")
        self.fee_result_text.insert(tk.END, f"【手动缴费完成】{plate_num} - 费用{self.current_fee_result['fee']}元\n")
        self.fee_result_text.see(tk.END)

        # 发送放行指令
        _, msg = self.recognition_core.send_serial_data(plate_num, True, self.auto_in_out_enabled.get())
        self.log_message(msg)

        # 清空
        delattr(self, 'current_fee_result')
        self.plate_input_var.set("")

        messagebox.showinfo("成功", f"车牌{plate_num}缴费成功！费用：{self.current_fee_result['fee']}元")

    def update_parking_tree(self):
        """更新在场车辆列表"""
        for item in self.parking_tree.get_children():
            self.parking_tree.delete(item)

        for plate, record in self.parking_records.items():
            self.parking_tree.insert("", tk.END, values=(plate, record["in_datetime"]))

    def update_payment_tree(self):
        """更新收费记录列表"""
        for item in self.payment_tree.get_children():
            self.payment_tree.delete(item)

        for record in self.payment_records:
            self.payment_tree.insert("", tk.END, values=(
                record["plate"],
                record["in_time"],
                record["out_time"],
                record["duration"],
                record["fee"],
                record["pay_status"]
            ))

    def on_parking_tree_select(self):
        """在场车辆右键选择"""
        selected = self.parking_tree.selection()
        if not selected:
            return

        item = self.parking_tree.item(selected[0])
        plate_num = item["values"][0]
        self.plate_input_var.set(plate_num)
        self.calculate_fee()

    def export_payment_records(self):
        """导出收费记录"""
        if not self.payment_records:
            messagebox.showwarning("警告", "暂无收费记录可导出！")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            title="导出收费记录"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["plate", "in_time", "out_time", "duration", "fee", "pay_status"])
                writer.writeheader()
                writer.writerows(self.payment_records)

            self.log_message(f"收费记录已导出到：{file_path}")
            messagebox.showinfo("成功", f"收费记录导出成功！\n文件路径：{file_path}")
        except Exception as e:
            self.log_message(f"导出收费记录失败：{str(e)}")
            messagebox.showerror("错误", f"导出失败：{str(e)}")

    # ========== 摄像头与识别控制 ==========
    def start_recognition(self):
        """启动识别"""
        if self.is_running:
            return

        # 保存配置
        self.save_config()

        # 初始化串口
        success, msg = self.recognition_core.init_serial(
            self.config["serial_port"],
            self.config["baud_rate"],
            SERIAL_TIMEOUT
        )
        self.log_message(msg)

        # 初始化摄像头
        self.cap = cv2.VideoCapture(self.config["camera_index"])
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        if not self.cap.isOpened():
            self.log_message(f"无法打开摄像头：索引 {self.config['camera_index']}")
            messagebox.showerror("错误", f"无法打开摄像头！\n请检查摄像头索引或连接状态")
            # 关闭串口
            self.recognition_core.close_serial()
            return

        # 更新状态
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        auto_mode = "开启" if self.auto_in_out_enabled.get() else "关闭"
        self.status_var.set(f"运行中 - 自动模式{auto_mode}")

        self.log_message("启动车牌识别系统")

        # 启动摄像头线程
        self.camera_thread = threading.Thread(target=self.camera_worker, daemon=True)
        self.camera_thread.start()

    def stop_recognition(self):
        """停止识别"""
        self.is_running = False

        # 等待线程
        if self.camera_thread:
            self.camera_thread.join(timeout=2)

        # 释放资源
        if self.cap:
            self.cap.release()
        msg = self.recognition_core.close_serial()
        self.log_message(msg)

        # 清空视频
        self.video_label.config(image='')

        # 更新状态
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("未运行")
        self.last_plate_var.set("无")

        self.log_message("停止车牌识别系统")

    def camera_worker(self):
        """摄像头处理线程"""
        detect_counter = 0
        frame_counter = 0
        cached_plate_num = ""

        while self.is_running:
            # 自动清理缓存
            self.recognition_core.clear_sent_plates_cache_auto()

            ret, frame = self.cap.read()
            if not ret:
                self.log_message("无法读取摄像头画面")
                break

            frame = (imutils.resize(frame, width=FRAME_WIDTH))
            output_frame = frame.copy()
            frame_counter += 1

            # 检测识别
            detect_result = self.recognition_core.detect_and_recognize(frame, frame_counter)
            is_plate_detected = detect_result["plate_detected"]
            plate_loc = detect_result["plate_loc"]
            current_plate = detect_result["plate_num"]

            # 防抖
            detect_counter = detect_counter + 1 if is_plate_detected else 0
            is_plate_detected = detect_counter >= DETECT_COUNTER_THRESH

            # 处理识别结果
            if is_plate_detected and plate_loc is not None and current_plate:
                cached_plate_num = current_plate

                # 自动模式
                if self.auto_in_out_enabled.get():
                    self.auto_entry_exit(current_plate)
                else:
                    # 手动模式
                    is_authorized = self.recognition_core.is_plate_authorized(current_plate,
                                                                              self.config["plate_whitelist"])
                    _, msg = self.recognition_core.send_serial_data(current_plate, is_authorized)
                    self.log_message(msg)

                    if is_authorized:
                        self.log_message(f"合法车牌：{current_plate} - 允许通行")
                    else:
                        self.log_message(f"非法车牌：{current_plate} - 禁止通行")

                # 更新最后识别车牌
                self.last_plate_var.set(current_plate)
            else:
                cached_plate_num = ""

            # 绘制结果
            if is_plate_detected and plate_loc is not None:
                x, y, w, h = plate_loc
                if cached_plate_num and (self.recognition_core.is_plate_authorized(cached_plate_num, self.config[
                    "plate_whitelist"]) or self.auto_in_out_enabled.get()):
                    color = (0, 255, 0)  # 绿色
                    text = f"Plate: {cached_plate_num} (ALLOWED)"
                else:
                    color = (0, 0, 255)  # 红色
                    text = f"Plate: {cached_plate_num} (DENIED)" if cached_plate_num else "Detecting Plate..."

                cv2.rectangle(output_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(output_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            else:
                cached_plate_num = ""
                cv2.putText(output_frame, "No Plate Detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # 转换为TK显示格式
            rgb_frame = cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            imgtk = ImageTk.PhotoImage(image=img)

            # 更新界面
            self.video_label.imgtk = imgtk
            self.video_label.config(image=imgtk)

            # 控制帧率
            time.sleep(0.02)

    def on_closing(self):
        """窗口关闭"""
        if self.is_running:
            self.stop_recognition()
        self.root.destroy()