@echo off
title VideoSaver - YouTube, TikTok, Facebook, Instagram
color 0F
echo.
echo  =======================================================
echo   VideoSaver - YouTube, TikTok, Facebook, Instagram
echo  =======================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python tidak ditemukan!
    echo  Install dari: https://www.python.org/downloads/
    pause & exit /b 1
)

echo  Menginstall/memperbarui dependencies...
pip install flask yt-dlp flask-cors --quiet --upgrade --no-warn-script-location
echo  [OK] Siap!
echo.
timeout /t 2 /nobreak >nul
start http://localhost:5000
echo  Server berjalan di: http://localhost:5000
echo  Tekan Ctrl+C untuk berhenti
echo.
python app.py
pause
