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
rem ---------------------------------------------------------------------------
rem 默认推理模型为 exp06（V2.2 候选，136 类，256 分辨率）。
rem 若已通过环境变量 CATDOG_WEIGHTS_PATH / CATDOG_CLASS_NAMES_PATH 显式指定
rem （例如回退到 V2.1 或 V1.1），则尊重该设置，不再检查默认路径。
rem ---------------------------------------------------------------------------
set "MODEL_DIR=%ROOT%artifacts\v2_2_border_collie_exp06_resolution256_lowlr_seed42"
rem 类别映射沿用既有那份 136 类表（与 exp06 目录内的副本字节相同）
set "CLASS_NAMES_FILE=%ROOT%artifacts\v2_1_136classes_seed42\class_names.json"
if not defined CATDOG_WEIGHTS_PATH (
    if not exist "%MODEL_DIR%\best_model.pth" (
        echo [错误] 未找到默认模型权重 "%MODEL_DIR%\best_model.pth"。
        echo         默认模型为 exp06（136 类，256 分辨率）；请确认模型目录完整。
        echo         如需回退到 V2.1（136 类，224 分辨率），先设置再启动：
        echo             set CATDOG_WEIGHTS_PATH=%ROOT%artifacts\v2_1_136classes_seed42\best_model.pth
        echo             set CATDOG_CLASS_NAMES_PATH=%ROOT%artifacts\v2_1_136classes_seed42\class_names.json
        echo             set CATDOG_IMAGE_SIZE=224
        echo         如需回退到 V1.1（37 类，224 分辨率），先设置再启动：
        echo             set CATDOG_WEIGHTS_PATH=%ROOT%artifacts\best_model.pth
        echo             set CATDOG_CLASS_NAMES_PATH=%ROOT%artifacts\class_names.json
        echo             set CATDOG_IMAGE_SIZE=224
        pause
        exit /b 1
    )
)
if not defined CATDOG_CLASS_NAMES_PATH (
    if not exist "%CLASS_NAMES_FILE%" (
        echo [错误] 未找到默认类别映射 "%CLASS_NAMES_FILE%"。
        echo         权重与类别表必须配对，缺一不可。
        echo         如需回退到 V2.1（136 类），先设置再启动：
        echo             set CATDOG_WEIGHTS_PATH=%ROOT%artifacts\v2_1_136classes_seed42\best_model.pth
        echo             set CATDOG_CLASS_NAMES_PATH=%ROOT%artifacts\v2_1_136classes_seed42\class_names.json
        echo             set CATDOG_IMAGE_SIZE=224
        pause
        exit /b 1
    )
)
if defined CATDOG_WEIGHTS_PATH echo [检查] 已通过环境变量指定权重: %CATDOG_WEIGHTS_PATH%
if defined CATDOG_CLASS_NAMES_PATH echo [检查] 已通过环境变量指定类名表: %CATDOG_CLASS_NAMES_PATH%

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
