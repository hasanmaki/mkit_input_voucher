@echo off
TITLE MKIT Input Voucher Service
echo Memulai Aplikasi...
echo Jangan ditutup window ini selama aplikasi digunakan.
echo ---------------------------------------------------
:: Update dependency otomatis jika ada perubahan (opsional, biar aman)
call uv sync --quiet

:: Jalankan server, otomatis buka browser
start "" "http://127.0.0.1:8000"
uv run fastapi run main.py --port 8000
pause
