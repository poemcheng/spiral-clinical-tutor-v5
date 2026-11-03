@echo off
setlocal
cd /d "%~dp0"
if not exist .venv-graphics\Scripts\python.exe (
  py -3 -m venv .venv-graphics
  if errorlevel 1 goto failed
)
.venv-graphics\Scripts\python.exe -c "import fastapi,uvicorn,httpx,dotenv" >nul 2>&1
if errorlevel 1 (
  .venv-graphics\Scripts\python.exe -m pip install -r requirements-graphics.txt
  if errorlevel 1 goto failed
)
echo Graphics teaching workspace: http://127.0.0.1:8715
echo First administrator credentials: runtime\graphics\initial-admin.txt
echo Use Ctrl+C to stop. Clinical port 8705 and data are separate.
.venv-graphics\Scripts\python.exe -m uvicorn backend.graphics_server:app --host 127.0.0.1 --port 8715
if errorlevel 1 goto failed
exit /b 0
:failed
echo Startup failed. Install Python 3.11+ and inspect the error above.
pause
exit /b 1
