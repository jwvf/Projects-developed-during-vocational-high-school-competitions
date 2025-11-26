@echo off
setlocal EnableDelayedExpansion

:: === 绿色运行时路径 ===
set "RUNTIME=%~dp0runtime"
set "PYTHON=%RUNTIME%\python.exe"
set "CAPTURE=%~dp0capture_template.py"
set "DETECT=%~dp0main.py"
set "REQ=%~dp0requirements.txt"

:: === 检查绿色 Python ===
if not exist "%PYTHON%" (
    echo 未找到绿色运行时：%PYTHON%
    echo 请将 pyenv 或嵌入式 Python 整个目录复制到 runtime\
    pause
    exit /b 1
)

echo ===== 第 1 步：录制模板 =====
"%PYTHON%" "%CAPTURE%"
if %errorlevel% neq 0 (
    echo 录制失败，停止启动
    pause
    exit /b 1
)