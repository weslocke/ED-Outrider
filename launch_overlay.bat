@echo off
rem Start ED Outrider's in-game overlay window (python -m outrider.overlay_window): it draws Outrider's panels over
rem Elite's window. Uses Outrider's own environment (.venv: run launch_outrider.bat once first) and offers to install
rem PyQt6 into it the first time (about 100 MB). Any arguments go to the window (launch_overlay.bat --url
rem http://192.168.1.81:8025 --password ... for an Outrider on a server). Windows is not yet tried against the game.
rem Kept with Windows line endings (.gitattributes), as launch_outrider.bat is.
setlocal
cd /d "%~dp0"
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo Outrider's environment ^(.venv^) is not set up yet: run launch_outrider.bat once first.
  goto fail
)
"%VPY%" -c "import PyQt6.QtWidgets" >nul 2>&1 && goto run
echo The overlay needs PyQt6 ^(about 100 MB^), installed into Outrider's .venv only.
set /p "YES=Install it now? [y/N] "
if /i not "%YES%"=="y" (
  echo Not installed. To install it yourself: %VPY% -m pip install -r requirements-overlay.txt
  goto fail
)
"%VPY%" -m pip install --quiet -r requirements-overlay.txt || (echo Installing PyQt6 failed. & goto fail)
:run
"%VPY%" -m outrider.overlay_window %*
exit /b %ERRORLEVEL%
:fail
pause
exit /b 1
