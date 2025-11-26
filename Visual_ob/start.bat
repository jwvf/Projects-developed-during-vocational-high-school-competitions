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

echo ===== 第 2 步：启动多区域检测 =====
:retry
"%PYTHON%" "%DETECT%" %*
if %errorlevel% neq 0 (
    echo 程序异常退出，5 秒后自动重试...
    timeout /t 5 >nul
    goto retry
)