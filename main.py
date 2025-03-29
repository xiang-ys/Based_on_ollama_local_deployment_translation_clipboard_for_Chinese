import os
import re
import time
import json
import queue
import threading
import subprocess
import pyperclip
import requests
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class OllamaTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama 剪贴板翻译器")
        self.root.attributes('-topmost', True)
        
        # 运行状态变量
        self.running = False
        self.last_text = ""
        self.current_model = ""
        self.ollama_running = False
        self.current_popup = None  # 当前打开的弹窗引用
        
        # 创建UI
        self.create_ui()
        
        # 初始检查
        self.check_ollama_status()
        self.update_model_list()
        
        # 启动监控线程
        self.start_monitoring()

    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 状态指示器
        self.status_var = tk.StringVar(value="正在检查Ollama状态...")
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        # 模型选择
        ttk.Label(main_frame, text="选择模型:").grid(row=1, column=0, sticky=tk.W)
        self.model_combobox = ttk.Combobox(main_frame, state="readonly")
        self.model_combobox.grid(row=1, column=1, sticky=(tk.W, tk.E))
        self.model_combobox.bind("<<ComboboxSelected>>", self.on_model_selected)
        
        # 控制按钮
        self.toggle_btn = ttk.Button(main_frame, text="开始监控", command=self.toggle_monitoring)
        self.toggle_btn.grid(row=2, column=0, columnspan=2, pady=5)
        
        # 日志区域
        ttk.Label(main_frame, text="操作日志:").grid(row=3, column=0, sticky=tk.W)
        self.log_text = tk.Text(main_frame, height=10, width=50, state="disabled")
        self.log_text.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # 配置网格权重
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # 设置窗口大小
        self.root.minsize(400, 300)

    def log_message(self, message):
        """在日志区域添加消息"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
    
    def check_ollama_status(self):
        """检查Ollama服务状态"""
        try:
            response = requests.get(f"http://localhost:11434", timeout=2)
            self.ollama_running = True
            self.status_var.set("Ollama服务运行中")
            self.log_message("Ollama服务已启动")
        except:
            self.ollama_running = False
            self.status_var.set("Ollama服务未运行")
            self.log_message("警告: Ollama服务未检测到")
            self.start_ollama_server()

    def start_ollama_server(self):
        """尝试启动Ollama服务"""
        try:
            self.log_message("正在尝试启动Ollama服务...")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(3)
            
            try:
                requests.get(f"http://localhost:11434", timeout=2)
                self.ollama_running = True
                self.status_var.set("Ollama服务运行中")
                self.log_message("Ollama服务启动成功")
            except:
                self.ollama_running = False
                self.status_var.set("Ollama启动失败")
                self.log_message("错误: 无法启动Ollama服务")
        except FileNotFoundError:
            self.log_message("严重错误: 系统未找到ollama命令")

    def update_model_list(self):
        """获取可用模型列表"""
        if not self.ollama_running:
            return
            
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if result.returncode == 0:
                models = []
                for line in result.stdout.split('\n')[1:]:
                    if line.strip():
                        model_name = line.split()[0]
                        models.append(model_name)
                
                self.model_combobox['values'] = models
                if models:
                    self.current_model = models[0]
                    self.model_combobox.set(models[0])
                    self.log_message(f"已加载{len(models)}个模型，默认选择: {models[0]}")
        except Exception as e:
            self.log_message(f"获取模型列表出错: {str(e)}")

    def on_model_selected(self, event):
        """当用户选择新模型时"""
        self.current_model = self.model_combobox.get()
        self.log_message(f"已切换模型: {self.current_model}")

    def toggle_monitoring(self):
        """切换监控状态"""
        self.running = not self.running
        if self.running:
            self.toggle_btn.config(text="停止监控")
            self.log_message("开始监控剪贴板...")
        else:
            self.toggle_btn.config(text="开始监控")
            self.log_message("已停止监控")

    def start_monitoring(self):
        """启动监控线程"""
        def monitoring_thread():
            while True:
                if self.running and self.ollama_running and self.current_model:
                    current_text = pyperclip.paste().strip()
                    
                    if current_text and current_text != self.last_text:
                        if not self.is_chinese(current_text):
                            self.process_text(current_text)
                        self.last_text = current_text
                
                time.sleep(3)
        
        thread = threading.Thread(target=monitoring_thread, daemon=True)
        thread.start()

    def is_chinese(self, text):
        """检测是否包含中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    def process_text(self, text):
        """处理翻译流程"""
        self.log_message(f"检测到新内容: {text[:50]}...")
        
        try:
            translated = self.translate_text(text)
            if translated:
                self.show_translation(text, translated)
        except Exception as e:
            self.log_message(f"翻译出错: {str(e)}")

    def translate_text(self, text):
        """调用Ollama翻译"""
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.current_model,
            "prompt": f"将以下内容翻译为中文，只返回译文不要额外说明:\n{text}",
            "stream": False
        }
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        translated = result.get("response", "").strip()
        
        for prefix in ["译文:", "翻译结果:", "Here is the translation:"]:
            if translated.startswith(prefix):
                translated = translated[len(prefix):].strip()
        
        return translated

    def show_translation(self, original, translated):
        """显示翻译结果弹窗"""
        # 关闭现有弹窗
        if self.current_popup:
            self.current_popup.destroy()
        
        # 创建新弹窗
        popup = tk.Toplevel(self.root)
        popup.title("翻译结果")
        popup.attributes('-topmost', True)
        self.current_popup = popup
        
        # 获取鼠标位置
        x, y = self.root.winfo_pointerxy()
        
        # 原文框
        ttk.Label(popup, text="原文:").pack(anchor=tk.W)
        orig_text = tk.Text(popup, height=5, width=50, wrap=tk.WORD)
        orig_text.pack(fill=tk.X, padx=5, pady=2)
        orig_text.insert(tk.END, original)
        orig_text.config(state="disabled")
        
        # 译文框
        ttk.Label(popup, text="译文:").pack(anchor=tk.W)
        trans_text = tk.Text(popup, height=5, width=50, wrap=tk.WORD)
        trans_text.pack(fill=tk.X, padx=5, pady=2)
        trans_text.insert(tk.END, translated)
        trans_text.config(state="disabled")
        
        # 按钮框
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=5)
        
        def copy_translation():
            pyperclip.copy(translated)
            self.log_message("译文已复制到剪贴板")
            popup.destroy()
            self.current_popup = None
        
        ttk.Button(btn_frame, text="复制", command=copy_translation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=lambda: [popup.destroy(), setattr(self, 'current_popup', None)]).pack(side=tk.RIGHT, padx=5)
        
        # 设置弹窗位置（鼠标位置附近）
        popup.update_idletasks()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        
        # 确保弹窗不会超出屏幕
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        
        x = min(x, screen_width - popup_width - 10)
        y = min(y, screen_height - popup_height - 10)
        
        popup.geometry(f"+{x}+{y}")
        
        # 弹窗关闭时清除引用
        popup.protocol("WM_DELETE_WINDOW", lambda: [popup.destroy(), setattr(self, 'current_popup', None)])

def main():
    root = tk.Tk()
    app = OllamaTranslator(root)
    root.mainloop()

if __name__ == "__main__":
    main()