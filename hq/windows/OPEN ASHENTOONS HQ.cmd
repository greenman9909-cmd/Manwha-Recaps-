@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\AshenToons\control-room\Start-AshenToonsHQ.ps1"
if errorlevel 1 (
  echo AshenToons could not start. See the preceding error.
  pause
)
