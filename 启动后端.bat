@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  猫狗品种分类识别系统 - 后端启动脚本 (FastAPI / Uvicorn)
rem  通过 %~dp0 定位项目根目录，不依赖当前终端所在目录
rem ============================================================
set "ROOT=%~dp0"

echo [1/3] 检查 Python 虚拟环境 ...
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo [错误] 未找到 "%ROOT%.venv\Scripts\python.exe"。
    echo         请先按 README.md 的说明创建虚拟环境：
    echo         E:\CatDogBreedNet\tools\python\python.exe -m venv E:\CatDogBreedNet\.venv
    echo         然后安装依赖：pip install -r requirements.txt
    pause
    exit /b 1
)

echo [2/3] 检查模型文件 ...
if not exist "%ROOT%artifacts\best_model.pth" (
    echo [错误] 未找到模型权重 "%ROOT%artifacts\best_model.pth"。
    echo         请先按 README.md 训练模型：python -m ml.train
    pause
    exit /b 1
)
if not exist "%ROOT%artifacts\class_names.json" (
    echo [错误] 未找到类别映射 "%ROOT%artifacts\class_names.json"。
    pause
    exit /b 1
)

rem 训练缓存与下载缓存固定在 E 盘，避免写入 C 盘
if not exist "%ROOT%.cache\torch" mkdir "%ROOT%.cache\torch"
set "TORCH_HOME=%ROOT%.cache\torch"

echo [3/3] 启动 FastAPI 后端: http://127.0.0.1:8000
echo        交互式 API 文档: http://127.0.0.1:8000/docs
echo        请等待出现 "Application startup complete" 且模型加载完成后再使用前端。
echo.
"%ROOT%.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --port 8000
if errorlevel 1 (
    echo.
    echo [错误] 后端启动失败。常见原因：
    echo   - 端口 8000 被占用（关闭其他占用该端口的程序后重试）
    echo   - 依赖未安装（pip install -r requirements.txt）
    echo   - GPU/CUDA 问题（可设置 CATDOG_DEVICE=cpu 后重试）
    pause
)
