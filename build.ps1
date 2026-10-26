Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Membangun ulang speech2google.exe..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "Mengaktifkan Virtual Environment (.venv)..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
}

Get-Process -Name "speech2google" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Menjalankan PyInstaller..." -ForegroundColor Green
pyinstaller --noconfirm --clean NeuralVoiceChanger.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  [SUKSES] Build selesai!" -ForegroundColor Green
    Write-Host "  File executable terbaru ada di: dist\speech2google.exe" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Red
    Write-Host "  [GAGAL] Terjadi kesalahan saat proses build." -ForegroundColor Red
    Write-Host "========================================================" -ForegroundColor Red
}
