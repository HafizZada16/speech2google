import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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

import threading
import asyncio
import time
import re
import numpy as np
from concurrent.futures import ThreadPoolExecutor

class RealtimeVoiceChanger:
    def __init__(self, root):
        self.root = root
        self.root.title("Low-Latency Real-Time Voice Changer")
        self.root.geometry("540x600")
        self.root.minsize(500, 550)
        
        self.is_running = False
        self.worker_thread = None
        
        # Daftar suara Edge-TTS yang tersedia
        self.voices = {
            "Gadis (Wanita - Indonesia)": "id-ID-GadisNeural",
            "Ardi (Pria - Indonesia)": "id-ID-ArdiNeural",
            "Jenny (Female - English US)": "en-US-JennyNeural",
            "Guy (Male - English US)": "en-US-GuyNeural"
        }
        
        # Mengambil daftar perangkat audio dari sounddevice (PortAudio)
        self.devices = sd.query_devices()
        
        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # 1. Header & Title
        header_frame = ttk.Frame(self.root)
        header_frame.pack(padx=20, pady=(15, 5), fill="x")
        
        title_label = ttk.Label(
            header_frame, 
            text="Real-Time Streaming Voice Changer", 
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(anchor="w")
        
        subtitle_label = ttk.Label(
            header_frame, 
            text="Streaming Edge-TTS Audio Chunks langsung ke Sounddevice (Ultra Low Latency)", 
            font=("Segoe UI", 9), 
            foreground="gray"
        )
        subtitle_label.pack(anchor="w")

        # 2. Pengaturan Audio Devices & Voice
        config_frame = ttk.LabelFrame(self.root, text=" Pengaturan Perangkat & Suara ")
        config_frame.pack(padx=20, pady=10, fill="x")

        # --- Dropdown Input (Microphone) ---
        ttk.Label(config_frame, text="Pilih Input (Mic):").pack(anchor="w", padx=10, pady=(6, 2))
        self.mic_list = self.get_device_names(is_input=True)
        self.mic_dropdown = ttk.Combobox(config_frame, values=self.mic_list, state="readonly")
        self.mic_dropdown.pack(padx=10, pady=(0, 6), fill="x")
        self.set_default_dropdown(self.mic_dropdown, is_input=True)

        # --- Dropdown Output (Speaker / VB-Cable) ---
        ttk.Label(config_frame, text="Pilih Output (Speaker / Virtual Cable):").pack(anchor="w", padx=10, pady=(4, 2))
        self.speaker_list = self.get_device_names(is_input=False)
        self.speaker_dropdown = ttk.Combobox(config_frame, values=self.speaker_list, state="readonly")
        self.speaker_dropdown.pack(padx=10, pady=(0, 6), fill="x")
        self.set_default_dropdown(self.speaker_dropdown, is_input=False)

        # --- Pilihan Model Suara (Edge-TTS) & Kecepatan ---
        voice_subframe = ttk.Frame(config_frame)
        voice_subframe.pack(padx=10, pady=(4, 10), fill="x")
        
        # Voice Dropdown
        voice_left = ttk.Frame(voice_subframe)
        voice_left.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Label(voice_left, text="Karakter Suara:").pack(anchor="w")
        self.voice_dropdown = ttk.Combobox(
            voice_left, 
            values=list(self.voices.keys()), 
            state="readonly"
        )
        self.voice_dropdown.pack(fill="x", pady=(2, 0))
        self.voice_dropdown.current(0)

        # Rate Dropdown
        rate_right = ttk.Frame(voice_subframe)
        rate_right.pack(side="right", padx=(5, 0))
        ttk.Label(rate_right, text="Kecepatan:").pack(anchor="w")
        self.rate_dropdown = ttk.Combobox(
            rate_right, 
            values=["Normal (+0%)", "Cepat (+15%)", "Sangat Cepat (+30%)", "Lambat (-10%)"], 
            state="readonly", 
            width=18
        )
        self.rate_dropdown.pack(pady=(2, 0))
        self.rate_dropdown.current(0)

        # --- Pengaturan Deteksi Hening (Silence Detection) ---
        silence_frame = ttk.Frame(config_frame)
        silence_frame.pack(padx=10, pady=(0, 10), fill="x")
        ttk.Label(silence_frame, text="Deteksi Jeda Hening (Berhenti Rekam Saat Diam):").pack(anchor="w")
        self.pause_dropdown = ttk.Combobox(
            silence_frame,
            values=[
                "0.8 detik (Respons Cepat)",
                "1.2 detik (Standar Alami - Rekomendasi)",
                "1.6 detik (Santai / Kalimat Panjang)",
                "2.0 detik (Bicara Sangat Lambat)"
            ],
            state="readonly"
        )
        self.pause_dropdown.pack(fill="x", pady=(2, 0))
        self.pause_dropdown.current(1)  # Default 1.2 detik

        # Checkbox Auto-Koma pada jeda bicara
        self.auto_comma_var = tk.BooleanVar(value=True)
        self.chk_auto_comma = ttk.Checkbutton(
            silence_frame,
            text="Otomatis sisipkan tanda koma (,) saat ada jeda bicara",
            variable=self.auto_comma_var
        )
        self.chk_auto_comma.pack(anchor="w", pady=(8, 0))

        # 3. Status Bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(padx=20, pady=5, fill="x")
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Status: Program Siap.", 
            font=("Segoe UI", 10, "bold"), 
            foreground="#555555"
        )
        self.status_label.pack(side="left")

        # 4. Transkrip & Log Box
        log_frame = ttk.LabelFrame(self.root, text=" Transkrip Percakapan Real-Time ")
        log_frame.pack(padx=20, pady=5, fill="both", expand=True)

        self.txt_log = scrolledtext.ScrolledText(log_frame, wrap="word", height=8, font=("Consolas", 9))
        self.txt_log.pack(padx=10, pady=10, fill="both", expand=True)
        self.txt_log.insert(tk.END, "Tekan 'MULAI STREAMING' lalu bicaralah ke mikrofon...\n")
        self.txt_log.config(state="disabled")

        # 5. Tombol Kontrol (Start / Stop)
        control_frame = ttk.Frame(self.root)
        control_frame.pack(padx=20, pady=(10, 15), fill="x")

        self.btn_control = ttk.Button(
            control_frame, 
            text="MULAI STREAMING", 
            command=self.toggle_process, 
            width=25
        )
        self.btn_control.pack(ipady=5)

    def log_message(self, message):
        """Menambahkan pesan ke area transkrip secara thread-safe"""
        def _append():
            self.txt_log.config(state="normal")
            self.txt_log.insert(tk.END, message + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state="disabled")
        self.root.after(0, _append)

    def set_status(self, text, color="#555555"):
        """Mengubah status secara thread-safe"""
        self.root.after(0, lambda: self.status_label.config(text=f"Status: {text}", foreground=color))

    def get_device_names(self, is_input=True):
        """Mengambil nama perangkat audio berdasarkan tipenya (input/output)"""
        device_names = []
        for i, dev in enumerate(self.devices):
            channels = dev['max_input_channels'] if is_input else dev['max_output_channels']
            if channels > 0:
                # Format: "ID: Nama Perangkat"
                device_names.append(f"{i}: {dev['name']}")
        return device_names

    def set_default_dropdown(self, dropdown, is_input=True):
        """Mengatur pilihan dropdown ke default bawaan sistem operasi"""
        try:
            default_idx = sd.default.device[0] if is_input else sd.default.device[1]
            for item in dropdown['values']:
                if item.startswith(f"{default_idx}:"):
                    dropdown.set(item)
                    return
            if dropdown['values']:
                dropdown.current(0)
        except Exception:
            if dropdown['values']:
                dropdown.current(0)

    def toggle_process(self):
        if not self.is_running:
            if edge_tts is None or av is None:
                messagebox.showerror(
                    "Pustaka Belum Lengkap",
                    "Pustaka 'edge-tts' atau 'av' belum terdeteksi.\nSilakan jalankan di terminal:\npip install -r requirements.txt"
                )
                return
            self.is_running = True
            self.btn_control.config(text="HENTIKAN PROGRAM")
            self.mic_dropdown.config(state="disabled")
            self.speaker_dropdown.config(state="disabled")
            self.voice_dropdown.config(state="disabled")
            self.rate_dropdown.config(state="disabled")
            self.pause_dropdown.config(state="disabled")
            self.chk_auto_comma.config(state="disabled")
            
            self.worker_thread = threading.Thread(target=self.loop_suara, daemon=True)
            self.worker_thread.start()
        else:
            self.is_running = False
            self.btn_control.config(text="MULAI STREAMING")
            self.mic_dropdown.config(state="readonly")
            self.speaker_dropdown.config(state="readonly")
            self.voice_dropdown.config(state="readonly")
            self.rate_dropdown.config(state="readonly")
            self.pause_dropdown.config(state="readonly")
            self.chk_auto_comma.config(state="normal")
            self.set_status("Dihentikan.", "#c0392b")

    def loop_suara(self):
        """Worker thread untuk menangani siklus Input -> STT -> Streaming TTS -> Output"""
        try:
            mic_id = int(self.mic_dropdown.get().split(":")[0])
            speaker_id = int(self.speaker_dropdown.get().split(":")[0])
        except Exception:
            self.root.after(0, lambda: messagebox.showerror("Error", "Silakan pilih perangkat input dan output terlebih dahulu."))
            self.root.after(0, self.toggle_process)
            return

        selected_voice_key = self.voice_dropdown.get()
        voice_id = self.voices.get(selected_voice_key, "id-ID-GadisNeural")
        
        # Kecepatan bicara
        rate_map = {
            "Normal (+0%)": "+0%",
            "Cepat (+15%)": "+15%",
            "Sangat Cepat (+30%)": "+30%",
            "Lambat (-10%)": "-10%"
        }
        speech_rate = rate_map.get(self.rate_dropdown.get(), "+0%")

        # Parsing durasi jeda hening dari pilihan pengguna
        try:
            pause_sec = float(self.pause_dropdown.get().split(" ")[0])
        except Exception:
            pause_sec = 1.2

        perekam = sr.Recognizer()
        # Rekam terus sampai terdeteksi jeda hening selama pause_sec
        perekam.pause_threshold = pause_sec
        perekam.non_speaking_duration = min(0.5, pause_sec / 2)
        perekam.phrase_threshold = 0.3

        try:
            mic_source = sr.Microphone(device_index=mic_id)
        except Exception as e:
            self.log_message(f"[Error] Gagal membuka mikrofon ID {mic_id}: {e}")
            self.root.after(0, self.toggle_process)
            return

        self.set_status("Mengalibrasi mikrofon & noise...", "#2980b9")
        try:
            with mic_source as sumber_suara:
                perekam.adjust_for_ambient_noise(sumber_suara, duration=0.8)
                # Buat threshold sedikit lebih sensitif agar kata lembut/ujung kalimat tidak terpotong
                perekam.energy_threshold = max(80, perekam.energy_threshold * 0.75)
                # Matikan auto-penyesuaian threshold saat bicara agar tidak memotong kata di tengah kalimat
                perekam.dynamic_energy_threshold = False
        except Exception as e:
            self.log_message(f"[Warning] Kalibrasi noise dilewati: {e}")

        self.log_message("=== Sistem Siap. Silakan berbicara... ===")

        while self.is_running:
            self.set_status("Mendengarkan suara Anda...", "#27ae60")
            
            try:
                with mic_source as sumber_suara:
                    # phrase_time_limit=None: TIDAK ADA batas detik! Rekam terus sampai suara berhenti/hening
                    audio = perekam.listen(sumber_suara, timeout=2.0, phrase_time_limit=None)
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                if self.is_running:
                    self.log_message(f"[Error Mic]: {e}")
                break

            if not self.is_running:
                break

            # 1. Proses STT (Speech to Text)
            t_start = time.time()
            self.set_status("Memproses suara -> teks...", "#d35400")
            
            try:
                # Jika opsi auto-koma aktif, periksa apakah ada jeda hening di tengah bicara
                if self.auto_comma_var.get():
                    audio_chunks = self.split_audio_by_pauses(
                        audio, 
                        min_silence_sec=0.35, 
                        energy_threshold=perekam.energy_threshold * 1.15
                    )
                else:
                    audio_chunks = [audio]

                if len(audio_chunks) > 1:
                    # Jalankan pengenalan paralel untuk tiap potongan agar latensi tetap sangat rendah
                    def _recognize_single(chunk):
                        try:
                            return perekam.recognize_google(chunk, language="id-ID").strip()
                        except Exception:
                            return ""

                    with ThreadPoolExecutor(max_workers=min(4, len(audio_chunks))) as executor:
                        transcripts = list(executor.map(_recognize_single, audio_chunks))

                    # Gabungkan potongan kata dengan tanda koma (,)
                    valid_parts = [p for p in transcripts if p]
                    if not valid_parts:
                        continue
                    teks_hasil = ", ".join(valid_parts)
                else:
                    teks_hasil = perekam.recognize_google(audio, language="id-ID")
                    if not teks_hasil.strip():
                        continue

                # Percantik tanda baca (kapitalisasi & koma sebelum kata hubung)
                teks_hasil = self.enhance_punctuation(teks_hasil)
                
                t_stt = time.time()
                self.log_message(f"[Anda]: \"{teks_hasil}\"")
                
            except sr.UnknownValueError:
                # Tidak ada kata yang dikenali / hanya hembusan nafas
                continue
            except sr.RequestError as e:
                self.log_message(f"[Error STT]: Koneksi gagal: {e}")
                continue
            except Exception as e:
                self.log_message(f"[Error STT]: {e}")
                continue

            if not self.is_running:
                break

            # 2. Proses Streaming TTS & Playback langsung ke Sounddevice
            self.set_status("Streaming audio chunks ke output...", "#2980b9")
            try:
                self.stream_tts_to_speaker(teks_hasil, voice_id, speech_rate, speaker_id)
                t_total = time.time() - t_start
                self.log_message(f"[Robot]: (Selesai diputar dalam {t_total:.2f} detik)\n")
            except Exception as e:
                self.log_message(f"[Error TTS/Audio]: {e}")

        self.set_status("Dihentikan.", "#c0392b")

    def split_audio_by_pauses(self, audio, min_silence_sec=0.35, energy_threshold=120):
        """
        Mendeteksi jeda hening / nafas di tengah percakapan dan membagi audio
        menjadi beberapa segmen AudioData untuk disisipkan tanda koma.
        """
        try:
            raw_data = audio.get_raw_data()
            samples = np.frombuffer(raw_data, dtype=np.int16)
            sr_rate = audio.sample_rate
            sample_width = audio.sample_width

            window_samples = int(sr_rate * 0.05)  # Window 50ms
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
                    # Pastikan jeda hening terjadi di tengah kalimat (bukan awal atau akhir)
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
        """
        Merapikan tanda baca: kapitalisasi awal kalimat, menyisipkan koma
        sebelum konjungsi bahasa Indonesia, dan tanda titik di akhir.
        """
        text = text.strip()
        if not text:
            return ""

        # Kapitalisasi huruf pertama
        text = text[0].upper() + text[1:]

        # Sisipkan koma sebelum kata hubung umum jika belum ada koma
        conjunctions = [
            "tetapi", "tapi", "karena", "sehingga", "sedangkan", 
            "namun", "melainkan", "padahal", "bahkan", "yaitu", "yakni"
        ]
        for conj in conjunctions:
            text = re.sub(r'(?<!,)\s+(' + conj + r')\b', r', \1', text, flags=re.IGNORECASE)

        # Rapikan koma ganda atau spasi berlebih
        text = re.sub(r',\s*,+', ',', text)
        text = re.sub(r'\s+', ' ', text)

        if not text.endswith(('.', '!', '?')):
            text += '.'

        return text

    def stream_tts_to_speaker(self, text, voice, rate, speaker_id):
        """
        Streaming potongan audio Edge-TTS langsung ke PyAV untuk didecode ke PCM
        dan diputar ke output device secara realtime tanpa jeda file MP3.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_stream_and_play(text, voice, rate, speaker_id))
        finally:
            loop.close()

    async def _async_stream_and_play(self, text, voice, rate, speaker_id):
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        codec = av.CodecContext.create('mp3', 'r')

        # Inisialisasi output stream Sounddevice
        # Edge-TTS menghasilkan MP3 24000 Hz Mono
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
                    # Parse paket MP3 dari potongan data streaming
                    packets = codec.parse(chunk['data'])
                    for packet in packets:
                        frames = codec.decode(packet)
                        for frame in frames:
                            if not self.is_running:
                                return
                            # Ubah frame audio ke numpy array PCM (samples, 1) int16
                            pcm_data = frame.to_ndarray().T
                            stream.write(pcm_data)

            # Flush sisa frame dari codec
            for frame in codec.decode():
                if not self.is_running:
                    return
                pcm_data = frame.to_ndarray().T
                stream.write(pcm_data)

    def on_close(self):
        self.is_running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RealtimeVoiceChanger(root)
    root.mainloop()
