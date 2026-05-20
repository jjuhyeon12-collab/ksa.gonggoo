@echo off
set /a tries=0
:loop
set /a tries+=1
if %tries% gtr 90 exit
timeout /t 1 >nul
curl -s -o nul http://127.0.0.1:8000/
if errorlevel 1 goto loop
start "" http://127.0.0.1:8000/
