@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  猫狗品种分类识别系统 - 一键启动（后端 + 前端）
rem  双击本文件即可启动整个 Web 系统。
rem  通过 %~dp0 定位项目根目录，不依赖当前终端所在目录。
rem ============================================================
set "ROOT=%~dp0"

echo ============================================================
echo   猫狗品种分类识别系统 - 启动向导
echo ============================================================
echo.

rem ---------- 启动前检查 ----------
set "MISSING="
if not exist "%ROOT%.venv\Scripts\python.exe" set "MISSING=1"
if not exist "%ROOT%frontend\package.json" set "MISSING=1"
if not exist "%ROOT%artifacts\best_model.pth" set "MISSING=1"

if defined MISSING (
    echo [错误] 启动前检查未通过，缺少必要文件：
    if not exist "%ROOT%.venv\Scripts\python.exe"  echo   - .venv\Scripts\python.exe（Python 虚拟环境）
    if not exist "%ROOT%frontend\package.json"     echo   - frontend\package.json（前端项目）
    if not exist "%ROOT%artifacts\best_model.pth"  echo   - artifacts\best_model.pth（训练好的模型权重）
    echo.
    echo 请先按 README.md 的 "首次启动" 章节完成环境与模型准备。
    echo.
    pause
    exit /b 1
)
echo [检查] 必要文件齐全。

rem ---------- Node 检查（信息提示，不阻断） ----------
where node >nul 2>nul
if errorlevel 1 (
    set "NODE_DIR="
    for /d %%D in ("%ROOT%tools\node\*") do if exist "%%~D\node.exe" set "NODE_DIR=%%~D"
    if defined NODE_DIR (
        echo [检查] 使用项目内置 Node.js: %NODE_DIR%
    ) else (
        echo [提示] 未在 PATH 找到 Node.js；前端启动脚本将尝试使用
        echo        tools\node 下的运行时，若失败请按 README 安装 Node.js LTS。
    )
) else (
    echo [检查] Node.js 已可用。
)

rem ---------- 分别在独立窗口启动后端与前端 ----------
echo.
echo [启动] 正在打开后端窗口（FastAPI :8000）...
start "CatDogBreedNet-Backend" "%ROOT%启动后端.bat"
echo [启动] 正在打开前端窗口（Vite :5173）...
start "CatDogBreedNet-Frontend" "%ROOT%启动前端.bat"

echo.
echo ============================================================
echo   启动完成提示：
echo   1. 在后端窗口等待 "Application startup complete"
echo      （模型加载完成，约需几秒到十几秒）；
echo   2. 在前端窗口等待出现 "Local: http://127.0.0.1:5173/"；
echo   3. 然后打开浏览器访问: http://127.0.0.1:5173
echo.
echo   停止方法：分别关闭 "后端" 与 "前端" 两个黑色命令行窗口
echo   （或在其窗口中按 Ctrl+C）。
echo   查看错误：窗口内的红色信息即为错误原因；
echo   详细日志见 README.md "日常使用" 章节。
echo ============================================================
echo.
pause
