@echo off
title Rebuilding speech2google EXE...
echo ========================================================
echo   Membangun ulang speech2google.exe...
echo ========================================================

REM Pindah ke direktori script ini
cd /d "%~dp0"

REM Periksa apakah virtual environment ada
if exist ".venv\Scripts\activate.bat" (
    echo Mengaktifkan Virtual Environment (.venv)...
    call .venv\Scripts\activate.bat
)

REM Jalankan PyInstaller menggunakan spec file yang sudah terkonfigurasi
echo Menjalankan PyInstaller...
pyinstaller --noconfirm --clean NeuralVoiceChanger.spec

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   [SUKSES] Build selesai!
    echo   File executable terbaru ada di: dist\speech2google.exe
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo   [GAGAL] Terjadi kesalahan saat build.
    echo ========================================================
)

pause
