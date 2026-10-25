import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
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
        self.geometry("700x780")
        self.minsize(640, 700)
        self.configure(fg_color=COLOR_BG)

        self.is_running = False
        self.worker_thread = None

        self.voices = {
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
                    matched = True
                    break
            if not matched:
                self.set_default_device(self.speaker_cb, is_input=False)

        saved_voice = self.saved_config.get("voice", "")
        if saved_voice in self.voices:
            self.voice_opt.set(saved_voice)

        saved_rate = self.saved_config.get("rate", "")
        if saved_rate:
            self.rate_opt.set(saved_rate)

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
        self.grid_rowconfigure(3, weight=1)

        header_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        header_card.grid(row=0, column=0, padx=22, pady=(20, 10), sticky="ew")

        header_content = ctk.CTkFrame(header_card, fg_color="transparent")
        header_content.pack(padx=20, pady=16, fill="x")

        title_lbl = ctk.CTkLabel(
            header_content,
            text="speech2google",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            header_content,
            text="Speech-to-speech voice changer • Edge-TTS & PyAV streaming",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

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
        self.status_badge.pack(anchor="w", pady=(10, 0))

        dev_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        dev_card.grid(row=1, column=0, padx=22, pady=6, sticky="ew")
        dev_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            dev_card,
            text="PENGATURAN PERANGKAT & SUARA",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(14, 8), sticky="w")

        ctk.CTkLabel(
            dev_card,
            text="Input Mikrofon (Mic):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=0, padx=(18, 10), pady=(4, 2), sticky="w")

        self.mic_cb = ttk.Combobox(
            dev_card,
            values=self.mic_list if self.mic_list else ["Tidak ada mic ditemukan"],
            style="Dark.TCombobox",
            state="readonly",
            height=12
        )
        self.mic_cb.grid(row=2, column=0, padx=(18, 10), pady=(0, 12), sticky="ew")
        self.set_default_device(self.mic_cb, is_input=True)

        ctk.CTkLabel(
            dev_card,
            text="Karakter Suara (Edge-TTS):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=3, column=0, padx=(18, 10), pady=(4, 2), sticky="w")

        self.voice_opt = ctk.CTkOptionMenu(
            dev_card,
            values=list(self.voices.keys()),
            corner_radius=8,
            height=36,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN
        )
        self.voice_opt.grid(row=4, column=0, padx=(18, 10), pady=(0, 16), sticky="ew")
        self.voice_opt.set("Gadis (Wanita - Indonesia)")

        ctk.CTkLabel(
            dev_card,
            text="Output Audio (Speaker / Virtual Cable):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=1, padx=(10, 18), pady=(4, 2), sticky="w")

        self.speaker_cb = ttk.Combobox(
            dev_card,
            values=self.speaker_list if self.speaker_list else ["Tidak ada output ditemukan"],
            style="Dark.TCombobox",
            state="readonly",
            height=12
        )
        self.speaker_cb.grid(row=2, column=1, padx=(10, 18), pady=(0, 12), sticky="ew")
        self.set_default_device(self.speaker_cb, is_input=False)

        ctk.CTkLabel(
            dev_card,
            text="Kecepatan Artikulasi:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=3, column=1, padx=(10, 18), pady=(4, 2), sticky="w")

        self.rate_opt = ctk.CTkOptionMenu(
            dev_card,
            values=["Normal (+0%)", "Cepat (+15%)", "Sangat Cepat (+30%)", "Lambat (-10%)"],
            corner_radius=8,
            height=36,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN
        )
        self.rate_opt.grid(row=4, column=1, padx=(10, 18), pady=(0, 16), sticky="ew")
        self.rate_opt.set("Normal (+0%)")

        silence_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        silence_card.grid(row=2, column=0, padx=22, pady=6, sticky="ew")
        silence_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            silence_card,
            text="Deteksi Jeda Hening (Selesai Bicara):",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        ).grid(row=0, column=0, padx=(18, 10), pady=(12, 2), sticky="w")

        self.pause_opt = ctk.CTkOptionMenu(
            silence_card,
            values=[
                "0.8 detik (Respons Cepat)",
                "1.2 detik (Standar Alami)",
                "1.6 detik (Santai / Panjang)",
                "2.0 detik (Sangat Lambat)"
            ],
            corner_radius=8,
            height=36,
            fg_color="#212536",
            button_color="#2b3047",
            button_hover_color="#3c4365",
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color="#1d2030",
            dropdown_text_color=COLOR_TEXT_MAIN
        )
        self.pause_opt.grid(row=1, column=0, padx=(18, 10), pady=(0, 14), sticky="ew")
        self.pause_opt.set("1.2 detik (Standar Alami)")

        switch_frame = ctk.CTkFrame(silence_card, fg_color="transparent")
        switch_frame.grid(row=0, column=1, rowspan=2, padx=(10, 18), pady=(14, 14), sticky="ew")

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
            button_hover_color="#e0e7ff"
        )
        self.chk_auto_comma.pack(anchor="w", pady=(6, 0))

        log_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_CARD_BORDER
        )
        log_card.grid(row=3, column=0, padx=22, pady=6, sticky="nsew")
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_card,
            text="TRANSKRIP PERCAKAPAN",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#818cf8"
        ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")

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
        self.txt_log.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.txt_log.insert("end", "Klik Mulai Streaming lalu bicaralah ke mikrofon...\n\n")
        self.txt_log.configure(state="disabled")

        self.btn_control = ctk.CTkButton(
            self,
            text="▶  Mulai Streaming",
            command=self.toggle_process,
            height=50,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff"
        )
        self.btn_control.grid(row=4, column=0, padx=22, pady=(10, 20), sticky="ew")

        self.mic_cb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.speaker_cb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.voice_opt.configure(command=lambda e: self.save_config())
        self.rate_opt.configure(command=lambda e: self.save_config())
        self.pause_opt.configure(command=lambda e: self.save_config())
        self.chk_auto_comma.configure(command=self.save_config)

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
        """Mengambil nama perangkat audio khusus MME (Multimedia) seperti Voicemeeter agar ringkas & bebas duplikasi"""
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
            # Filter hanya perangkat dengan hostapi == MME
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

            # 2. Proses Streaming TTS & Playback langsung ke Sounddevice
            self.set_status_badge("STREAMING SUARA KE OUTPUT...", "streaming")
            try:
                self.stream_tts_to_speaker(teks_hasil, voice_id, speech_rate, speaker_id)
                t_total = time.time() - t_start
                self.log_message(f"🤖 [Robot]: Selesai diputar ({t_total:.2f}s)\n")
            except Exception as e:
                self.log_message(f"❌ [Error Audio Out]: {e}")

        self.set_status_badge("PROGRAM DIHENTIKAN", "stopped")

    def split_audio_by_pauses(self, audio, min_silence_sec=0.35, energy_threshold=120):
        """Mendeteksi jeda hening / nafas di tengah percakapan untuk disisipkan koma"""
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
        """Streaming Edge-TTS langsung ke PyAV -> sounddevice.OutputStream"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_stream_and_play(text, voice, rate, speaker_id))
        finally:
            loop.close()

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
        self.destroy()

if __name__ == "__main__":
    app = RealtimeVoiceChanger()
    app.mainloop()
