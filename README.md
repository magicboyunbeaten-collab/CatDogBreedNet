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
| 阶段 6 | 联调、测试与文档 | ✅ 已完成（2026-10-14） |

**项目已完成全部 6 个阶段**：数据管道 → 模型基线 → 评估实验 → FastAPI 后端 → Vue 3 前端 → 系统联调与测试。测试集指标：Accuracy 0.8035 / Macro-F1 0.8022（37 类，3669 张）。

**当前可用命令**：数据集准备、模型训练、单图预测、测试集评估、FastAPI 后端、Vue 3 前端（见下文）。

## 环境要求（本机实测配置）

- **操作系统**：Windows 11（x64）
- **Python**：3.11.9，独立运行时位于 `tools/python`（E 盘，不依赖 C 盘；由 python-build-standalone 独立包解压而来，SHA256 已验证）
- **GPU**：NVIDIA RTX 4060 Laptop 8GB，驱动 610.47（CUDA UMD 13.3）
- **PyTorch**：2.14.1+cu130 / torchvision 0.29.1+cu130（实测 `torch.cuda.is_available() == True`）
- **Node.js**：v24.21.0 LTS 位于 `tools/node`（E 盘，官方 ZIP + SHA256 校验；npm 缓存 `E:\CatDogBreedNet\.cache\npm`）
- **Git**：已安装（C:\Program Files\Git），仓库已初始化并分 6 次提交

所有缓存（pip/torch/npm）与数据均位于 E 盘：`PIP_CACHE_DIR`、`TORCH_HOME`、`npm_config_cache`
均已设置为用户级环境变量并指向 `E:\CatDogBreedNet\.cache`。

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

## 快速启动（Windows）

项目根目录提供一键启动脚本（也可分别启动）：

| 脚本 | 作用 |
|---|---|
| `启动系统.bat` | 一键检查依赖并分别在独立窗口启动后端（:8000）与前端（:5173） |
| `启动后端.bat` | 仅启动 FastAPI 后端 |
| `启动前端.bat` | 仅启动 Vite 前端（首次运行自动 `npm install`） |

**首次启动**（按顺序确认）：

1. Python 虚拟环境：`E:\CatDogBreedNet\.venv\Scripts\python.exe` 存在
   （创建：`tools\python\python.exe -m venv .venv`，然后 `pip install -r requirements.txt`）；
2. 模型文件：`artifacts\best_model.pth` 与 `artifacts\class_names.json` 存在
   （未训练时先运行 `python -m ml.train`）；
3. Node.js：PATH 中可用，或已将 Node LTS 解压到 `tools\node\`（脚本会自动查找）；
4. 双击 `启动系统.bat`。

**日常使用**：双击 `启动系统.bat` → 在后端窗口等待
`Application startup complete`（模型加载完成）→ 在前端窗口等待出现
`Local: http://127.0.0.1:5173/` → 浏览器打开 <http://127.0.0.1:5173>。

**停止程序**：分别关闭"后端"与"前端"两个命令行窗口（或在窗口中按 Ctrl+C）。

**查看错误**：两个窗口内的输出即为运行日志；后端详细请求日志同窗口显示。
端口被占用（8000/5173）、依赖缺失、GPU 不可用（可设 `CATDOG_DEVICE=cpu`）等
问题会在窗口中给出具体提示，不会静默退出。

**配置缺失处理**：前端未创建 `.env.development` 时使用代码内置默认地址
`http://127.0.0.1:8000/api`（可从 `frontend/.env.example` 复制创建）；
后端配置项见 `.env.example`（`CATDOG_*`），均有安全默认值。

> 启动脚本通过 `%~dp0` 定位项目根目录，不依赖双击时的当前目录；
> 所有路径与缓存均在 E 盘，不会写入 C 盘；脚本不会清除数据库、上传图片或模型权重。

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
| 图片识别 | `/predict` | 点击/拖拽上传、本地预览（对象 URL 及时释放）、前端预检（服务端校验为准）、Top-3 品种与分数（中文品种名，悬停显示英文原始标签）、三种耗时口径、错误提示与重试、一键清空 |
| 识别历史 | `/history` | 后端分页（10/20/50 每页）、记录 ID/图片文件名/品种/置信度/UTC 时间、详情弹窗（品种名为中文，含 Top-K 分数排名）、删除二次确认并联动删图 |
| 识别统计 | `/stats` | 总识别次数、平均推理耗时、覆盖品种数、品种分布图（中文品种名、按次数降序 Top 10、标题显示具体数量）与每日趋势图（ECharts，UTC 日期，组件卸载时销毁实例） |

顶栏实时显示模型就绪状态（`/api/health`，30 秒轮询）；后端不可用时页面显示
"无法连接后端服务"错误提示而非白屏。

**前端测试与构建**：

```powershell
cd E:\CatDogBreedNet\frontend
npm test           # Vitest：54 个用例（API 适配/错误规范化/文件预检/中文品种映射/上传组件回归/导航/统计页/历史详情/路由表，Mock 或组件挂载，不依赖真实后端）
npm run build      # 生产构建（dist/，不入 Git）
```

真实联调（2026-10-13，uvicorn:8000 + vite:5173 + 真实 Chrome 浏览器实测）：
上传 `pug_1.jpg` → Top-1 pug 100.00%（记录入库）→ 历史页可见新记录 → 详情弹窗正常 →
删除确认后列表与统计同步更新 → 刷新页面历史仍在 → 停止后端后前端显示连接错误且不白屏。

**界面修复记录（2026-10-14，真实 Chrome 浏览器复测通过）**：

| 缺陷 | 根因 | 修复 |
|---|---|---|
| 三个页面 Back 按钮点击无响应 | `el-page-header` 的 `back` 事件未绑定处理函数 | 新增 `frontend/src/utils/navigation.js`：有站内历史时 `router.back()`，直接打开 URL 时回退 `/predict`；默认识别页移除无用途的 Back 按钮 |
| 统计页两张图表空白 | `renderCharts()` 在 `loading` 仍为 `true` 时执行，图表行被 `v-if` 隐藏、ECharts 容器不存在，从未初始化 | 先解除 `loading` 再初始化；图表行不再随 loading 卸载，加载中显示占位；增加数据签名去重；标题显示具体 Top N，x 轴改中文品种名，补充合计口径说明 |
| 历史详情弹窗品种名为英文 | 模板直接渲染数据库英文标签 | 详情弹窗 `predicted_breed` 与 Top-K `breed` 经 `breedNames.js` 映射中文（未映射回退英文；数据库/API/权重不变） |
| 详情弹窗关闭按钮被页头遮挡（附带发现） | element-plus 2.14 的 `appendTo="body"` 默认**不** teleport，需显式 `append-to-body` | 历史详情弹窗增加 `append-to-body` |

导航回归测试见 `frontend/tests/navigation.test.js`、`router.test.js`、`statsView.test.js`、
`historyView.test.js`；浏览器验收截图保存于 `reports/screenshots/`（本地留存，不入 Git）。

## 测试

```powershell
# 后端（73 个用例：合成数据 + 假 Predictor + 临时 SQLite，不依赖真实推理）
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pytest tests/ -q

# 前端（54 个 Vitest 用例：API 适配/错误规范化/文件预检/中文品种映射/上传组件回归/导航/统计页/历史详情/路由表，全 Mock 或组件挂载）
cd E:\CatDogBreedNet\frontend
npm test

# 前端生产构建
npm run build

# 依赖干净重装验证（按锁文件）
npm ci
```

单元测试只使用临时合成的微型图片、假 Predictor 与临时数据库验证软件逻辑，
不作为模型实验数据。

## 系统测试与论文材料（阶段 6）

- [`reports/system_test_report.md`](reports/system_test_report.md)：功能测试报告
  （自动化 73+18、临时隔离环境 15 项真实接口用例、真实 Chrome 联调 8 项、
  统计耗时差异专项核查）；
- [`reports/thesis_materials.md`](reports/thesis_materials.md)：论文材料汇总
  （架构图/业务流程图/ER 图 `reports/diagrams/`、API 说明、界面截图
  `reports/screenshots/`、模型评估摘要、软件环境与部署说明）；
- 计时口径说明：`inference_ms` 仅模型前向、`preprocess_ms` 仅解码与变换、
  `elapsed_ms` 为服务端处理总耗时；数据库中的平均推理耗时为全部历史记录
  （含每次服务进程首次 CUDA 初始化）的平均，稳态单张约 3–6ms，两者不可互比；
- 数据保护：测试不删除既有识别记录；破坏性测试使用临时数据库
  （`CATDOG_DB_PATH`/`CATDOG_UPLOAD_DIR` 环境变量隔离）。

## 模型改进计划与 V1.1 实验（2026-10-17）

诊断与实验设计见 [`reports/model_improvement_plan.md`](reports/model_improvement_plan.md)，
数据诊断见 [`reports/model_diagnostics.md`](reports/model_diagnostics.md)，
**A2/A3/A4/A5 实验结果见 [`reports/model_experiments_report.md`](reports/model_experiments_report.md)**。

诊断要点（真实统计）：每类训练样本 84–90 张（均值 89.5，无显著类别不平衡）；
测试集 Macro-F1 0.8022，最弱品种为两种斗牛犬（0.533/0.547）与吉娃娃（0.604），
错误集中于外形近缘品种；样本量与 F1 相关系数仅 -0.182。

已执行实验的关键真实结果（`resnet18` 基线 Acc 0.8035 / Macro-F1 0.8022）：

| 实验 | 变更 | test Macro-F1 | Δ |
|---|---|---|---|
| A3b | 分层学习率 head 1e-3 / backbone 1e-4 | **0.8807** | **+0.0785** |
| A4 | EfficientNet-B0（bs 16） | 0.8673 | +0.0651（延迟 +122%，超预算） |
| A3a | 解冻 layer4，lr 5e-4 | 0.8632 | +0.0610 |
| A3c | label smoothing 0.1 | 0.8188 | +0.0166 |
| A2c | RandomErasing(0.25) | 0.8062 | +0.0040（噪声边缘） |
| A2b | ColorJitter(0.2) | 0.7953 | −0.0069 |
| A3d | 20 轮 + 早停(patience 3) | 0.5876 | −0.2146（早停过早） |
| A2d | Mixup(0.2) | 0.5988 | −0.2034（轮数不适配） |
| A4 | ConvNeXt-Tiny / ResNet50 | 0.6800 / 0.2305 | 基线配方无法迁移 |

**当前 `artifacts/best_model.pth` 仍为原始基线，未被替换**；
A3b 作为 V1.1 候选已保存于 `artifacts/exp_A3b_layered_lr/`，
替换需用户确认并先做多 seed 验证。A1（补充真实数据）与 B/U3–U5（新增类别）
因缺合规图片数据**未执行**。

### 泄漏审查与多种子配对验证（2026-10-17）

完整报告见 [`reports/seed_validation_report.md`](reports/seed_validation_report.md)。

**数据泄漏（已确认存在，官方数据集固有）**：U1 发现的 25 对跨 train/val/test
的 pHash 近重复，已逐张目视核验，**25/25 为同一照片的变体**（24 对
train/val→test、1 对 train↔val，0 例误报）。审查联系表在
`reports/leakage_review/`，判定记录在 `visual_verification.json`。

**去重划分**：`data/processed_clean/`（train 3288 / val 368 / test 3669，
官方 test 原样保留；pHash 跨划分近重复 0）。清单见
`reports/clean_split_manifest.json`。

**泄漏对指标的影响很小**：同配置下原始划分 0.8035/0.8022 vs 去重划分
0.8077/0.8055，总体仅差约 +0.004；但少数品种分数被抬高
（japanese_chin 0.9388→0.8778）。

**A3b 的多种子配对验证（去重划分，5 种子，两配置仅差学习率策略）**：

| 配置 | Accuracy | Macro-F1 | Weighted-F1 | val_acc | 延迟 |
|---|---|---|---|---|---|
| baseline | 0.8077 ± 0.0013 | 0.8055 ± 0.0014 | 0.8059 ± 0.0015 | 0.8370 ± 0.0061 | 2.286 ms |
| a3b | 0.8729 ± 0.0185 | 0.8715 ± 0.0182 | 0.8723 ± 0.0182 | 0.8973 ± 0.0068 | 2.191 ms |
| **配对差值** | **+0.0652 ± 0.0177** | **+0.0660 ± 0.0171** | +0.0663 ± 0.0172 | — | — |

**5/5 种子全部为正**，最小差值 +0.0403 约为基线种子噪声（0.0014）的 29 倍；
val_acc 与 test 排序一致，无据 test 选模迹象；逐类 36/37 提升。

**结论**：A3b 的提升稳健且无推理代价，**建议设为默认模型，但按约定未自动
替换，等待用户确认**。替换前建议先确定 A3b 的早停策略（patience 3 对 A3b
偏早，2/5 种子在第 1 轮即最佳后回落）。

## 已知限制

- **模型仅支持训练时的 37 个品种**（12 猫 + 25 狗）。边境牧羊犬（Border Collie）等
  训练类别之外的品种不在支持范围内，系统会给出一个低置信度的错误猜测——
  详见 [`reports/thesis_materials.md`](reports/thesis_materials.md) 第 9 节；
- 普通分类器不保证识别训练类别之外的动物、物体或无效图片；
- Softmax 分数是模型在当前类别集合上的归一化分数，不应宣称为真实正确概率；
- **默认模型仍为阶段 2 基线**（test Macro-F1 0.8022）。A2–A4 实验与 5 种子
  配对验证均已完成（见
  [`reports/model_experiments_report.md`](reports/model_experiments_report.md)、
  [`reports/seed_validation_report.md`](reports/seed_validation_report.md)），
  最优候选为 A3b 分层学习率（去重划分上 Macro-F1 0.8715 ± 0.0182，
  配对 5/5 全正），保存在 `artifacts/exp_A3b_layered_lr/`，
  但**尚未替换为默认模型**（需用户确认；替换前建议先定早停策略）；
- 识别页品种名显示为中文（映射见 `frontend/src/utils/breedNames.js`，未映射标签
  回退显示英文原名）；历史与统计页保持数据库原始英文标签；
- 数据集仅限研究用途，图片版权归原始网站所有。
