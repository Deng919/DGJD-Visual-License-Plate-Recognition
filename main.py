# main.py - 程序入口
import sys
import tkinter as tk
from ui_components import LicensePlateRecognitionGUI

# 恢复标准输出（便于调试）
sys_stdout = sys.stdout
sys_stderr = sys.stderr

if __name__ == "__main__":
    # 创建主窗口
    root = tk.Tk()
    # 创建应用实例
    app = LicensePlateRecognitionGUI(root)
    # 运行主循环
    root.mainloop()
