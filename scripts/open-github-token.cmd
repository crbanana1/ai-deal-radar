@echo off
chcp 65001 >nul
title GitHub Token - AI Deal Radar
if not exist "%~dp0..\github-token.txt" type nul > "%~dp0..\github-token.txt"
notepad "%~dp0..\github-token.txt"
