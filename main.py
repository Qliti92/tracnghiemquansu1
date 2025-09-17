#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ứng dụng Trắc nghiệm với CustomTkinter - Phiên bản cải tiến
File: main.py
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import pandas as pd
import random
import time
import os
import csv
from datetime import datetime, timedelta
from pathlib import Path
import threading
import glob

# Cấu hình CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

import textwrap

def _wrap(self, s: str, width: int = 70) -> str:
    # Tự chèn \n để CTkButton hiển thị xuống dòng
    return textwrap.fill(str(s), width=width)

class SplashScreen:
    """Màn hình khởi động (dùng chung root, không tạo root mới)"""
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.top = ctk.CTkToplevel(self.root)
        self.top.title("Khởi động ứng dụng")
        self.top.geometry("400x300")
        self.top.resizable(False, False)
        self.top.overrideredirect(True)

        # Center
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - 200
        y = (self.top.winfo_screenheight() // 2) - 150
        self.top.geometry(f"400x300+{x}+{y}")

        main_frame = ctk.CTkFrame(self.top, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            main_frame, text="🎯 TRẮC NGHIỆM QUÂN SỰ",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(pady=(50, 20))

        ctk.CTkLabel(
            main_frame, text="Phiên bản 1.1 | Trần Đình Quân",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(pady=(0, 20))

        self.progress = ctk.CTkProgressBar(main_frame, width=300)
        self.progress.pack(pady=20)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            main_frame, text="Đang khởi động...", font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=(10, 30))

    def set_progress(self, value: float, status: str = ""):
        self.progress.set(value)
        if status:
            self.status_label.configure(text=status)
        # Không cần update() thủ công; mainloop đang chạy sẽ render

    def close(self):
        self.top.destroy()

class QuizApplication:
    def __init__(self):
        # Chỉ tạo 1 root duy nhất
        self.root = ctk.CTk()
        self.root.title("Ứng dụng Trắc nghiệm v1.1 | Trần Đình Quân")
        self.root.geometry("1400x800")
        self.root.withdraw()  # Ẩn UI chính đến khi nạp xong

        # Cấu hình
        self.config = {
            'exam_time_min': 30,
            'randomize_questions': True,
            'randomize_options': True,
            'theme': 'dark',
            'font_family': 'Inter'
        }

        # Load cấu hình từ .env nếu có
        self.load_config()

        # Dữ liệu
        self.questions = []
        self.current_mode = "practice"
        self.current_question_index = 0
        self.user_answers = {}
        self.question_feedback = {}
        self.exam_start_time = None
        self.exam_time_limit = None
        self.timer_running = False

        # Biến giao diện
        self.selected_answer = tk.StringVar()
        self.selected_option_index = -1
        self.option_buttons = []

    def _wrap(self, s: str, width: int = 70) -> str:
        """Tự động xuống dòng cho text trong nút đáp án"""
        return textwrap.fill(str(s), width=width)

    def initialize_with_splash(self):
        """Khởi tạo ứng dụng với màn hình splash (chạy trên main thread bằng after)"""
        splash = SplashScreen(self.root)

        def step1():
            splash.set_progress(0.2, "Đang tải cấu hình...")
            self.root.after(400, step2)

        def step2():
            splash.set_progress(0.4, "Đang tìm file Excel...")
            excel_found = False
            try:
                excel_found = self.auto_load_excel()
            except Exception as e:
                print("Lỗi tự động tải Excel:", e)
            self._excel_found = excel_found
            self.root.after(400, step3)

        def step3():
            splash.set_progress(0.6, "Đang thiết lập giao diện...")
            self.setup_ui()  # Thiết lập UI chỉ trên main thread
            self.root.after(400, step4)

        def step4():
            splash.set_progress(0.8, "Đang khởi tạo dữ liệu...")
            if not getattr(self, "_excel_found", False):
                self.load_default_data()
            self.root.after(400, step5)

        def step5():
            splash.set_progress(1.0, "Hoàn tất!")
            self.root.after(300, finish)

        def finish():
            splash.close()
            self.root.deiconify()  # Hiển thị cửa sổ chính

        self.root.after(50, step1)

    # ================== CONFIG / DATA ==================
    def load_config(self):
        """Load cấu hình từ file .env"""
        env_path = Path('.env')
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            if key == 'EXAM_TIME_MIN':
                                self.config['exam_time_min'] = int(value)
                            elif key in ['RANDOMIZE_QUESTIONS', 'RANDOMIZE_OPTIONS']:
                                self.config[key.lower()] = value.lower() == 'true'
                            elif key in ['THEME', 'FONT_FAMILY']:
                                self.config[key.lower()] = value
            except Exception as e:
                print(f"Lỗi đọc file .env: {e}")

    def auto_load_excel(self):
        """Tự động tìm và tải file Excel trong thư mục hiện tại"""
        try:
            excel_patterns = ['*.xlsx', '*.xls']
            excel_files = []
            for pattern in excel_patterns:
                excel_files.extend(glob.glob(pattern))
            if not excel_files:
                return False

            priority_keywords = ['cau_hoi', 'tracnghiem', 'quiz', 'question']
            prioritized_files, other_files = [], []
            for file in excel_files:
                if any(k in file.lower() for k in priority_keywords):
                    prioritized_files.append(file)
                else:
                    other_files.append(file)
            target_file = prioritized_files[0] if prioritized_files else other_files[0]
            return self.load_excel_data(target_file)
        except Exception as e:
            print(f"Lỗi tự động tải Excel: {e}")
            return False

    def load_excel_data(self, file_path):
        """Tải dữ liệu từ file Excel"""
        try:
            df = pd.read_excel(file_path)

            required_columns = ['cau_hoi', 'tra_loi_a', 'tra_loi_b', 'tra_loi_c', 'dap_an_dung']
            missing_columns = [c for c in required_columns if c not in df.columns]
            if missing_columns:
                print(f"File Excel thiếu các cột: {', '.join(missing_columns)}")
                return False

            validation_errors = []
            for idx, row in df.iterrows():
                for col in required_columns:
                    if pd.isna(row[col]) or str(row[col]).strip() == '':
                        validation_errors.append(f"Dòng {idx+2}, cột '{col}': Không được để trống")
                if row['dap_an_dung'] not in ['A', 'B', 'C', 'D']:
                    validation_errors.append(f"Dòng {idx+2}: Đáp án đúng phải là A, B, C, hoặc D")
            if validation_errors:
                print("Phát hiện lỗi dữ liệu:", validation_errors[:5])
                return False

            self.questions = []
            for _, row in df.iterrows():
                question_data = {
                    'cau_hoi': str(row['cau_hoi']).strip(),
                    'tra_loi_a': str(row['tra_loi_a']).strip(),
                    'tra_loi_b': str(row['tra_loi_b']).strip(),
                    'tra_loi_c': str(row['tra_loi_c']).strip(),
                    'dap_an_dung': str(row['dap_an_dung']).strip(),
                    'giai_thich': str(row.get('giai_thich', '')).strip()
                }
                tra_loi_d = row.get('tra_loi_d', '')
                if pd.notna(tra_loi_d) and str(tra_loi_d).strip():
                    question_data['tra_loi_d'] = str(tra_loi_d).strip()
                else:
                    question_data['tra_loi_d'] = None
                self.questions.append(question_data)

            self.current_question_index = 0
            self.user_answers = {}
            self.question_feedback = {}

            print(f"Đã tải thành công {len(self.questions)} câu hỏi từ {file_path}")
            return True
        except Exception as e:
            print(f"Lỗi đọc file Excel: {e}")
            return False

    def load_default_data(self):
        """Tải dữ liệu mẫu nếu không có file Excel"""
        sample_data = [
            {
                'cau_hoi': 'Không tìm thấy file Excel câu hỏi. Đây là câu hỏi mẫu: Python được tạo ra bởi ai?',
                'tra_loi_a': 'Guido van Rossum',
                'tra_loi_b': 'Dennis Ritchie',
                'tra_loi_c': 'James Gosling',
                'tra_loi_d': 'Bjarne Stroustrup',
                'dap_an_dung': 'A',
                'giai_thich': 'Guido van Rossum là người tạo ra Python vào năm 1991.'
            },
            {
                'cau_hoi': 'Cú pháp nào dùng để in ra màn hình trong Python?',
                'tra_loi_a': 'echo()',
                'tra_loi_b': 'print()',
                'tra_loi_c': 'printf()',
                'tra_loi_d': None,
                'dap_an_dung': 'B',
                'giai_thich': 'Trong Python, dùng hàm print().'
            }
        ]
        self.questions = sample_data
        self.update_question_display()
        self.update_status()
        if hasattr(self, 'file_info_label'):
            self.file_info_label.configure(text="📄 Dữ liệu mẫu\n2 câu hỏi", text_color="yellow")

    # ================== UI ==================
    def setup_ui(self):
        """Thiết lập giao diện người dùng"""
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.setup_sidebar()
        self.setup_main_content()
        self.setup_status_bar()

    def setup_sidebar(self):
        """Thiết lập sidebar trái"""
        self.sidebar = ctk.CTkFrame(self.root, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(
            self.sidebar, text="🎯 Trắc Nghiệm Quân Sự", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(30, 20), sticky="ew")

        self.practice_btn = ctk.CTkButton(
            self.sidebar, text="📚 Luyện tập", font=ctk.CTkFont(size=18), height=50,
            command=lambda: self.switch_mode("practice")
        )
        self.practice_btn.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.exam_btn = ctk.CTkButton(
            self.sidebar, text="📝 Thi", font=ctk.CTkFont(size=18), height=50,
            command=lambda: self.switch_mode("exam")
        )
        self.exam_btn.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        load_btn = ctk.CTkButton(
            self.sidebar, text="📁 Tải file Excel khác", font=ctk.CTkFont(size=14), height=35,
            command=self.load_excel_file_manual
        )
        load_btn.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(
            self.sidebar, text="⚙️ Cài đặt", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=4, column=0, padx=20, pady=(20, 10), sticky="w")

        self.random_questions_switch = ctk.CTkSwitch(
            self.sidebar, text="Ngẫu nhiên câu hỏi", font=ctk.CTkFont(size=14)
        )
        self.random_questions_switch.grid(row=5, column=0, padx=20, pady=5, sticky="w")
        if self.config['randomize_questions']:
            self.random_questions_switch.select()

        self.random_options_switch = ctk.CTkSwitch(
            self.sidebar, text="Ngẫu nhiên đáp án (Đang phát triển)", font=ctk.CTkFont(size=14)
        )
        self.random_options_switch.grid(row=6, column=0, padx=20, pady=5, sticky="w")
        if self.config['randomize_options']:
            self.random_options_switch.select()

        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, text="Dark Mode", font=ctk.CTkFont(size=14),
            command=self.toggle_theme
        )
        self.theme_switch.grid(row=7, column=0, padx=20, pady=5, sticky="w")
        if self.config['theme'] == 'dark':
            self.theme_switch.select()

        self.file_info_label = ctk.CTkLabel(
            self.sidebar, text="Đang tải dữ liệu...", font=ctk.CTkFont(size=12), text_color="orange"
        )
        self.file_info_label.grid(row=11, column=0, padx=20, pady=20, sticky="ew")

    def setup_main_content(self):
        """Thiết lập vùng nội dung chính"""
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.setup_navigation_header()
        self.setup_question_content()
        self.setup_control_footer()

    def setup_navigation_header(self):
        nav_frame = ctk.CTkFrame(self.main_frame)
        nav_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        nav_frame.grid_columnconfigure(1, weight=1)

        self.prev_btn = ctk.CTkButton(
            nav_frame, text="⬅ Câu trước", font=ctk.CTkFont(size=14), width=100,
            command=self.previous_question
        )
        self.prev_btn.grid(row=0, column=0, padx=10, pady=10)

        self.question_progress_label = ctk.CTkLabel(
            nav_frame, text="Câu 1/10", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.question_progress_label.grid(row=0, column=1, pady=10)

        self.next_btn = ctk.CTkButton(
            nav_frame, text="Câu sau ➡", font=ctk.CTkFont(size=14), width=100,
            command=self.next_question
        )
        self.next_btn.grid(row=0, column=2, padx=10, pady=10)

    def setup_question_content(self):
        self.content_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.question_label = ctk.CTkLabel(
            self.content_frame, text="Đang tải câu hỏi...", font=ctk.CTkFont(size=18, weight="bold"),
            wraplength=850, justify="left"
        )
        self.question_label.grid(row=0, column=0, sticky="ew", padx=20, pady=20)

        self.options_frame = ctk.CTkFrame(self.content_frame)
        self.options_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.options_frame.grid_columnconfigure(0, weight=1)

        self.option_buttons = []
        for i in range(4):
            option_btn = ctk.CTkButton(
                self.options_frame,
                text=f"{chr(65+i)}. Đáp án {chr(65+i)}",
                font=ctk.CTkFont(size=14),
                height=40,
                anchor="w",
                fg_color="gray25",
                hover_color="gray30",
                text_color="white",
                command=lambda idx=i: self.select_option(chr(65+idx))
            )
            option_btn.grid(row=i, column=0, sticky="ew", padx=30, pady=5)
            self.option_buttons.append(option_btn)

        self.feedback_frame = ctk.CTkFrame(self.content_frame)
        self.feedback_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        self.feedback_frame.grid_columnconfigure(0, weight=1)

        self.feedback_label = ctk.CTkLabel(
            self.feedback_frame, text="", font=ctk.CTkFont(size=16), wraplength=750
        )
        self.feedback_label.grid(row=0, column=0, padx=20, pady=15)

        self.explanation_label = ctk.CTkLabel(
            self.feedback_frame, text="", font=ctk.CTkFont(size=14),
            wraplength=750, text_color="gray"
        )
        self.explanation_label.grid(row=1, column=0, padx=20, pady=(0, 15))

        self.feedback_frame.grid_remove()

    def setup_control_footer(self):
        control_frame = ctk.CTkFrame(self.main_frame)
        control_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        control_frame.grid_columnconfigure(1, weight=1)

        self.check_btn = ctk.CTkButton(
            control_frame, text="✓ Kiểm tra", font=ctk.CTkFont(size=16),
            height=40, command=self.check_answer
        )
        self.check_btn.grid(row=0, column=0, padx=10, pady=10)

        self.submit_btn = ctk.CTkButton(
            control_frame, text="📋 Nộp bài", font=ctk.CTkFont(size=16), height=40,
            fg_color="orange", hover_color="darkorange", command=self.submit_exam
        )
        self.submit_btn.grid(row=0, column=2, padx=10, pady=10)
        self.submit_btn.grid_remove()

    def setup_status_bar(self):
        status_frame = ctk.CTkFrame(self.root, height=50, corner_radius=0)
        status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        self.mode_label = ctk.CTkLabel(
            status_frame, text="📚 Chế độ: Luyện tập", font=ctk.CTkFont(size=14)
        )
        self.mode_label.grid(row=0, column=0, padx=20, pady=10)

        self.stats_label = ctk.CTkLabel(
            status_frame, text="Câu đã trả lời: 0/0", font=ctk.CTkFont(size=14)
        )
        self.stats_label.grid(row=0, column=1, pady=10)

        self.timer_label = ctk.CTkLabel(
            status_frame, text="", font=ctk.CTkFont(size=14, weight="bold"),
            text_color="orange"
        )
        self.timer_label.grid(row=0, column=2, padx=20, pady=10)

    # ================== LOGIC ==================
    def select_option(self, option_letter):
        """Xử lý khi người dùng chọn đáp án"""
        self.selected_answer.set(option_letter)
        for i, btn in enumerate(self.option_buttons):
            if chr(65+i) == option_letter:
                btn.configure(fg_color="blue", hover_color="darkblue")
                self.selected_option_index = i
            else:
                btn.configure(fg_color="gray25", hover_color="gray30")

    def load_excel_file_manual(self):
        """Tải file Excel thủ công"""
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not file_path:
            return

        if self.load_excel_data(file_path):
            if self.random_questions_switch.get():
                random.shuffle(self.questions)
            self.update_question_display()
            self.update_status()

            file_name = os.path.basename(file_path)
            self.file_info_label.configure(
                text=f"📄 {file_name}\n{len(self.questions)} câu hỏi",
                text_color="lightgreen"
            )
            messagebox.showinfo("Thành công", f"Đã tải {len(self.questions)} câu hỏi từ file Excel!")
        else:
            messagebox.showerror("Lỗi", "Không thể đọc file Excel. Vui lòng kiểm tra định dạng file.")

    def update_question_display(self):
        """Cập nhật hiển thị câu hỏi"""
        if not self.questions:
            self.question_label.configure(text="Không có câu hỏi nào. Vui lòng tải file Excel.")
            return

        if self.current_question_index >= len(self.questions):
            self.current_question_index = len(self.questions) - 1

        question = self.questions[self.current_question_index]
        self.question_progress_label.configure(
            text=f"Câu {self.current_question_index + 1}/{len(self.questions)}"
        )
        self.question_label.configure(text=question['cau_hoi'])

        options = [
            ('A', question['tra_loi_a']),
            ('B', question['tra_loi_b']),
            ('C', question['tra_loi_c'])
        ]
        if question.get('tra_loi_d'):
            options.append(('D', question['tra_loi_d']))

        if self.random_options_switch.get():
            random.shuffle(options)

        for i in range(4):
            if i < len(options):
                letter, text = options[i]
                self.option_buttons[i].configure(
                    text=f"{letter}. {textwrap.fill(str(text), 70)}",

                    state="normal"
                )
                self.option_buttons[i].grid()
            else:
                self.option_buttons[i].grid_remove()

        current_answer = self.user_answers.get(self.current_question_index, "")
        self.selected_answer.set(current_answer)

        for i, btn in enumerate(self.option_buttons):
            if i < len(options) and chr(65+i) == current_answer:
                btn.configure(fg_color="blue", hover_color="darkblue")
                self.selected_option_index = i
            else:
                btn.configure(fg_color="gray25", hover_color="gray30")

        self.prev_btn.configure(state="normal" if self.current_question_index > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_question_index < len(self.questions) - 1 else "disabled")

        if self.current_mode == "practice":
            if self.current_question_index in self.question_feedback:
                fb = self.question_feedback[self.current_question_index]
                self.show_feedback(fb['correct'], fb['explanation'])
            else:
                self.hide_feedback()
        else:
            self.hide_feedback()

        if hasattr(self, 'file_info_label') and self.questions:
            if len(self.questions) > 2:
                self.file_info_label.configure(
                    text=f"📄 File đã tải\n{len(self.questions)} câu hỏi",
                    text_color="lightgreen"
                )

    def switch_mode(self, mode):
        """Chuyển đổi chế độ luyện tập/thi"""
        if mode == self.current_mode:
            return

        self.current_mode = mode
        self.user_answers = {}
        self.question_feedback = {}
        self.current_question_index = 0

        if mode == "practice":
            self.mode_label.configure(text="📚 Chế độ: Luyện tập")
            self.check_btn.grid()
            self.submit_btn.grid_remove()
            self.practice_btn.configure(fg_color=("gray75", "gray25"))
            self.exam_btn.configure(fg_color=("blue", "blue"))
            self.stop_timer()
        elif mode == "exam":
            self.mode_label.configure(text="📝 Chế độ: Thi")
            self.check_btn.grid_remove()
            self.submit_btn.grid()
            self.exam_btn.configure(fg_color=("gray75", "gray25"))
            self.practice_btn.configure(fg_color=("blue", "blue"))
            self.start_exam_timer()

        self.update_question_display()
        self.update_status()

    def start_exam_timer(self):
        self.exam_start_time = datetime.now()
        self.exam_time_limit = self.exam_start_time + timedelta(minutes=self.config['exam_time_min'])
        self.timer_running = True
        self.update_timer()

    def update_timer(self):
        if not self.timer_running or self.current_mode != "exam":
            self.timer_label.configure(text="")
            return

        now = datetime.now()
        remaining = self.exam_time_limit - now
        if remaining.total_seconds() <= 0:
            self.timer_label.configure(text="⏰ Hết giờ!", text_color="red")
            self.timer_running = False
            messagebox.showwarning("Hết giờ", "Thời gian làm bài đã hết! Tự động nộp bài.")
            self.submit_exam()
            return

        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        color = "red" if minutes < 5 else "orange"
        self.timer_label.configure(text=f"⏰ Thời gian: {minutes:02d}:{seconds:02d}", text_color=color)
        self.root.after(1000, self.update_timer)

    def stop_timer(self):
        self.timer_running = False
        self.timer_label.configure(text="")

    def previous_question(self):
        if self.current_question_index > 0:
            if self.selected_answer.get():
                self.user_answers[self.current_question_index] = self.selected_answer.get()
            self.current_question_index -= 1
            self.update_question_display()

    def next_question(self):
        if self.current_question_index < len(self.questions) - 1:
            if self.selected_answer.get():
                self.user_answers[self.current_question_index] = self.selected_answer.get()
            self.current_question_index += 1
            self.update_question_display()

    def check_answer(self):
        if not self.selected_answer.get():
            messagebox.showwarning("Chưa chọn đáp án", "Vui lòng chọn một đáp án trước khi kiểm tra!")
            return

        self.user_answers[self.current_question_index] = self.selected_answer.get()
        question = self.questions[self.current_question_index]
        correct_answer = question['dap_an_dung']
        user_answer = self.selected_answer.get()
        is_correct = user_answer == correct_answer
        explanation = question.get('giai_thich', '')

        self.question_feedback[self.current_question_index] = {
            'correct': is_correct,
            'explanation': explanation
        }
        self.show_feedback(is_correct, explanation)
        self.update_status()

    def show_feedback(self, is_correct, explanation=""):
        self.feedback_frame.grid()

        question = self.questions[self.current_question_index]
        correct_answer = question['dap_an_dung']
        user_answer = self.selected_answer.get()

        for i, btn in enumerate(self.option_buttons):
            option_letter = chr(65+i)
            try:
                btn.winfo_viewable()
                if option_letter == correct_answer:
                    btn.configure(fg_color="green", hover_color="darkgreen")
                elif option_letter == user_answer and user_answer != correct_answer:
                    btn.configure(fg_color="red", hover_color="darkred")
                else:
                    btn.configure(fg_color="gray40", hover_color="gray45")
            except:
                continue

        if is_correct:
            self.feedback_label.configure(text="✅ Chính xác! Bạn đã chọn đúng.", text_color="lightgreen")
        else:
            self.feedback_label.configure(text=f"❌ Sai rồi! Đáp án đúng là: {correct_answer}", text_color="lightcoral")

        if explanation:
            self.explanation_label.configure(text=f"💡 Giải thích: {explanation}")
        else:
            self.explanation_label.configure(text="")

    def hide_feedback(self):
        self.feedback_frame.grid_remove()
        current_answer = self.selected_answer.get()
        for i, btn in enumerate(self.option_buttons):
            try:
                btn.winfo_viewable()
                if chr(65+i) == current_answer:
                    btn.configure(fg_color="blue", hover_color="darkblue")
                else:
                    btn.configure(fg_color="gray25", hover_color="gray30")
            except:
                continue

    def submit_exam(self):
        if self.selected_answer.get():
            self.user_answers[self.current_question_index] = self.selected_answer.get()

        unanswered = [i + 1 for i in range(len(self.questions)) if i not in self.user_answers or not self.user_answers[i]]
        if unanswered:
            unanswered_str = ", ".join(map(str, unanswered[:10]))
            if len(unanswered) > 10:
                unanswered_str += f" và {len(unanswered)-10} câu khác"
            result = messagebox.askyesno("Xác nhận nộp bài", f"Bạn chưa trả lời câu: {unanswered_str}\n\nBạn có chắc chắn muốn nộp bài không?")
            if not result:
                return
        else:
            result = messagebox.askyesno("Xác nhận nộp bài", "Bạn có chắc chắn muốn nộp bài không?")
            if not result:
                return

        self.stop_timer()
        self.show_results()

    def show_results(self):
        correct_count = 0
        total_questions = len(self.questions)
        results_data = []

        for i, question in enumerate(self.questions):
            user_answer = self.user_answers.get(i, "")
            correct_answer = question['dap_an_dung']
            is_correct = user_answer == correct_answer
            if is_correct:
                correct_count += 1
            results_data.append({
                'stt': i + 1,
                'cau_hoi': question['cau_hoi'],
                'lua_chon': user_answer or "Không trả lời",
                'dap_an_dung': correct_answer,
                'ket_qua': "Đúng" if is_correct else "Sai",
                'giai_thich': question.get('giai_thich', '')
            })

        score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        exam_duration = ""
        if self.exam_start_time:
            duration = datetime.now() - self.exam_start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            exam_duration = f"{minutes} phút {seconds} giây"

        self.show_results_window(correct_count, total_questions, score_percentage, exam_duration, results_data)

    def show_results_window(self, correct_count, total_questions, score_percentage, exam_duration, results_data):
        results_window = ctk.CTkToplevel(self.root)
        results_window.title("Kết quả bài thi")
        results_window.geometry("1000x700")
        results_window.transient(self.root)
        results_window.grab_set()

        header_frame = ctk.CTkFrame(results_window)
        header_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(header_frame, text="🏆 KẾT QUẢ BÀI THI", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)

        stats_frame = ctk.CTkFrame(header_frame)
        stats_frame.pack(fill="x", padx=20, pady=10)
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            stats_frame, text=f"📊 Điểm số\n{score_percentage:.1f}%",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="lightgreen" if score_percentage >= 80 else "orange" if score_percentage >= 60 else "lightcoral"
        ).grid(row=0, column=0, padx=20, pady=15)

        ctk.CTkLabel(
            stats_frame, text=f"✅ Kết quả\n{correct_count}/{total_questions} câu đúng",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=1, padx=20, pady=15)

        if exam_duration:
            ctk.CTkLabel(
                stats_frame, text=f"⏰ Thời gian\n{exam_duration}", font=ctk.CTkFont(size=16, weight="bold")
            ).grid(row=0, column=2, padx=20, pady=15)

        list_frame = ctk.CTkFrame(results_window)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ctk.CTkLabel(
            list_frame, text="📋 Chi tiết từng câu hỏi:", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        scrollable_frame = ctk.CTkScrollableFrame(list_frame, height=300)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for result in results_data:
            result_item = ctk.CTkFrame(scrollable_frame)
            result_item.pack(fill="x", pady=5)

            status_color = "lightgreen" if result['ket_qua'] == "Đúng" else "lightcoral"
            status_icon = "✅" if result['ket_qua'] == "Đúng" else "❌"

            ctk.CTkLabel(
                result_item, text=f"{status_icon} Câu {result['stt']}",
                font=ctk.CTkFont(size=14, weight="bold"), text_color=status_color
            ).pack(anchor="w", padx=15, pady=(10, 5))

            question_text = result['cau_hoi']
            if len(question_text) > 100:
                question_text = question_text[:100] + "..."
            ctk.CTkLabel(
                result_item, text=f"❓ {question_text}", font=ctk.CTkFont(size=12),
                anchor="w", wraplength=900
            ).pack(fill="x", padx=15, pady=2)

            ctk.CTkLabel(
                result_item, text=f"👤 Bạn chọn: {result['lua_chon']} | ✓ Đáp án đúng: {result['dap_an_dung']}",
                font=ctk.CTkFont(size=12), text_color="gray"
            ).pack(anchor="w", padx=15, pady=(2, 10))

        footer_frame = ctk.CTkFrame(results_window)
        footer_frame.pack(fill="x", padx=20, pady=(0, 20))
        button_frame = ctk.CTkFrame(footer_frame)
        button_frame.pack(pady=15)

        ctk.CTkButton(
            button_frame, text="📄 Xuất kết quả (CSV)", font=ctk.CTkFont(size=14),
            command=lambda: self.export_results(results_data, correct_count, total_questions, score_percentage, exam_duration)
        ).pack(side="left", padx=10)

        wrong_questions = [r for r in results_data if r['ket_qua'] == "Sai"]
        if wrong_questions:
            ctk.CTkButton(
                button_frame, text=f"🔍 Xem {len(wrong_questions)} câu sai",
                font=ctk.CTkFont(size=14), fg_color="orange", hover_color="darkorange",
                command=lambda: self.show_wrong_answers(wrong_questions)
            ).pack(side="left", padx=10)

        ctk.CTkButton(button_frame, text="❌ Đóng", font=ctk.CTkFont(size=14), command=results_window.destroy)\
            .pack(side="left", padx=10)

    def export_results(self, results_data, correct_count, total_questions, score_percentage, exam_duration):
        try:
            file_path = filedialog.asksaveasfilename(
                title="Lưu kết quả",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialname=f"ket_qua_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            if not file_path:
                return

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                csvfile.write(f"# KẾT QUẢ BÀI THI\n")
                csvfile.write(f"# Ngày thi: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                csvfile.write(f"# Điểm số: {score_percentage:.1f}%\n")
                csvfile.write(f"# Số câu đúng: {correct_count}/{total_questions}\n")
                if exam_duration:
                    csvfile.write(f"# Thời gian làm bài: {exam_duration}\n")
                csvfile.write(f"#\n")

                writer = csv.writer(csvfile)
                writer.writerow(['STT', 'Câu hỏi', 'Lựa chọn', 'Đáp án đúng', 'Kết quả', 'Giải thích'])
                for r in results_data:
                    writer.writerow([r['stt'], r['cau_hoi'], r['lua_chon'], r['dap_an_dung'], r['ket_qua'], r['giai_thich']])

            messagebox.showinfo("Thành công", f"Đã xuất kết quả ra file:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất file:\n{str(e)}")

    def show_wrong_answers(self, wrong_questions):
        wrong_window = ctk.CTkToplevel(self.root)
        wrong_window.title("Câu trả lời sai")
        wrong_window.geometry("900x600")
        wrong_window.transient(self.root)

        ctk.CTkLabel(
            wrong_window, text=f"🔍 XEM LẠI {len(wrong_questions)} CÂU TRẢ LỜI SAI",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=20)

        scrollable_frame = ctk.CTkScrollableFrame(wrong_window)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for wrong in wrong_questions:
            wrong_frame = ctk.CTkFrame(scrollable_frame)
            wrong_frame.pack(fill="x", pady=10)
            wrong_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                wrong_frame, text=f"❌ Câu {wrong['stt']}",
                font=ctk.CTkFont(size=16, weight="bold"), text_color="lightcoral"
            ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

            ctk.CTkLabel(
                wrong_frame, text=f"❓ {wrong['cau_hoi']}",
                font=ctk.CTkFont(size=14), wraplength=800, justify="left"
            ).grid(row=1, column=0, sticky="ew", padx=20, pady=5)

            ctk.CTkLabel(
                wrong_frame, text=f"👤 Bạn đã chọn: {wrong['lua_chon']}",
                font=ctk.CTkFont(size=13), text_color="lightcoral"
            ).grid(row=2, column=0, sticky="w", padx=20, pady=2)

            ctk.CTkLabel(
                wrong_frame, text=f"✅ Đáp án đúng: {wrong['dap_an_dung']}",
                font=ctk.CTkFont(size=13), text_color="lightgreen"
            ).grid(row=3, column=0, sticky="w", padx=20, pady=2)

            if wrong['giai_thich']:
                ctk.CTkLabel(
                    wrong_frame, text=f"💡 Giải thích: {wrong['giai_thich']}",
                    font=ctk.CTkFont(size=12), text_color="gray",
                    wraplength=800, justify="left"
                ).grid(row=4, column=0, sticky="ew", padx=20, pady=(5, 15))

        ctk.CTkButton(wrong_window, text="Đóng", command=wrong_window.destroy).pack(pady=20)

    def update_status(self):
        if not self.questions:
            self.stats_label.configure(text="Chưa có dữ liệu")
            return

        answered_count = len([ans for ans in self.user_answers.values() if ans])
        total_count = len(self.questions)

        if self.current_mode == "practice":
            checked_count = len(self.question_feedback)
            self.stats_label.configure(
                text=f"Đã kiểm tra: {checked_count}/{total_count} | Trả lời: {answered_count}/{total_count}"
            )
        else:
            self.stats_label.configure(text=f"Đã trả lời: {answered_count}/{total_count}")

    def toggle_theme(self):
        if self.theme_switch.get():
            ctk.set_appearance_mode("dark")
            self.config['theme'] = 'dark'
        else:
            ctk.set_appearance_mode("light")
            self.config['theme'] = 'light'

    def run(self):
        self.root.mainloop()


def main():
    """Hàm main"""
    app = QuizApplication()
    app.initialize_with_splash()
    app.run()


if __name__ == "__main__":
    main()
