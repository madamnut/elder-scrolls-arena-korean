@echo off
setlocal
chcp 65001 >nul
title The Elder Scrolls Arena Korean Patch
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0patcher\patcher.ps1" -PackageRoot "%~dp0."
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo 설치기가 오류 코드 %EXIT_CODE%^(으^)로 종료되었습니다.
  pause
)
exit /b %EXIT_CODE%
