@echo off
cd /d "%~dp0"
title GongGoo Server

echo ================================================
echo            GongGoo Backend Server
echo ================================================
echo.
echo  Starting server...
echo  The browser opens AUTOMATICALLY when ready.
echo  (please wait - first start can take 10-20 sec)
echo.
echo  To stop the server, just close this window.
echo.
echo ================================================
echo.

start "GongGoo Browser" /min cmd /c "%~dp0wait_and_open.bat"

venv\Scripts\python.exe manage.py migrate

venv\Scripts\python.exe manage.py runserver

echo.
echo Server stopped.
pause
