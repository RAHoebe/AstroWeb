@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import astropy_healpix, scipy.spatial, flask, cv2, waitress" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
echo AstroWeb: http://127.0.0.1:8090
echo Open deze link in je browser. Sluit dit venster met Ctrl+C.
echo Open this link in your browser. Stop this window with Ctrl+C.
".venv\Scripts\python.exe" -m astroweb serve
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Starten mislukt / Startup failed. Zie de melding hierboven / See the error above.
pause
exit /b 1
