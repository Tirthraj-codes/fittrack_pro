@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (set PY=python) else (set PY=py -3)

echo Creating the virtual environment...
%PY% -m venv venv
if errorlevel 1 goto error

echo Installing packages (internet needed once)...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo Setup finished. Now double-click start_demo.bat
pause
exit /b 0

:error
echo.
echo Something went wrong. Install Python 3.12 or 3.13 from python.org, tick "Add python.exe to PATH", then run setup.bat again.
pause
exit /b 1