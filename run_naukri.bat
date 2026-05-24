@echo off
cd /d "C:\Users\hp\Downloads\NaukriCronChecker"
echo [%DATE% %TIME%] Starting Naukri Auto-Apply...
"C:\Users\hp\P\Python\python.exe" naukri_bot.py
echo [%DATE% %TIME%] Done. Check naukri_bot.log and naukri_log.txt
