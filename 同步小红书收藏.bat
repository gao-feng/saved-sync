@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".codex-work\venv\Scripts\python.exe" (
  ".codex-work\venv\Scripts\python.exe" "scripts\windows_launcher.py" xiaohongshu
) else (
  py -3 --version >nul 2>&1
  if errorlevel 1 (
    python "scripts\windows_launcher.py" xiaohongshu
  ) else (
    py -3 "scripts\windows_launcher.py" xiaohongshu
  )
)
set "sync_exit=%errorlevel%"
echo.
pause
exit /b %sync_exit%
