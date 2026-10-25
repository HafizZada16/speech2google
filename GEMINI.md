# speech2google — Anti-Slop Engineering & Architecture Guidelines

This file defines the project coding standards, UI aesthetic requirements, and architecture rules for Google Antigravity and AI agents.

## Project Overview
`speech2google` is a high-performance, real-time speech-to-speech voice changer desktop application built on Windows.
- **UI Framework**: `customtkinter` (Modern Dark Mode with obsidian/slate/indigo palette)
- **Audio Capture**: `speech_recognition` + `pyaudio` (MME Host API filtered)
- **TTS Engine**: `edge-tts` (Neural voices: Gadis, Ardi, Jenny, Guy)
- **Audio Streaming & Decode**: PyAV (`av`) on-the-fly MP3 chunk decoding streamed directly to `sounddevice.OutputStream` (Zero disk I/O)
- **Packaging**: PyInstaller (`NeuralVoiceChanger.spec` -> `dist/speech2google.exe`) with auto-detected `sys.frozen` persistent `config.json`

---

## Anti-Slop Rules

### 1. Code Quality & Lean Implementation
- **Zero Redundant Comments**: Do not describe what standard Python code is doing line-by-line. Write comments only for non-trivial hardware workarounds or timing/audio calculations.
- **No Premature Abstraction**: Prefer direct, readable, procedural or cohesive object-oriented code. Do not introduce generic design patterns (factories, adapters, handlers) for single-purpose features.
- **Complete Implementations**: Never leave `# TODO` placeholders or omitted functions.

### 2. UI Anti-Slop Standards
- **Strict Color Tokens**:
  - `COLOR_BG = "#0d0f17"`
  - `COLOR_CARD = "#171a26"`
  - `COLOR_CARD_BORDER = "#25293d"`
  - `COLOR_TEXT_MAIN = "#f1f5f9"`
  - `COLOR_TEXT_MUTED = "#94a3b8"`
  - `COLOR_PRIMARY = "#4f46e5"` / hover `"#4338ca"`
  - `COLOR_DANGER = "#e11d48"` / hover `"#be123c"`
- **No Overflowing Menus**: Use native OS scrollbars (`Dark.TCombobox` with 16 dropdown height) and filter devices strictly by `hostapi == mme_index` to prevent 100+ duplicate WASAPI/DirectSound entries.

### 3. Architecture & Packaging
- **Local Persistence**: Always preserve `config.json` in `os.path.dirname(sys.executable)` when frozen.
- **Build Cleanliness**: Ensure `build/` and `dist/` remain in `.gitignore`. Use `.\build.bat` for redeploys.
