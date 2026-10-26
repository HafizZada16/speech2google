import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import speech_recognition as sr
import sounddevice as sd
try:
    import edge_tts  # type: ignore
except ImportError:
    edge_tts = None

try:
    import av  # type: ignore
except ImportError:
    av = None

try:
    import gtts  # type: ignore
except ImportError:
    gtts = None

import io

import sys
import os
import json
import threading
import asyncio
import time
import re
import numpy as np
from concurrent.futures import ThreadPoolExecutor

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

COLOR_BG = "#0d0f17"
COLOR_CARD = "#171a26"
COLOR_CARD_BORDER = "#25293d"
COLOR_TEXT_MAIN = "#f1f5f9"
COLOR_TEXT_MUTED = "#94a3b8"
COLOR_PRIMARY = "#4f46e5"
COLOR_PRIMARY_HOVER = "#4338ca"
COLOR_DANGER = "#e11d48"
COLOR_DANGER_HOVER = "#be123c"

class RealtimeVoiceChanger(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("speech2google")
        self.geometry("700x820")
        self.minsize(660, 720)
        self.configure(fg_color=COLOR_BG)

        self.is_running = False
        self.tts_is_playing = False
        self.worker_thread = None
        self.tts_thread = None
        self.active_tab = "streaming"

        self.voices = {
            "Google Translate Meme (Mbak Google - ID)": "gtts:id",
            "Google Translate (English - US)": "gtts:en",
            "Gadis (Wanita - Indonesia)": "id-ID-GadisNeural",
            "Ardi (Pria - Indonesia)": "id-ID-ArdiNeural",
            "Jenny (Female - English US)": "en-US-JennyNeural",
            "Guy (Male - English US)": "en-US-GuyNeural"
        }

        self.devices = sd.query_devices()
        self.mic_list = self.get_device_names(is_input=True)
        self.speaker_list = self.get_device_names(is_input=False)

        self.setup_combobox_theme()
        self.saved_config = self.load_config()

        self.setup_ui()
        self.apply_saved_config()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Gagal memuat config: {e}")
        return {}

    def save_config(self):
        try:
            mic_val = self.mic_cb.get()
            speaker_val = self.speaker_cb.get()

            mic_name = mic_val.split(":", 1)[1].strip() if ":" in mic_val else mic_val
            speaker_name = speaker_val.split(":", 1)[1].strip() if ":" in speaker_val else speaker_val

            cfg = {
                "mic": mic_name,
                "speaker": speaker_name,
                "voice": self.voice_opt.get(),
                "rate": self.rate_opt.get(),
                "pause_threshold": self.pause_opt.get(),
                "auto_comma": self.auto_comma_var.get()
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Gagal menyimpan config: {e}")

    def apply_saved_config(self):
        if not self.saved_config:
            return

        saved_mic = self.saved_config.get("mic", "")
        if saved_mic:
            matched = False
            for idx, item in enumerate(self.mic_list):
                if saved_mic.lower() in item.lower():
                    self.mic_cb.current(idx)
                    matched = True
                    break
            if not matched:
                self.set_default_device(self.mic_cb, is_input=True)

        saved_speaker = self.saved_config.get("speaker", "")
        if saved_speaker:
            matched = False
            for idx, item in enumerate(self.speaker_list):
                if saved_speaker.lower() in item.lower():
                    self.speaker_cb.current(idx)
                    self.tts_speaker_cb.current(idx)
                    matched = True
                    break
            if not matched:
                self.set_default_device(self.speaker_cb, is_input=False)
                self.set_default_device(self.tts_speaker_cb, is_input=False)

        saved_voice = self.saved_config.get("voice", "")
        if saved_voice in self.voices:
            self.voice_opt.set(saved_voice)
            self.tts_voice_opt.set(saved_voice)

        saved_rate = self.saved_config.get("rate", "")
        if saved_rate:
            self.rate_opt.set(saved_rate)
            self.tts_rate_opt.set(saved_rate)

        saved_pause = self.saved_config.get("pause_threshold", "")
        if saved_pause:
            self.pause_opt.set(saved_pause)

        if "auto_comma" in self.saved_config:
            self.auto_comma_var.set(bool(self.saved_config["auto_comma"]))

    def setup_combobox_theme(self):
        self.option_add('*TCombobox*Listbox.background', '#171a26')
        self.option_add('*TCombobox*Listbox.foreground', '#f1f5f9')
        self.option_add('*TCombobox*Listbox.selectBackground', '#4f46e5')
        self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        self.option_add('*TCombobox*Listbox.font', ('Segoe UI', 10))
        self.option_add('*TCombobox*Listbox.relief', 'flat')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Dark.TCombobox',
            fieldbackground='#212536',
            background='#2b3047',
            foreground='#f1f5f9',
            darkcolor='#212536',
            lightcolor='#212536',
            bordercolor='#2e344e',
            arrowcolor='#818cf8',
            padding=6,
            font=('Segoe UI', 10)
        )
        style.map(
            'Dark.TCombobox',
            fieldbackground=[('readonly', '#212536'), ('disabled', '#151722')],
            foreground=[('readonly', '#f1f5f9'), ('disabled', '#64748b')],
            bordercolor=[('focus', '#4f46e5')]
        )

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---------------- 1. HEADER HERO CARD ----------------
        header_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        header_card.grid(row=0, column=0, padx=22, pady=(16, 8), sticky="ew")

        header_content = ctk.CTkFrame(header_card, fg_color="transparent")
        header_content.pack(padx=20, pady=14, fill="x")

        title_row = ctk.CTkFrame(header_content, fg_color="transparent")
        title_row.pack(anchor="w")

        icon_frame = ctk.CTkFrame(
            title_row,
            width=36,
            height=36,
            corner_radius=9,
            fg_color="#212536",
            border_width=1,
            border_color="#2e344e"
        )
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(
            icon_frame,
            text="🎙",
            font=ctk.CTkFont(size=18)
        )
        icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

        title_lbl = ctk.CTkLabel(
            title_row,
            text="speech2google",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title_lbl.pack(side="left")

        subtitle_lbl = ctk.CTkLabel(
            header_content,
            text="Realtime Speech-to-Speech Streaming & Neural Text-to-Speech",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        )
        subtitle_lbl.pack(anchor="w", pady=(3, 0))

        self.status_badge = ctk.CTkLabel(
            header_content,
            text="● SIAP DIGUNAKAN",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8",
            fg_color="#212536",
            corner_radius=20,
            padx=14,
            pady=4
        )
        self.status_badge.pack(anchor="w", pady=(8, 0))

        # ---------------- 2. TOPBAR NAVBAR TABS ----------------
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=1, column=0, padx=22, pady=(0, 8), sticky="ew")

        nav_container = ctk.CTkFrame(
            nav_frame,
            fg_color=COLOR_CARD,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_CARD_BORDER,
            height=44
        )
        nav_container.pack(fill="x")
        nav_container.grid_columnconfigure((0, 1), weight=1)

        self.btn_tab_streaming = ctk.CTkButton(
            nav_container,
            text="🎙  Voice Changer (Streaming)",
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff",
            command=lambda: self.switch_page("streaming")
        )
        self.btn_tab_streaming.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.btn_tab_tts = ctk.CTkButton(
            nav_container,
            text="💬  Text to Speech (TTS)",
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#212536",
            text_color=COLOR_TEXT_MUTED,
            command=lambda: self.switch_page("tts")
        )
        self.btn_tab_tts.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # ---------------- 3. MAIN CONTENT CONTAINER ----------------
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Build individual page views
        self.setup_streaming_page()
        self.setup_tts_page()

        # Display initial page
        self.switch_page("streaming")

    def switch_page(self, page_name):
        self.active_tab = page_name
        if page_name == "streaming":
            self.btn_tab_streaming.configure(fg_color=COLOR_PRIMARY, text_color="#ffffff")
            self.btn_tab_tts.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED)
            self.page_tts.grid_forget()
            self.page_streaming.grid(row=0, column=0, sticky="nsew")
            if not self.is_running:
                self.set_status_badge("SIAP DIGUNAKAN", "idle")
            else:
                self.set_status_badge("STREAMING AKTIF", "listening")
        else:
            self.btn_tab_tts.configure(fg_color=COLOR_PRIMARY, text_color="#ffffff")
            self.btn_tab_streaming.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED)
            self.page_streaming.grid_forget()
            self.page_tts.grid(row=0, column=0, sticky="nsew")
            if not self.tts_is_playing:
                self.set_status_badge("TTS SIAP", "idle")
            else:
                self.set_status_badge("MEMUTAR SUARA TTS...", "streaming")

    def setup_streaming_page(self):
        self.page_streaming = ctk.CTkFrame(self.container, fg_color="transparent")
        self.page_streaming.grid_columnconfigure(0, weight=1)
        self.page_streaming.grid_rowconfigure(2, weight=1)

        # Device & Voice Settings Card
        dev_card = ctk.CTkFrame(
            self.page_streaming,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        dev_card.grid(row=0, column=0, padx=22, pady=(0, 6), sticky="ew")
        dev_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            dev_card,
            text="PENGATURAN PERANGKAT & SUARA",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(12, 6), sticky="w")

        ctk.CTkLabel(
            dev_card,
            text="Input Mikrofon (Mic):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=0, padx=(18, 10), pady=(2, 2), sticky="w")

        self.mic_cb = ttk.Combobox(
            dev_card,
            values=self.mic_list if self.mic_list else ["Tidak ada mic ditemukan"],
            style="Dark.TCombobox",
            state="readonly",
            height=12
        )
        self.mic_cb.grid(row=2, column=0, padx=(18, 10), pady=(0, 10), sticky="ew")
        self.set_default_device(self.mic_cb, is_input=True)

        ctk.CTkLabel(
            dev_card,
            text="Karakter Suara (Edge-TTS):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=3, column=0, padx=(18, 10), pady=(2, 2), sticky="w")

        self.voice_opt = ctk.CTkOptionMenu(
            dev_card,
            values=list(self.voices.keys()),
            corner_radius=8,
            height=34,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN,
            command=self.on_voice_changed_sync
        )
        self.voice_opt.grid(row=4, column=0, padx=(18, 10), pady=(0, 14), sticky="ew")
        self.voice_opt.set("Gadis (Wanita - Indonesia)")

        ctk.CTkLabel(
            dev_card,
            text="Output Audio (Speaker / Virtual Cable):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=1, padx=(10, 18), pady=(2, 2), sticky="w")

        self.speaker_cb = ttk.Combobox(
            dev_card,
            values=self.speaker_list if self.speaker_list else ["Tidak ada output ditemukan"],
            style="Dark.TCombobox",
            state="readonly",
            height=12
        )
        self.speaker_cb.grid(row=2, column=1, padx=(10, 18), pady=(0, 10), sticky="ew")
        self.set_default_device(self.speaker_cb, is_input=False)

        ctk.CTkLabel(
            dev_card,
            text="Kecepatan Artikulasi:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=3, column=1, padx=(10, 18), pady=(2, 2), sticky="w")

        self.rate_opt = ctk.CTkOptionMenu(
            dev_card,
            values=["Normal (+0%)", "Cepat (+15%)", "Sangat Cepat (+30%)", "Lambat (-10%)"],
            corner_radius=8,
            height=34,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN,
            command=self.on_rate_changed_sync
        )
        self.rate_opt.grid(row=4, column=1, padx=(10, 18), pady=(0, 14), sticky="ew")
        self.rate_opt.set("Normal (+0%)")

        # Silence & Punctuation Card
        silence_card = ctk.CTkFrame(
            self.page_streaming,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        silence_card.grid(row=1, column=0, padx=22, pady=4, sticky="ew")
        silence_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            silence_card,
            text="Deteksi Jeda Hening (Selesai Bicara):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=0, column=0, padx=(18, 10), pady=(10, 2), sticky="w")

        self.pause_opt = ctk.CTkOptionMenu(
            silence_card,
            values=[
                "0.8 detik (Respons Cepat)",
                "1.2 detik (Standar Alami)",
                "1.6 detik (Santai / Panjang)",
                "2.0 detik (Sangat Lambat)"
            ],
            corner_radius=8,
            height=34,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN,
            command=lambda e: self.save_config()
        )
        self.pause_opt.grid(row=1, column=0, padx=(18, 10), pady=(0, 12), sticky="ew")
        self.pause_opt.set("1.2 detik (Standar Alami)")

        switch_frame = ctk.CTkFrame(silence_card, fg_color="transparent")
        switch_frame.grid(row=0, column=1, rowspan=2, padx=(10, 18), pady=(10, 12), sticky="ew")

        ctk.CTkLabel(
            switch_frame,
            text="Otomatisasi Tanda Baca:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w")

        self.auto_comma_var = ctk.BooleanVar(value=True)
        self.chk_auto_comma = ctk.CTkSwitch(
            switch_frame,
            text="Sisipkan Koma (,) pada Jeda",
            variable=self.auto_comma_var,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            progress_color=COLOR_PRIMARY,
            button_color="#ffffff",
            button_hover_color="#e0e7ff",
            command=self.save_config
        )
        self.chk_auto_comma.pack(anchor="w", pady=(6, 0))

        # Transcript Log Card
        log_card = ctk.CTkFrame(
            self.page_streaming,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        log_card.grid(row=2, column=0, padx=22, pady=4, sticky="nsew")
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_card,
            text="TRANSKRIP PERCAKAPAN REAL-TIME",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, padx=18, pady=(10, 4), sticky="w")

        self.txt_log = ctk.CTkTextbox(
            log_card,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0f111a",
            text_color="#e2e8f0",
            border_width=1,
            border_color="#202436",
            corner_radius=10
        )
        self.txt_log.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="nsew")
        self.txt_log.insert("end", "Klik 'Mulai Streaming' lalu bicaralah ke mikrofon Anda...\n\n")
        self.txt_log.configure(state="disabled")

        # Bottom Streaming Control Button
        self.btn_control = ctk.CTkButton(
            self.page_streaming,
            text="▶  Mulai Streaming",
            command=self.toggle_process,
            height=48,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff"
        )
        self.btn_control.grid(row=3, column=0, padx=22, pady=(8, 16), sticky="ew")

        self.mic_cb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.speaker_cb.bind("<<ComboboxSelected>>", self.on_speaker_changed_sync)

    def setup_tts_page(self):
        self.page_tts = ctk.CTkFrame(self.container, fg_color="transparent")
        self.page_tts.grid_columnconfigure(0, weight=1)
        self.page_tts.grid_rowconfigure(1, weight=1)

        # Voice & Output Settings Card for TTS
        tts_settings_card = ctk.CTkFrame(
            self.page_tts,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        tts_settings_card.grid(row=0, column=0, padx=22, pady=(0, 6), sticky="ew")
        tts_settings_card.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            tts_settings_card,
            text="PENGATURAN SUARA & OUTPUT AUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, columnspan=3, padx=18, pady=(12, 6), sticky="w")

        ctk.CTkLabel(
            tts_settings_card,
            text="Karakter Suara (Voice):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=0, padx=(18, 8), pady=(2, 2), sticky="w")

        self.tts_voice_opt = ctk.CTkOptionMenu(
            tts_settings_card,
            values=list(self.voices.keys()),
            corner_radius=8,
            height=34,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN,
            command=self.on_tts_voice_changed_sync
        )
        self.tts_voice_opt.grid(row=2, column=0, padx=(18, 8), pady=(0, 14), sticky="ew")
        self.tts_voice_opt.set("Gadis (Wanita - Indonesia)")

        ctk.CTkLabel(
            tts_settings_card,
            text="Output Audio:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=1, padx=(8, 8), pady=(2, 2), sticky="w")

        self.tts_speaker_cb = ttk.Combobox(
            tts_settings_card,
            values=self.speaker_list if self.speaker_list else ["Tidak ada output ditemukan"],
            style="Dark.TCombobox",
            state="readonly",
            height=12
        )
        self.tts_speaker_cb.grid(row=2, column=1, padx=(8, 8), pady=(0, 14), sticky="ew")
        self.set_default_device(self.tts_speaker_cb, is_input=False)
        self.tts_speaker_cb.bind("<<ComboboxSelected>>", self.on_tts_speaker_changed_sync)

        ctk.CTkLabel(
            tts_settings_card,
            text="Kecepatan Artikulasi:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=2, padx=(8, 18), pady=(2, 2), sticky="w")

        self.tts_rate_opt = ctk.CTkOptionMenu(
            tts_settings_card,
            values=["Normal (+0%)", "Cepat (+15%)", "Sangat Cepat (+30%)", "Lambat (-10%)"],
            corner_radius=8,
            height=34,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN,
            command=self.on_tts_rate_changed_sync
        )
        self.tts_rate_opt.grid(row=2, column=2, padx=(8, 18), pady=(0, 14), sticky="ew")
        self.tts_rate_opt.set("Normal (+0%)")

        # Text Input Card
        text_card = ctk.CTkFrame(
            self.page_tts,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        text_card.grid(row=1, column=0, padx=22, pady=4, sticky="nsew")
        text_card.grid_columnconfigure(0, weight=1)
        text_card.grid_rowconfigure(1, weight=1)

        text_header_row = ctk.CTkFrame(text_card, fg_color="transparent")
        text_header_row.grid(row=0, column=0, padx=18, pady=(12, 6), sticky="ew")
        text_header_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            text_header_row,
            text="MASUKKAN TEKS UNTUK DISUARAKAN",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, sticky="w")

        quick_tools = ctk.CTkFrame(text_header_row, fg_color="transparent")
        quick_tools.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            quick_tools,
            text="📋 Tempel",
            width=70,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#212536",
            hover_color="#2b3047",
            text_color=COLOR_TEXT_MAIN,
            command=self.paste_to_tts
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            quick_tools,
            text="💬 Contoh",
            width=70,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#212536",
            hover_color="#2b3047",
            text_color=COLOR_TEXT_MAIN,
            command=self.insert_sample_tts
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            quick_tools,
            text="🗑️ Hapus",
            width=65,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#212536",
            hover_color="#3c2025",
            text_color="#f87171",
            command=self.clear_tts_input
        ).pack(side="left")

        self.txt_tts_input = ctk.CTkTextbox(
            text_card,
            wrap="word",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#0f111a",
            text_color="#f1f5f9",
            border_width=1,
            border_color="#202436",
            corner_radius=10
        )
        self.txt_tts_input.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="nsew")
        self.txt_tts_input.insert("1.0", "Halo semuanya! Selamat datang di speech2google. Ketik teks apa saja di sini untuk disuarakan ke perangkat output Anda.")
        self.txt_tts_input.bind("<KeyRelease>", self.update_tts_counter)

        bottom_text_info = ctk.CTkFrame(text_card, fg_color="transparent")
        bottom_text_info.grid(row=2, column=0, padx=18, pady=(0, 10), sticky="ew")

        self.lbl_char_counter = ctk.CTkLabel(
            bottom_text_info,
            text="0 karakter • 0 kata",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_char_counter.pack(side="left")

        self.lbl_tts_status = ctk.CTkLabel(
            bottom_text_info,
            text="● Siap memutar suara",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8"
        )
        self.lbl_tts_status.pack(side="right")
        self.update_tts_counter()

        # Bottom Actions Bar for TTS
        tts_actions_frame = ctk.CTkFrame(self.page_tts, fg_color="transparent")
        tts_actions_frame.grid(row=2, column=0, padx=22, pady=(8, 16), sticky="ew")
        tts_actions_frame.grid_columnconfigure(0, weight=2)
        tts_actions_frame.grid_columnconfigure(1, weight=1)

        self.btn_tts_play = ctk.CTkButton(
            tts_actions_frame,
            text="▶  Putar Suara ke Output",
            command=self.toggle_tts_playback,
            height=48,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff"
        )
        self.btn_tts_play.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.btn_tts_save = ctk.CTkButton(
            tts_actions_frame,
            text="💾  Simpan ke File (.mp3)",
            command=self.save_tts_file,
            height=48,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#212536",
            hover_color="#2b3047",
            border_width=1,
            border_color="#2e344e",
            text_color=COLOR_TEXT_MAIN
        )
        self.btn_tts_save.grid(row=0, column=1, sticky="ew")

    # Sync handlers between pages
    def on_voice_changed_sync(self, choice):
        self.tts_voice_opt.set(choice)
        self.save_config()

    def on_tts_voice_changed_sync(self, choice):
        self.voice_opt.set(choice)
        self.save_config()

    def on_rate_changed_sync(self, choice):
        self.tts_rate_opt.set(choice)
        self.save_config()

    def on_tts_rate_changed_sync(self, choice):
        self.rate_opt.set(choice)
        self.save_config()

    def on_speaker_changed_sync(self, event=None):
        idx = self.speaker_cb.current()
        if idx >= 0:
            self.tts_speaker_cb.current(idx)
        self.save_config()

    def on_tts_speaker_changed_sync(self, event=None):
        idx = self.tts_speaker_cb.current()
        if idx >= 0:
            self.speaker_cb.current(idx)
        self.save_config()

    # TTS Helper actions
    def clear_tts_input(self):
        self.txt_tts_input.delete("1.0", "end")
        self.update_tts_counter()

    def paste_to_tts(self):
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.txt_tts_input.insert("insert", clipboard_text)
                self.update_tts_counter()
        except Exception:
            pass

    def insert_sample_tts(self):
        sample = "Halo semuanya! Selamat datang di speech2google. Ini adalah contoh suara natural berkecepatan tinggi yang dihasilkan secara real-time."
        self.txt_tts_input.delete("1.0", "end")
        self.txt_tts_input.insert("1.0", sample)
        self.update_tts_counter()

    def update_tts_counter(self, event=None):
        text = self.txt_tts_input.get("1.0", "end-1c")
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.lbl_char_counter.configure(text=f"{chars} karakter • {words} kata")

    def toggle_tts_playback(self):
        if not self.tts_is_playing:
            text = self.txt_tts_input.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning("Teks Kosong", "Silakan masukkan teks yang ingin disuarakan.")
                return

            if edge_tts is None or av is None:
                messagebox.showerror(
                    "Pustaka Belum Lengkap",
                    "Pustaka 'edge-tts' atau 'av' belum terdeteksi.\nSilakan jalankan di terminal:\npip install -r requirements.txt"
                )
                return

            try:
                speaker_id = int(self.tts_speaker_cb.get().split(":")[0])
            except Exception:
                messagebox.showerror("Error", "Silakan pilih perangkat output audio terlebih dahulu.")
                return

            selected_voice_key = self.tts_voice_opt.get()
            voice_id = self.voices.get(selected_voice_key, "id-ID-GadisNeural")

            rate_map = {
                "Normal (+0%)": "+0%",
                "Cepat (+15%)": "+15%",
                "Sangat Cepat (+30%)": "+30%",
                "Lambat (-10%)": "-10%"
            }
            speech_rate = rate_map.get(self.tts_rate_opt.get(), "+0%")

            self.tts_is_playing = True
            self.btn_tts_play.configure(
                text="⏹  Hentikan Suara",
                fg_color=COLOR_DANGER,
                hover_color=COLOR_DANGER_HOVER
            )
            self.lbl_tts_status.configure(text="● Sedang menyuarakan...", text_color="#60a5fa")
            self.set_status_badge("MEMUTAR TTS...", "streaming")

            self.tts_thread = threading.Thread(
                target=self._run_tts_playback,
                args=(text, voice_id, speech_rate, speaker_id),
                daemon=True
            )
            self.tts_thread.start()
        else:
            self.tts_is_playing = False
            self.btn_tts_play.configure(
                text="▶  Putar Suara ke Output",
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER
            )
            self.lbl_tts_status.configure(text="● Pemutaran dihentikan", text_color="#f87171")
            self.set_status_badge("TTS DIHENTIKAN", "stopped")

    def _run_tts_playback(self, text, voice_id, speech_rate, speaker_id):
        t_start = time.time()
        try:
            if voice_id.startswith("gtts:"):
                lang = voice_id.split(":")[1]
                self._play_gtts_direct(text, lang, speaker_id)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._async_stream_and_play_tts(text, voice_id, speech_rate, speaker_id))
                finally:
                    loop.close()
            t_total = time.time() - t_start
            self.after(0, lambda: self.lbl_tts_status.configure(
                text=f"● Selesai diputar ({t_total:.2f}s)",
                text_color="#34d399"
            ))
        except Exception as e:
            self.after(0, lambda: self.lbl_tts_status.configure(
                text=f"● Error: {str(e)[:40]}",
                text_color="#f87171"
            ))
        finally:
            self.tts_is_playing = False
            self.after(0, self._reset_tts_ui)

    def _play_gtts_direct(self, text, lang, speaker_id):
        tts = gtts.gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        data = fp.getvalue()
        codec = av.CodecContext.create('mp3', 'r')
        with sd.OutputStream(
            samplerate=24000,
            channels=1,
            dtype='int16',
            device=speaker_id,
            latency='low'
        ) as stream:
            for packet in codec.parse(data):
                if not self.tts_is_playing:
                    break
                for frame in codec.decode(packet):
                    if not self.tts_is_playing:
                        return
                    pcm_data = frame.to_ndarray().T
                    stream.write(pcm_data)
            for frame in codec.decode():
                if not self.tts_is_playing:
                    return
                pcm_data = frame.to_ndarray().T
                stream.write(pcm_data)

    def _reset_tts_ui(self):
        self.btn_tts_play.configure(
            text="▶  Putar Suara ke Output",
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER
        )
        if self.active_tab == "tts":
            self.set_status_badge("TTS SIAP", "idle")

    async def _async_stream_and_play_tts(self, text, voice, rate, speaker_id):
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        codec = av.CodecContext.create('mp3', 'r')

        with sd.OutputStream(
            samplerate=24000,
            channels=1,
            dtype='int16',
            device=speaker_id,
            latency='low'
        ) as stream:
            async for chunk in comm.stream():
                if not self.tts_is_playing:
                    break
                if chunk['type'] == 'audio':
                    packets = codec.parse(chunk['data'])
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            if not self.tts_is_playing:
                                return
                            pcm_data = frame.to_ndarray().T
                            stream.write(pcm_data)

            for frame in codec.decode():
                if not self.tts_is_playing:
                    return
                pcm_data = frame.to_ndarray().T
                stream.write(pcm_data)

    def save_tts_file(self):
        text = self.txt_tts_input.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Teks Kosong", "Silakan masukkan teks yang ingin disimpan.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("File Audio MP3", "*.mp3"), ("Semua File", "*.*")],
            title="Simpan Suara ke File MP3"
        )
        if not file_path:
            return

        selected_voice_key = self.tts_voice_opt.get()
        voice_id = self.voices.get(selected_voice_key, "id-ID-GadisNeural")

        rate_map = {
            "Normal (+0%)": "+0%",
            "Cepat (+15%)": "+15%",
            "Sangat Cepat (+30%)": "+30%",
            "Lambat (-10%)": "-10%"
        }
        speech_rate = rate_map.get(self.tts_rate_opt.get(), "+0%")

        self.lbl_tts_status.configure(text="● Menyimpan ke MP3...", text_color="#fbbf24")

        def _save_worker():
            try:
                if voice_id.startswith("gtts:"):
                    lang = voice_id.split(":")[1]
                    tts = gtts.gTTS(text=text, lang=lang)
                    tts.save(file_path)
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    comm = edge_tts.Communicate(text, voice=voice_id, rate=speech_rate)
                    loop.run_until_complete(comm.save(file_path))
                    loop.close()
                self.after(0, lambda: self.lbl_tts_status.configure(
                    text=f"● Berhasil disimpan: {os.path.basename(file_path)}",
                    text_color="#34d399"
                ))
            except Exception as e:
                self.after(0, lambda: self.lbl_tts_status.configure(
                    text=f"● Gagal simpan: {str(e)[:40]}",
                    text_color="#f87171"
                ))

        threading.Thread(target=_save_worker, daemon=True).start()

    def set_status_badge(self, text, state="idle"):
        """Mengubah pill status badge dengan warna indikator modern"""
        palette = {
            "idle": ("● " + text, "#94a3b8", "#212536"),
            "listening": ("● " + text, "#34d399", "#064e3b"),
            "processing": ("● " + text, "#fbbf24", "#78350f"),
            "streaming": ("● " + text, "#60a5fa", "#1e3a8a"),
            "stopped": ("● " + text, "#f87171", "#450a0a"),
        }
        badge_text, text_col, bg_col = palette.get(state, ("● " + text, "#94a3b8", "#212536"))
        self.after(0, lambda: self.status_badge.configure(text=badge_text, text_color=text_col, fg_color=bg_col))

    def log_message(self, message):
        """Menambahkan pesan ke area transkrip secara thread-safe"""
        def _append():
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", message + "\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        self.after(0, _append)

    def get_device_names(self, is_input=True):
        """Mengambil nama perangkat audio khusus MME (Multimedia) agar ringkas dan bebas duplikasi"""
        device_names = []
        try:
            hostapis = sd.query_hostapis()
            mme_idx = 0
            for idx, api in enumerate(hostapis):
                if "MME" in api.get("name", "").upper():
                    mme_idx = idx
                    break
        except Exception:
            mme_idx = 0

        for i, dev in enumerate(self.devices):
            if dev.get('hostapi') == mme_idx:
                channels = dev['max_input_channels'] if is_input else dev['max_output_channels']
                if channels > 0:
                    device_names.append(f"{i}: {dev['name']}")
        return device_names

    def set_default_device(self, combobox, is_input=True):
        try:
            default_idx = sd.default.device[0] if is_input else sd.default.device[1]
            device_list = self.mic_list if is_input else self.speaker_list
            for idx, item in enumerate(device_list):
                if item.startswith(f"{default_idx}:"):
                    combobox.current(idx)
                    return
            if 0 <= default_idx < len(self.devices):
                def_name = self.devices[default_idx]['name'].lower()
                for idx, item in enumerate(device_list):
                    item_name = item.split(":", 1)[1].strip().lower()
                    if item_name in def_name or def_name in item_name:
                        combobox.current(idx)
                        return
            if device_list:
                combobox.current(0)
        except Exception:
            if combobox['values']:
                combobox.current(0)

    def toggle_process(self):
        if not self.is_running:
            if edge_tts is None or av is None:
                messagebox.showerror(
                    "Pustaka Belum Lengkap",
                    "Pustaka 'edge-tts' atau 'av' belum terdeteksi.\nSilakan jalankan di terminal:\npip install -r requirements.txt"
                )
                return

            self.is_running = True
            self.btn_control.configure(
                text="⏹  Hentikan",
                fg_color=COLOR_DANGER,
                hover_color=COLOR_DANGER_HOVER
            )
            self.mic_cb.configure(state="disabled")
            self.speaker_cb.configure(state="disabled")
            self.voice_opt.configure(state="disabled")
            self.rate_opt.configure(state="disabled")
            self.pause_opt.configure(state="disabled")
            self.chk_auto_comma.configure(state="disabled")

            self.worker_thread = threading.Thread(target=self.loop_suara, daemon=True)
            self.worker_thread.start()
        else:
            self.is_running = False
            self.btn_control.configure(
                text="▶  Mulai Streaming",
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER
            )
            self.mic_cb.configure(state="readonly")
            self.speaker_cb.configure(state="readonly")
            self.voice_opt.configure(state="normal")
            self.rate_opt.configure(state="normal")
            self.pause_opt.configure(state="normal")
            self.chk_auto_comma.configure(state="normal")
            self.set_status_badge("Dihentikan", "stopped")

    def loop_suara(self):
        try:
            mic_id = int(self.mic_cb.get().split(":")[0])
            speaker_id = int(self.speaker_cb.get().split(":")[0])
        except Exception:
            self.after(0, lambda: messagebox.showerror("Error", "Silakan pilih perangkat input dan output terlebih dahulu."))
            self.after(0, self.toggle_process)
            return

        selected_voice_key = self.voice_opt.get()
        voice_id = self.voices.get(selected_voice_key, "id-ID-GadisNeural")

        rate_map = {
            "Normal (+0%)": "+0%",
            "Cepat (+15%)": "+15%",
            "Sangat Cepat (+30%)": "+30%",
            "Lambat (-10%)": "-10%"
        }
        speech_rate = rate_map.get(self.rate_opt.get(), "+0%")

        try:
            pause_sec = float(self.pause_opt.get().split(" ")[0])
        except Exception:
            pause_sec = 1.2

        perekam = sr.Recognizer()
        perekam.pause_threshold = pause_sec
        perekam.non_speaking_duration = min(0.5, pause_sec / 2)
        perekam.phrase_threshold = 0.3

        try:
            mic_source = sr.Microphone(device_index=mic_id)
        except Exception as e:
            self.log_message(f"[Error] Gagal membuka mikrofon ID {mic_id}: {e}")
            self.after(0, self.toggle_process)
            return

        self.set_status_badge("Mengalibrasi mikrofon...", "processing")
        try:
            with mic_source as sumber_suara:
                perekam.adjust_for_ambient_noise(sumber_suara, duration=0.8)
                perekam.energy_threshold = max(80, perekam.energy_threshold * 0.75)
                perekam.dynamic_energy_threshold = False
        except Exception as e:
            self.log_message(f"[Warning] Kalibrasi noise dilewati: {e}")

        self.log_message("[Sistem]: Siap mendengarkan. Silakan berbicara...")

        while self.is_running:
            self.set_status_badge("Mendengarkan...", "listening")

            try:
                with mic_source as sumber_suara:
                    audio = perekam.listen(sumber_suara, timeout=2.0, phrase_time_limit=None)
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                if self.is_running:
                    self.log_message(f"[Error Mic]: {e}")
                break

            if not self.is_running:
                break

            t_start = time.time()
            self.set_status_badge("Memproses...", "processing")

            try:
                if self.auto_comma_var.get():
                    audio_chunks = self.split_audio_by_pauses(
                        audio,
                        min_silence_sec=0.35,
                        energy_threshold=perekam.energy_threshold * 1.15
                    )
                else:
                    audio_chunks = [audio]

                if len(audio_chunks) > 1:
                    def _recognize_single(chunk):
                        try:
                            return perekam.recognize_google(chunk, language="id-ID").strip()
                        except Exception:
                            return ""

                    with ThreadPoolExecutor(max_workers=min(4, len(audio_chunks))) as executor:
                        transcripts = list(executor.map(_recognize_single, audio_chunks))

                    valid_parts = [p for p in transcripts if p]
                    if not valid_parts:
                        continue
                    teks_hasil = ", ".join(valid_parts)
                else:
                    teks_hasil = perekam.recognize_google(audio, language="id-ID")
                    if not teks_hasil.strip():
                        continue

                teks_hasil = self.enhance_punctuation(teks_hasil)
                self.log_message(f"🗣️ [Anda]: \"{teks_hasil}\"")

            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                self.log_message(f"❌ [Error STT]: Koneksi gagal: {e}")
                continue
            except Exception as e:
                self.log_message(f"❌ [Error STT]: {e}")
                continue

            if not self.is_running:
                break

            self.set_status_badge("STREAMING SUARA KE OUTPUT...", "streaming")
            try:
                self.stream_tts_to_speaker(teks_hasil, voice_id, speech_rate, speaker_id)
                t_total = time.time() - t_start
                self.log_message(f"🤖 [Robot]: Selesai diputar ({t_total:.2f}s)\n")
            except Exception as e:
                self.log_message(f"❌ [Error Audio Out]: {e}")

        self.set_status_badge("PROGRAM DIHENTIKAN", "stopped")

    def split_audio_by_pauses(self, audio, min_silence_sec=0.35, energy_threshold=120):
        """Mendeteksi jeda hening di tengah percakapan untuk disisipkan koma"""
        try:
            raw_data = audio.get_raw_data()
            samples = np.frombuffer(raw_data, dtype=np.int16)
            sr_rate = audio.sample_rate
            sample_width = audio.sample_width

            window_samples = int(sr_rate * 0.05)
            if len(samples) < window_samples * 25:
                return [audio]

            num_windows = len(samples) // window_samples
            reshaped = samples[:num_windows * window_samples].reshape(num_windows, window_samples)
            rms = np.sqrt(np.mean(reshaped.astype(np.float32) ** 2, axis=1))

            is_silent = rms < max(60.0, float(energy_threshold))
            min_silent_windows = max(5, int(min_silence_sec / 0.05))

            pause_cut_samples = []
            silent_count = 0
            start_silence = None

            for i, silent in enumerate(is_silent):
                if silent:
                    if silent_count == 0:
                        start_silence = i
                    silent_count += 1
                else:
                    if silent_count >= min_silent_windows and start_silence is not None:
                        if start_silence > 8 and (len(is_silent) - i) > 8:
                            mid_point = (start_silence + i) // 2
                            pause_cut_samples.append(mid_point * window_samples)
                    silent_count = 0
                    start_silence = None

            if not pause_cut_samples:
                return [audio]

            chunks = []
            prev_sample = 0
            min_chunk_samples = int(sr_rate * 0.4)
            for cut_idx in pause_cut_samples:
                if (cut_idx - prev_sample) >= min_chunk_samples:
                    chunk_bytes = raw_data[prev_sample * sample_width : cut_idx * sample_width]
                    chunks.append(sr.AudioData(chunk_bytes, sr_rate, sample_width))
                    prev_sample = cut_idx

            if (len(samples) - prev_sample) >= min_chunk_samples:
                chunk_bytes = raw_data[prev_sample * sample_width :]
                chunks.append(sr.AudioData(chunk_bytes, sr_rate, sample_width))

            return chunks if len(chunks) > 1 else [audio]
        except Exception:
            return [audio]

    def enhance_punctuation(self, text):
        """Merapikan tanda baca: kapitalisasi awal dan koma sebelum konjungsi"""
        text = text.strip()
        if not text:
            return ""

        text = text[0].upper() + text[1:]
        conjunctions = [
            "tetapi", "tapi", "karena", "sehingga", "sedangkan",
            "namun", "melainkan", "padahal", "bahkan", "yaitu", "yakni"
        ]
        for conj in conjunctions:
            text = re.sub(r'(?<!,)\s+(' + conj + r')\b', r', \1', text, flags=re.IGNORECASE)

        text = re.sub(r',\s*,+', ',', text)
        text = re.sub(r'\s+', ' ', text)

        if not text.endswith(('.', '!', '?')):
            text += '.'

        return text

    def stream_tts_to_speaker(self, text, voice, rate, speaker_id):
        """Streaming Edge-TTS atau gTTS langsung ke PyAV -> sounddevice.OutputStream"""
        if voice.startswith("gtts:"):
            lang = voice.split(":")[1]
            self._stream_gtts_to_speaker(text, lang, speaker_id)
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_stream_and_play(text, voice, rate, speaker_id))
            finally:
                loop.close()

    def _stream_gtts_to_speaker(self, text, lang, speaker_id):
        tts = gtts.gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        data = fp.getvalue()
        codec = av.CodecContext.create('mp3', 'r')
        with sd.OutputStream(
            samplerate=24000,
            channels=1,
            dtype='int16',
            device=speaker_id,
            latency='low'
        ) as stream:
            for packet in codec.parse(data):
                if not self.is_running:
                    break
                for frame in codec.decode(packet):
                    if not self.is_running:
                        return
                    pcm_data = frame.to_ndarray().T
                    stream.write(pcm_data)
            for frame in codec.decode():
                if not self.is_running:
                    return
                pcm_data = frame.to_ndarray().T
                stream.write(pcm_data)

    async def _async_stream_and_play(self, text, voice, rate, speaker_id):
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        codec = av.CodecContext.create('mp3', 'r')

        with sd.OutputStream(
            samplerate=24000,
            channels=1,
            dtype='int16',
            device=speaker_id,
            latency='low'
        ) as stream:
            async for chunk in comm.stream():
                if not self.is_running:
                    break
                if chunk['type'] == 'audio':
                    packets = codec.parse(chunk['data'])
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            if not self.is_running:
                                return
                            pcm_data = frame.to_ndarray().T
                            stream.write(pcm_data)

            for frame in codec.decode():
                if not self.is_running:
                    return
                pcm_data = frame.to_ndarray().T
                stream.write(pcm_data)

    def on_close(self):
        self.save_config()
        self.is_running = False
        self.tts_is_playing = False
        self.destroy()

if __name__ == "__main__":
    app = RealtimeVoiceChanger()
    app.mainloop()
