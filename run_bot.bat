@echo off
cd /d "%~dp0"
echo Starting Naukri Auto-Apply...
python naukri_bot.py
echo.
echo Done. Check naukri_bot.log for details.
pause
