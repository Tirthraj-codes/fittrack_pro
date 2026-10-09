@echo off
cd /d "%~dp0"
echo This recreates all demo members, trainers and their data with fresh dates.
echo The admin login is kept. Close the black server window first.
set /p confirm=Type YES and press Enter to continue: 
if /i not "%confirm%"=="YES" (
  echo Cancelled.
  pause
  exit /b
)
venv\Scripts\python.exe manage.py seed_demo --reset --yes
pause