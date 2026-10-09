@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\AshenToons\control-room\Start-Google-Voice-Setup.ps1"
if errorlevel 1 pause
