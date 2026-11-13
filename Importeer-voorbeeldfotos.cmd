@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Start eerst Start-AstroWeb.cmd om de Python-omgeving te installeren.
  echo Run Start-AstroWeb.cmd first to install the Python environment.
  pause
  exit /b 1
)
echo Stop AstroWeb voordat je importeert / Stop AstroWeb before importing.
".venv\Scripts\python.exe" -m astroweb import --source AstroPhotos --render
pause
