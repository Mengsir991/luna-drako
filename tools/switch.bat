@echo off
setlocal enabledelayedexpansion
set "PY=C:\Users\93149\.workbuddy\binaries\python\versions\3.13.12\python.exe"
cd /d "%~dp0"

if not exist "%PY%" (
  echo [ERROR] Python not found: %PY%
  pause
  exit /b 1
)

if "%~1"=="" goto MENU
set "SEL=%~1"
goto RUN

:MENU
echo.
echo  ===== Luna Fury33 EVO firmware switch =====
echo   1. hybrid  - HyperMode ON = locked 20k, normal = stock adaptive (power saving)
echo   2. fps     - always locked 20000 fps (max performance)
echo   3. stock   - stock framerate, only low-DPI patch kept
echo.
set /p SEL=Enter 1/2/3 (default 1):
if "%SEL%"=="1" set "SEL=hybrid"
if "%SEL%"=="2" set "SEL=fps"
if "%SEL%"=="3" set "SEL=stock"
if "%SEL%"=="" set "SEL=hybrid"

:RUN
echo.
echo  *** Keep the USB cable plugged in! ***
echo.
"%PY%" switch_fw.py %SEL%
echo.
pause
