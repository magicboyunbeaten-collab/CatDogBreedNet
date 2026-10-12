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

### 遗留事项
- Git 未安装，`git init` 与首次提交待用户安装后执行
- C 盘残留一份安装工具部署的 Python（`C:\Users\23547\.workbuddy\binaries\python\versions\3.11.9`），已向用户报告，是否删除待用户决定
