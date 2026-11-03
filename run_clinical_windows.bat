@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe tools\check_dependencies.py
if not errorlevel 1 goto ready
echo Installing platform dependencies for this version...
if exist requirements.lock.txt (
  .venv\Scripts\python.exe -m pip install -r requirements.lock.txt
) else (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if errorlevel 1 goto fail
:ready
if exist runtime\models\faster-whisper-base\vocabulary.txt goto voice_ready
echo Installing the local speech model once. Recordings stay on this computer.
.venv\Scripts\python.exe tools\prepare_voice.py
if errorlevel 1 echo Speech model download failed. Text chat remains available.
:voice_ready
echo Opening a fresh sign-in page. Existing server can remain running.
echo Administrator: user / 1234 on first installation. Create learner and teacher accounts in the platform.
set PLATFORM_PORT=8705
set OPEN_PLATFORM_BROWSER=1
.venv\Scripts\python.exe run.py
exit /b
:fail
echo Setup failed. Please inspect the error above.
pause
