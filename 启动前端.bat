@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  猫狗品种分类识别系统 - 前端启动脚本 (Vue 3 / Vite)
rem  通过 %~dp0 定位项目根目录，不依赖当前终端所在目录
rem ============================================================
set "ROOT=%~dp0"

echo [1/4] 检查前端项目 ...
if not exist "%ROOT%frontend\package.json" (
    echo [错误] 未找到 "%ROOT%frontend\package.json"。
    pause
    exit /b 1
)

echo [2/4] 检查 Node.js ...
rem 优先使用 PATH 中的 Node；否则回退到项目 E 盘 tools\node 下的运行时
where node >nul 2>nul
if errorlevel 1 (
    set "NODE_DIR="
    for /d %%D in ("%ROOT%tools\node\*") do if exist "%%~D\node.exe" set "NODE_DIR=%%~D"
    if defined NODE_DIR (
        echo        使用项目内置 Node: %NODE_DIR%
        set "PATH=%NODE_DIR%;%PATH%"
    ) else (
        echo [错误] 未找到 Node.js。请安装 Node.js LTS 并加入 PATH，
        echo        或按 README.md 将 Node 解压到 tools\node 目录。
        pause
        exit /b 1
    )
) else (
    for /f "delims=" %%i in ('where node') do echo        使用 Node: %%i
)

rem npm 缓存固定在 E 盘，避免写入 C 盘
set "npm_config_cache=%ROOT%.cache\npm"
if not exist "%ROOT%.cache\npm" mkdir "%ROOT%.cache\npm"

cd /d "%ROOT%frontend"

echo [3/4] 检查依赖 ...
if not exist node_modules (
    echo        首次运行，正在安装前端依赖 npm install ...
    call npm install
    if errorlevel 1 (
        echo [错误] npm install 失败。请检查网络后重试。
        pause
        exit /b 1
    )
)

echo [4/4] 启动 Vite 开发服务器 ...
echo        本地访问地址: http://127.0.0.1:5173
echo        请等待出现 "Local: http://127.0.0.1:5173/" 后再打开浏览器。
echo.
call npm run dev
if errorlevel 1 (
    echo.
    echo [错误] 前端启动失败。常见原因：
    echo   - 端口 5173 被占用
    echo   - 依赖损坏（可删除 frontend\node_modules 后重新运行本脚本）
    pause
)
