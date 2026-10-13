# DONE 已完成事项

## 2026-10-12

### 阶段 0：仓库检查与计划（已完成）
- 通读 `md/CODEBUDDY.md`（方案 B：单模型多品种分类，37 类）
- 仓库检查结论：仓库仅含 md/ 规范文档；Python/Git/Node 均未安装；硬件 RTX 4060 8GB、驱动 610.47
- 用户确认决策：Python/Node 由工具安装且不得位于 C 盘；阶段 1 下载官方 Oxford-IIIT Pet Dataset；安装 CUDA 12.x 版 PyTorch
- 产出 7 步实施计划并获用户批准

### 阶段 1：环境与数据管道（已完成）
- **Python 环境**：
  - 安装工具将 Python 3.11.9 装在 C 盘（`C:\Users\23547\.workbuddy\binaries\...`），违反用户约束，已按其回退方案改为：从 npmmirror 下载 python-build-standalone 独立包（SHA256 `368474c6...` 验证通过），解压至 `E:\CatDogBreedNet\tools\python`
  - 用户级环境变量 `PIP_CACHE_DIR`、`TORCH_HOME` 指向 E 盘 `.cache`
  - `.venv` 创建；安装 torch 2.14.1+cu130、torchvision 0.29.1+cu130 及 requirements.txt 全部依赖
  - 实测 `torch.cuda.is_available() == True`，设备 RTX 4060 Laptop GPU
- **数据管道**（`scripts/prepare_dataset.py`，download/build/stats 三子命令）：
  - 下载官方 images.tar.gz（791,918,971 B）与 annotations.tar.gz（19,173,078 B），大小与服务器 Content-Length 完全一致；官网不公布 MD5，已记录计算值并说明校验依据
  - 解析官方标注（list.txt 含 # 注释头；trainval/test 为四列格式），按"官方 test 作测试集 + trainval 分层 90/10（种子 42）"构建 ImageFolder
  - 结果：train 3311 / val 369 / test 3669，37 类
  - 断言全部通过：class_to_idx 三集一致、图片 ID 无跨集重复、图片内容 MD5 无跨集重复
  - 相同种子重建 train 划分逐项一致（可复现实测）
- **测试**：`tests/test_prepare_dataset.py` 9/9 通过（合成小图，不依赖真实数据集）
- **文档**：README.md（环境安装/数据命令/进度/限制）、reports/dataset.md（来源/许可原文/引用/划分/37 类统计）
- **三文件**：TODO/PROGRESS/DONE 持续更新

### 遗留事项（已处理）
- Git：用户已手动安装（C:\Program Files\Git 2.55.0），完成 `git init` 与首次提交（commit 171688d，14 个文件，已验证）；调用 git 需用全路径（shell PATH 未刷新）
- C 盘 Python 残留（126.4MB）：已于 2026-10-13 经用户批准删除，E 盘副本与 .venv 不受影响

## 2026-10-13

### 阶段 2：模型基线（已完成）
- **新增代码**：
  - `ml/dataset.py`：ImageFolder + transforms（训练用 RandomResizedCrop/水平翻转/轻旋转，评估用 Resize256+CenterCrop224，统一 ImageNet 归一化），三集 class_to_idx 一致性断言，num_workers=0 默认
  - `ml/model.py`：build_model（ResNet18 IMAGENET1K_V1 预训练 + fc 换 37 类，权重下载失败明确报错不静默退化）、set_seed、save/load_checkpoint（架构记录 + 类数校验 + 严格 state_dict）、resolve_device
  - `ml/train.py`：CLI 可配置 epochs/batch/lr/设备/种子等；AdamW + StepLR + CrossEntropyLoss；按 val_acc 存最佳权重；CSV 日志 + 损失/准确率曲线 + experiment_config.json；CUDA OOM 给出调整建议
  - `ml/predict.py`：单图 Top-K 预测（默认 Top-3），inference_mode + softmax，输出品种名/分数/耗时；权重缺失、图片解码失败、top_k 越界均明确报错
- **测试**：新增 `tests/test_model_predict.py` 20 个用例（合成图片 + 轻量玩具模型，不下载预训练权重、不依赖真实数据集）；`pytest tests/` **29/29 通过**
- **训练（真实运行）**：
  - 冒烟：1 epoch，val_acc 0.2520
  - 完整：10 epochs 共 198.8s（约 19.9s/epoch，RTX 4060 8GB），最佳 **val_acc 0.8401（epoch 8）**，末轮 train_acc 0.9852 / val_acc 0.8293
  - 预训练权重缓存在 E:\.cache\torch（验证 C 盘无缓存）
- **预测（真实运行）**：6 个品种（Siamese/Bengal/beagle/pug/samoyed/boxer）测试图片 Top-1 全部正确，分数 0.8569–1.0000
- **文档**：README 增加阶段 2 命令与产物说明；新增 `reports/README.md` 实验摘要（真实数字）；`.gitignore` 增加 reports/*.log；三文件更新；git 提交完成
