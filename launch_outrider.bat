@echo off
rem Start ED Outrider on Windows, setting it up first when needed: makes the virtual environment (.venv) and installs
rem requirements.txt on the first run, again whenever requirements.txt has changed (after a git pull), and if the
rem environment is broken; otherwise it starts at once. With the in-game overlay on ([overlay] enabled = true) it also
rem installs PyQt6 when missing. Double-click it, or run it in a Command Prompt; any arguments
rem go to Outrider (launch_outrider.bat --port 8026). PYTHON=C:\path\to\python.exe picks the Python that makes the
rem environment (3.11 or newer); otherwise the py launcher's newest Python 3, then python on the PATH.
rem Auto honk, auto-target and the control rail are experimental on Windows; the co-pilot button is Linux only for
rem now; everything else works. The Linux and macOS launcher is launch_outrider.sh.
rem Kept with Windows line endings (.gitattributes): cmd can misread labels in a file with Unix ones.
setlocal
rem relative paths in the arguments are the caller's: Outrider runs from the folder this was started in
set "CALLER=%CD%"
cd /d "%~dp0"
set "HERE=%CD%"
rem Settings -> Server's Restart: Outrider exits with 75 and this starts it again (below), setup included
set "OUTRIDER_LAUNCHER=%~f0"
set "PP0=%PYTHONPATH%"

set "VENV=.venv"
rem requirements.txt as it was when last installed
set "STAMP=%VENV%\.requirements.txt"
set "VPY=%VENV%\Scripts\python.exe"
rem the date certifi was last checked for a newer version (below)
set "CERTSTAMP=%VENV%\.certifi-checked"

:check
if not exist "%VPY%" goto create
if defined OUTRIDER_REINSTALL goto install
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
rem one line at a time when all at once fails (scripts\install_requirements.py: 0 all, 2 optional ones missing,
rem 3 offline with a working environment: start without a new stamp, 1 cannot run)
"%VPY%" scripts\install_requirements.py requirements.txt
if %errorlevel% equ 0 goto stamp
if %errorlevel% equ 2 goto stamp
if %errorlevel% equ 3 goto run
goto fail

:stamp
copy /y requirements.txt "%STAMP%" >nul

:run
rem certifi (the root certificates every HTTPS request also trusts, outrider\tls.py) upgraded once a week: pip never
rem upgrades an installed one that meets requirements.txt's floor (the author, 2026-10-14). The stamp holds the date
rem of the last check, compared in Python (not with cmd's date, which depends on the region's format); written only
rem when pip got through, so an offline start tries again next time. Never stops Outrider from starting.
"%VPY%" -c "import datetime as d, sys; s = open(sys.argv[1]).read().strip(); sys.exit(not 0 <= (d.date.today() - d.date.fromisoformat(s)).days < 7)" "%CERTSTAMP%" >nul 2>&1 && goto overlay
"%VPY%" -m pip install --upgrade --quiet --disable-pip-version-check --retries 1 --timeout 10 certifi >nul 2>&1 && goto certstamp
echo certifi: could not check for a newer certificate bundle (offline?); using the installed one
goto overlay
:certstamp
"%VPY%" -c "import datetime, sys; open(sys.argv[1], 'w').write(datetime.date.today().isoformat() + '\n')" "%CERTSTAMP%"

:overlay
rem the in-game overlay's PyQt6, installed when [overlay] enabled is true in the config and it is missing; run in the
rem caller's folder like Outrider, so a relative --config is the same file
cd /d "%CALLER%"
set "PP=%HERE%"
if defined PP0 set "PP=%HERE%;%PP0%"
set "PYTHONPATH=%PP%"
"%HERE%\%VPY%" -m outrider.overlay_runner --setup %*
"%HERE%\%VPY%" "%HERE%\ed_outrider.py" %*
rem 75: Settings -> Server's Restart asked to be started again (checked before the error's pause)
if %errorlevel% equ 75 goto again
if errorlevel 1 goto stopped
exit /b 0

:again
echo Restarting ED Outrider
cd /d "%HERE%"
goto check

:stopped
echo.
echo ED Outrider stopped with an error (see above).
pause
exit /b 1

:fail
pause
exit /b 1
