@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 install.py
) else (
  python install.py
)
if not %ERRORLEVEL%==0 (
  echo zmcp installation failed. See the error above.
  pause
  exit /b 1
)
echo Restart ChatGPT Desktop, then enable or reinstall zmcp in Plugins.
pause
