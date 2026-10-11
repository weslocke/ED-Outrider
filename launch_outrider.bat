@echo off
rem Start ED Outrider on Windows, setting it up first when needed: makes the virtual environment (.venv) and installs
rem requirements.txt on the first run, again whenever requirements.txt has changed (after a git pull), and if the
rem environment is broken; otherwise it starts at once. Double-click it, or run it in a Command Prompt; any arguments
rem go to Outrider (launch_outrider.bat --port 8026). PYTHON=C:\path\to\python.exe picks the Python that makes the
rem environment (3.11 or newer); otherwise the py launcher's newest Python 3, then python on the PATH.
rem Auto honk, auto-target and the control rail are experimental on Windows; the co-pilot button is Linux only for
rem now; everything else works. The Linux and macOS launcher is launch_outrider.sh.
rem Kept with Windows line endings (.gitattributes): cmd can misread labels in a file with Unix ones.
setlocal
cd /d "%~dp0"

set "VENV=.venv"
rem requirements.txt as it was when last installed
set "STAMP=%VENV%\.requirements.txt"
set "VPY=%VENV%\Scripts\python.exe"

if not exist "%VPY%" goto create
rem installs again when requirements.txt changed since (or the stamp is missing), or the environment is broken
rem (no aiohttp); compared in Python, not with fc, which is unreliable outside Windows (Wine)
"%VPY%" -c "import aiohttp, sys; sys.exit(open('requirements.txt', 'rb').read() != open(r'%STAMP%', 'rb').read())" >nul 2>&1 || goto install
goto run

:create
set "PY="
if defined PYTHON set PY="%PYTHON%"
if defined PY goto checkpy
py -3 --version >nul 2>&1 && set "PY=py -3"
if defined PY goto checkpy
python --version >nul 2>&1 && set "PY=python"
if defined PY goto checkpy
echo Python not found. Install Python 3.11 or newer from https://www.python.org/downloads/ (tick "Add python.exe to
echo PATH"), or set PYTHON=C:\path\to\python.exe
goto fail

:checkpy
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 && goto makevenv
echo ED Outrider needs Python 3.11 or newer, and found:
%PY% --version
echo Install a newer one from https://www.python.org/downloads/ or set PYTHON=C:\path\to\python.exe
goto fail

:makevenv
echo Setting up ED Outrider: creating %VENV% (the first time takes a minute or two: about 100 MB with Piper)
%PY% -m venv "%VENV%" || goto venvfail
"%VPY%" -m pip --version >nul 2>&1 && goto install
:venvfail
rem nothing half-made left behind: the next run starts clean
if exist "%VENV%" rmdir /s /q "%VENV%"
echo Could not create %VENV% with %PY%.
goto fail

:install
rem a half-made environment (python but no pip) is made again rather than failing on every run
"%VPY%" -m pip --version >nul 2>&1 && goto pipok
echo %VENV% is incomplete (no pip): making it again
rmdir /s /q "%VENV%"
goto create
:pipok
echo Installing ED Outrider's requirements into %VENV%
"%VPY%" -m pip install --quiet --upgrade pip
"%VPY%" -m pip install --quiet -r requirements.txt && goto stamp
echo Installing the requirements failed (the messages above say why). Piper's line in requirements.txt can be
echo removed to do without the natural voice. Then run this again.
goto fail

:stamp
copy /y requirements.txt "%STAMP%" >nul

:run
"%VPY%" ed_outrider.py %*
if errorlevel 1 goto stopped
exit /b 0

:stopped
echo.
echo ED Outrider stopped with an error (see above).
pause
exit /b 1

:fail
pause
exit /b 1
