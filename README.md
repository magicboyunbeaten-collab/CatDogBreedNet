# 猫狗品种分类识别系统（Cat/Dog Breed Classification System）

基于深度学习的猫狗品种分类识别系统——本科毕业设计项目。
分类方案：**方案 B，单模型多类别品种分类**（一个多类别分类器直接预测 37 个具体猫狗品种，不是仅输出 Cat/Dog 二分类）。

> 开发规范见 [`md/CODEBUDDY.md`](md/CODEBUDDY.md)；任务进度见 `md/TODO.md`、`md/PROGRESS.md`、`md/DONE.md`。

## 当前进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 0 | 仓库检查与计划 | ✅ 已完成（2026-10-12） |
| 阶段 1 | 环境与数据管道 | ✅ 已完成（2026-10-12） |
| 阶段 2 | 模型基线（ResNet18 训练/预测） | ✅ 已完成（2026-10-13，最佳验证精度 0.8401） |
| 阶段 3 | 评估实验（指标/混淆矩阵/性能测试） | ✅ 已完成（2026-10-13，测试集 Accuracy 0.8035 / Macro-F1 0.8022） |
| 阶段 4 | 后端 API（FastAPI + SQLite） | ✅ 已完成（2026-10-13） |
| 阶段 5 | 前端（Vue 3 + Element Plus） | ✅ 已完成（2026-10-13） |
| 阶段 6 | 联调、测试与文档 | ⬜ 未开始 |

**当前可用命令**：数据集准备、模型训练、单图预测、测试集评估、FastAPI 后端、Vue 3 前端（见下文）。

## 环境要求（本机实测配置）

- **操作系统**：Windows 11（x64）
- **Python**：3.11.9，独立运行时位于 `tools/python`（E 盘，不依赖 C 盘；由 python-build-standalone 独立包解压而来，SHA256 已验证）
- **GPU**：NVIDIA RTX 4060 Laptop 8GB，驱动 610.47（CUDA UMD 13.3）
- **PyTorch**：2.14.1+cu130 / torchvision 0.29.1+cu130（实测 `torch.cuda.is_available() == True`）
- **Node.js**：阶段 5（前端）时再按同样"非 C 盘"规则安装
- **Git**：需用户手动安装（尚未安装，因此仓库尚未 `git init`）

所有缓存（pip/torch）与数据均位于 E 盘：`PIP_CACHE_DIR=E:\CatDogBreedNet\.cache\pip`、`TORCH_HOME=E:\CatDogBreedNet\.cache\torch`（已设置为用户级环境变量）。

## 安装步骤

```powershell
# 1. 创建虚拟环境（使用 E 盘独立 Python）
E:\CatDogBreedNet\tools\python\python.exe -m venv E:\CatDogBreedNet\.venv

# 2. 安装 CUDA 版 PyTorch（索引地址以 pytorch.org 当前公告为准；本机实测 cu130）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pip install --upgrade pip
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130

# 3. 安装其余依赖
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. 验证 GPU 可用
E:\CatDogBreedNet\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

> 说明：不直接调用 `.venv\Scripts\Activate.ps1`（可能被 PowerShell 执行策略拦截），统一使用虚拟环境的 `python.exe` 绝对路径。

## 数据集：Oxford-IIIT Pet Dataset

- **来源**：<https://www.robots.ox.ac.uk/~vgg/data/pets/>（官方源，自动重定向至 `thor.robots.ox.ac.uk`）
- **规模**：37 个品种（12 个猫品种 + 25 个狗品种），共 7349 张图片
- **许可**：官方 README 原文——"Dataset is made available for research purposes only. Use of these images must respect the corresponding terms of use of original websites from which they are taken."（详见 [`reports/dataset.md`](reports/dataset.md)）
- **引用**：O. M. Parkhi, A. Vedaldi, A. Zisserman, C. V. Jawahar. *Cats and Dogs*. CVPR 2012.

```powershell
# 下载官方压缩包（images.tar.gz 约 792MB + annotations.tar.gz 约 19MB）到 data/raw
E:\CatDogBreedNet\.venv\Scripts\python.exe scripts\prepare_dataset.py download

# 解压并构建 ImageFolder 划分（train/val/test/<品种>/）
E:\CatDogBreedNet\.venv\Scripts\python.exe scripts\prepare_dataset.py build --seed 42 --val-ratio 0.1

# 打印各子集与各类别样本数统计
E:\CatDogBreedNet\.venv\Scripts\python.exe scripts\prepare_dataset.py stats
```

**划分方案（如实记录）**：

- `test` = 官方 test 划分（3669 张）；
- `train`/`val` = 官方 trainval 划分（3680 张）按类别分层、种子 42、`val_ratio=0.1` 划分，得到 train 3311 / val 369；
- 相同种子重复运行结果完全一致（已验证）；三集之间通过图片 ID 与内容 MD5 双重检查无重复。

## 项目结构

```text
CatDogBreedNet/
├── ml/                     # 模型与数据代码（config/dataset/model/train/predict/evaluate/predictor）
├── scripts/
│   └── prepare_dataset.py  # 数据管道：download / build / stats
├── backend/
│   └── app/                # FastAPI 后端（main/config/schemas/database/models + routes + services）
├── frontend/               # Vue 3 前端（src + tests，node_modules/dist 不入 Git）
├── data/
│   ├── raw/                # 官方压缩包与解压文件（不入 Git）
│   ├── processed/          # train/val/test/<品种>/ ImageFolder 结构（不入 Git）
│   └── app.db              # SQLite 数据库（不入 Git，由后端自动创建）
├── uploads/                # 上传图片（不入 Git，随机文件名）
├── artifacts/              # 模型产物（best_model.pth 等，权重不入 Git）
├── reports/                # 数据集报告、训练指标、评估报告
├── tests/                  # pytest 单元测试（合成小图/假 Predictor，不依赖真实推理）
├── tools/
│   ├── python/             # E 盘独立 Python 3.11.9 运行时（不入 Git）
│   └── node/               # E 盘 Node.js v24.21.0 LTS 运行时（不入 Git）
├── md/                     # 开发规范与三文件进度
├── .env.example            # 后端配置样例（复制为 .env 使用，.env 不入 Git）
├── requirements.txt
└── README.md
```

## 训练与预测（阶段 2）

```powershell
# 训练 ResNet18 基线（默认 10 epochs / batch 32；显存不足时减小 --batch-size）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m ml.train

# 单图 Top-3 预测（使用 artifacts/best_model.pth）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m ml.predict --image data\processed\test\Siamese\Siamese_20.jpg --top-k 3
```

训练产物（`artifacts/`，权重不入 Git）：

- `best_model.pth`：按验证集精度选择的最佳权重；
- `last_model.pth`：最后一个 epoch 的权重；
- `class_names.json`：37 个类别名（顺序与训练集 ImageFolder 一致）；
- `experiment_config.json`：完整超参数、数据规模与软硬件环境。

训练日志与曲线（`reports/`）：`train_log.csv`、`loss_curve.png`、`accuracy_curve.png`
（由 `.gitignore` 排除，仅本机留存）；实验摘要见 [`reports/README.md`](reports/README.md)。

**已完成的基线结果（真实运行）**：10 epochs 共 198.8s，最佳验证精度 **0.8401**（epoch 8）；
对 6 个品种的测试图片抽样预测 Top-1 全部正确。测试集整体指标（Accuracy/Macro-F1/混淆矩阵）
属阶段 3，尚未计算。

## 测试集评估（阶段 3）

```powershell
# 完整 test 集（3669 张）评估 + 推理性能测试
E:\CatDogBreedNet\.venv\Scripts\python.exe -m ml.evaluate

# 仅指标，跳过性能测试
E:\CatDogBreedNet\.venv\Scripts\python.exe -m ml.evaluate --no-benchmark
```

产物（`reports/`，CSV/PNG 不入 Git）：`test_metrics.json`、
`classification_report.csv`、`confusion_matrix.csv`、`confusion_matrix.png`、
`confusion_matrix_normalized.png`、`inference_benchmark.json`、
`evaluation_summary.md`。

**测试集真实结果**（官方 test 划分 3669 张，未参与调参）：Accuracy **0.8035**、
Macro-F1 **0.8022**、Weighted-F1 **0.8026**；混淆最严重的是两种斗牛犬互混与
Siamese/Birman/Ragdoll 长毛猫互混。推理性能：模型纯推理 1184.9 img/s（batch 32，
单张平均 2.95ms），端到端（含预处理）平均 7.18ms/张——详见
[`reports/evaluation_summary.md`](reports/evaluation_summary.md)。

## 后端 API（阶段 4）

```powershell
# 启动（仓库根目录；模型在启动时加载一次，之后所有请求复用）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

交互式文档：<http://127.0.0.1:8000/docs>（OpenAPI 自动生成）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务状态、模型是否就绪、类别数 |
| POST | `/api/predict` | 上传图片识别（multipart/form-data，字段 `file`，可选 `top_k`，默认 3） |
| GET | `/api/history?page=&page_size=` | 识别历史（分页，按时间倒序） |
| GET | `/api/history/{record_id}` | 单条记录详情 |
| DELETE | `/api/history/{record_id}` | 删除记录及其上传图片 |
| GET | `/api/stats` | 统计（总次数、品种分布、每日趋势、平均推理耗时） |

预测响应示例（数值为真实格式示例，非固定结果）：

```json
{
  "success": true,
  "record_id": 1,
  "predictions": [{"breed": "beagle", "confidence": 0.979491}],
  "elapsed_ms": 56.8,
  "inference_ms": 3.6,
  "preprocess_ms": 1.7,
  "top_k": 3,
  "num_classes": 37,
  "note": "confidence is a softmax score over the trained class set, not a true probability"
}
```

计时口径：`elapsed_ms` = 服务端处理总耗时（上传校验 + 预处理 + 推理）；
`inference_ms` = 仅模型前向；`preprocess_ms` = 仅图片解码与变换。三者不可互比。

**上传安全与保留策略**：

- 大小上限 10MB（读取时流式校验，超限返回 413）；支持 JPEG/PNG/WebP（Pillow 实解析，
  不信扩展名与 Content-Type）；像素总数上限 2500 万（防解压炸弹）；损坏/伪造图片返回 400。
- 服务端文件名随机生成（UUID），用户无法控制保存路径；只保存在 `uploads/` 目录内。
- 图片保留策略：预测成功后图片保留在 `uploads/` 供历史记录引用，删除对应历史记录时
  联动删除（且只允许删除上传目录内的文件）。重置方法：停止服务后删除 `data/app.db`
  与 `uploads/` 下的文件。
- 时间戳统一为 UTC ISO 8601（带 `+00:00` 偏移），如 `2026-10-13T10:51:36.341341+00:00`。
- 配置通过环境变量覆盖（见 `.env.example`）：权重路径、设备、上传目录、大小/像素上限、
  数据库路径、CORS 来源等；默认只放行 `http://localhost:5173` 与 `http://127.0.0.1:5173`。
- 模型在应用 lifespan 启动时加载一次；加载失败时 `/api/health` 的 `model_loaded=false`
  并给出简短原因，`/api/predict` 返回 503，不会返回伪造结果。
- 数据库写入失败返回 500 并记录服务端日志，同时清理本次生成的孤立图片，不会静默声称成功。

集成测试（真实运行，2026-10-13）：CLI 与 API 对同一张 `beagle_1.jpg` 的 Top-3 结果逐位一致
（beagle 0.979491 / basset_hound 0.005011 / miniature_pinscher 0.00496）。

## 前端（阶段 5）

前端为 Vue 3 + Vite + Vue Router + Element Plus + Axios + ECharts（JavaScript），
源码位于 `frontend/`，所有数据均来自真实后端 API，无任何写死的演示数据。

**Node.js 环境**（E 盘，避免占用 C 盘）：

- 运行时：`tools/node/node-v24.21.0-win-x64/`（Node.js v24.21.0 LTS + npm 11.19.0，
  官方 ZIP 安装，SHA256 已验证；已加入用户级 PATH）
- npm 缓存：`.cache/npm`（用户级环境变量 `npm_config_cache` 指向 E 盘）
- 前端依赖：`frontend/node_modules`（`package-lock.json` 已提交，锁住版本）

```powershell
# 启动后端（终端 1，仓库根目录）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000

# 启动前端（终端 2）
cd E:\CatDogBreedNet\frontend
npm install        # 首次
npm run dev        # 开发服务器 http://127.0.0.1:5173
```

本地访问地址：<http://127.0.0.1:5173>（自动跳转 `/predict`）。
后端地址通过 `frontend/.env.development` 的 `VITE_API_BASE_URL` 配置
（默认 `http://127.0.0.1:8000/api`，样例见 `frontend/.env.example`；该文件不入 Git，
代码内置了相同默认值作为回退）。端口 5173 已包含在后端 CORS 允许列表中。

**页面**：

| 页面 | 路径 | 功能 |
|---|---|---|
| 图片识别 | `/predict` | 点击/拖拽上传、本地预览（对象 URL 及时释放）、前端预检（服务端校验为准）、Top-3 品种与分数、三种耗时口径、错误提示与重试、一键清空 |
| 识别历史 | `/history` | 后端分页（10/20/50 每页）、记录 ID/图片文件名/品种/置信度/UTC 时间、详情弹窗、删除二次确认并联动删图 |
| 识别统计 | `/stats` | 总识别次数、平均推理耗时、覆盖品种数、品种分布图与每日趋势图（ECharts，组件卸载时销毁实例） |

顶栏实时显示模型就绪状态（`/api/health`，30 秒轮询）；后端不可用时页面显示
"无法连接后端服务"错误提示而非白屏。

**前端测试与构建**：

```powershell
cd E:\CatDogBreedNet\frontend
npm test           # Vitest：18 个用例（API 适配/错误规范化/文件预检，Mock 不依赖真实后端）
npm run build      # 生产构建（dist/，不入 Git）
```

真实联调（2026-10-13，uvicorn:8000 + vite:5173 + 真实 Chrome 浏览器实测）：
上传 `pug_1.jpg` → Top-1 pug 100.00%（记录入库）→ 历史页可见新记录 → 详情弹窗正常 →
删除确认后列表与统计同步更新 → 刷新页面历史仍在 → 停止后端后前端显示连接错误且不白屏。

## 测试

```powershell
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pytest tests/ -q
```

测试只使用临时合成的微型图片验证软件逻辑，不作为模型实验数据。

## 已知限制

- 普通分类器不保证识别训练类别之外的动物、物体或无效图片；
- Softmax 分数是模型在当前类别集合上的归一化分数，不应宣称为真实正确概率；
- 数据集仅限研究用途，图片版权归原始网站所有。
