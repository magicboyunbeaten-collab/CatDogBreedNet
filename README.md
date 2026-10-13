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
| 阶段 3 | 评估实验（指标/混淆矩阵） | ⬜ 未开始 |
| 阶段 4 | 后端 API（FastAPI） | ⬜ 未开始 |
| 阶段 5 | 前端（Vue 3） | ⬜ 未开始 |
| 阶段 6 | 联调、测试与文档 | ⬜ 未开始 |

**当前可用命令**：数据集下载/划分/统计、模型训练、单图预测（见下文）。后端 API 与前端尚未实现。

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
├── ml/                     # 模型与数据代码（config.py 已就绪；dataset/model/train 等属阶段 2）
├── scripts/
│   └── prepare_dataset.py  # 数据管道：download / build / stats
├── data/
│   ├── raw/                # 官方压缩包与解压文件（不入 Git）
│   └── processed/          # train/val/test/<品种>/ ImageFolder 结构（不入 Git）
├── artifacts/              # 模型产物（阶段 2 起）
├── reports/                # 数据集报告、训练指标（阶段 2 起）
├── tests/                  # pytest 单元测试（合成小图，不依赖真实数据集）
├── tools/python/           # E 盘独立 Python 3.11.9 运行时（不入 Git）
├── md/                     # 开发规范与三文件进度
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

## 测试

```powershell
E:\CatDogBreedNet\.venv\Scripts\python.exe -m pytest tests/ -q
```

测试只使用临时合成的微型图片验证软件逻辑，不作为模型实验数据。

## 已知限制

- 普通分类器不保证识别训练类别之外的动物、物体或无效图片；
- Softmax 分数是模型在当前类别集合上的归一化分数，不应宣称为真实正确概率；
- 数据集仅限研究用途，图片版权归原始网站所有。
