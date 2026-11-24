@echo off
setlocal
cd /d "%~dp0"
if not exist routing.json (echo Open SplitDesk Stereo and save Devices first. & pause & exit /b 1)
"venv\Scripts\python.exe" router.py check
if errorlevel 1 (echo See routing.log for details. & pause & exit /b 1)
echo Endpoint checks complete.
pause
