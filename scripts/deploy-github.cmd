@echo off
chcp 65001 >nul
title Deploy AI Deal Radar
"C:\Program Files\Git\bin\bash.exe" "%~dp0deploy-github.sh"
echo.
pause
