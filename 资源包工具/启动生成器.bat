@echo off
chcp 65001 >nul
set PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
if not exist "%PY%" set PY=python
"%PY%" "%~dp0奶龙动图资源包生成器.py"
if errorlevel 1 pause
