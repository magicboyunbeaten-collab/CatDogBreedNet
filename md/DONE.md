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

## 2026-10-13（续）

### 阶段 3：模型评估实验（已完成）
- **新增代码**：
  - `ml/evaluate.py`：`verify_class_mapping`（检查点类别名/数量与数据集映射不一致即报错，含顺序校验）、`collect_predictions`（eval 模式 + no_grad，全量单次遍历，expected_total 防残缺评估）、`compute_metrics`（Top-1、逐类 P/R/F1/Support、Macro/Weighted 三套，`zero_division=0` 并列出无预测类别）、分类报告 CSV+JSON、混淆矩阵 CSV + 计数/行归一化双 PNG（37×37 标注类名）、`benchmark_batch_inference`（预热 + CUDA 同步，批吞吐与单张延迟 mean/median/P95）、`benchmark_end_to_end`（含文件读取+PIL 解码+预处理，口径分离）、自动生成 `evaluation_summary.md`
  - `tests/test_evaluate.py` 13 个用例：手算 toy 指标校验、混淆矩阵形状/顺序/CSV、缺失类别 zero_division、产物文件有效性、eval 模式与无梯度、expected_total 防残缺、映射不匹配报错、双口径 benchmark CPU 冒烟
- **真实评估（3669 张全量）**：Accuracy **0.8035**、Macro P/R/F1 = 0.8123/0.8031/**0.8022**、Weighted P/R/F1 = 0.8127/0.8035/**0.8026**；无零预测类别；最好 keeshond F1 0.946，最弱 american_pit_bull_terrier 0.533；斗牛犬两种互混 35 次、Siamese/Birman/Ragdoll 互混 62 次
- **真实性能测试**：模型纯推理（batch 32，预热 10 + 计时 50 batch，CUDA 同步）27.01 ms/batch、1184.9 img/s、单张 2.95/2.20/4.93 ms（1600 次）；端到端（含预处理，100 张）7.18/5.78/13.65 ms、139.2 img/s；硬件与环境记录于 `inference_benchmark.json`
- **测试**：`pytest tests/` **42/42 通过**；未重新训练、未覆盖阶段 2 权重与日志、未重下数据集、权重与数据未入 Git
- **文档**：README 增加阶段 3 命令与真实结果；`reports/README.md` 补充测试集指标；`reports/evaluation_summary.md` 含易混淆品种对分析；三文件更新；git 提交完成

## 2026-10-13（续）

### 阶段 4：FastAPI 后端（已完成）
- **新增代码**：
  - `ml/predictor.py`：共享 `Predictor` 类（一次加载检查点，`predict_pil`/`predict_path`，`model.eval()` + `inference_mode` + softmax，GPU 推理锁），CLI 与后端共用
  - `ml/predict.py`：`predict_image()` 重构为复用 `Predictor`（签名与返回结构不变，进程内仍只加载一次）
  - `ml/model.py`：新增 `verify_class_mapping`（由 evaluate.py 迁入，避免后端依赖 sklearn）
  - `backend/app/`：config（CATDOG_* 环境变量，默认 E 盘路径、10MB、25M 像素、本地 CORS）、schemas（Pydantic 响应模型）、database（SQLAlchemy engine/session/get_db）、models（`PredictionRecord` 7 字段，UTC ISO 8601 时间戳）、main（`create_app` 工厂 + lifespan 一次性加载 + CORS + 全局异常处理 + /api/health）、routes/predict（流式限大小→Pillow 实校验→随机名保存→共享推理→写库→返回 record_id；DB 失败 500 并清理孤立图片）、routes/history（分页/详情/删除，删除先提交 DB 再删受控目录内图片）、routes/stats（真实记录聚合，空库返回空统计）、services/predictor（PredictorService + class_names.json 映射校验）、services/image_utils（流式读取、格式/像素/解压炸弹校验、UUID 文件名、目录包含检查）
- **测试**：`tests/test_api.py` 31 个用例（FakePredictor + 临时 SQLite + 临时上传目录，不下载权重不做真实推理）：health 正常/未就绪 503、合法预测结构与持久化、空文件/文本伪装/损坏 JPEG/BMP/超大/超高像素/ top_k 越界、推理失败与 DB 失败的孤立图片清理、历史分页与排序、详情 404、删除联动与目录外保护、统计空库与真实记录、image_utils 单元、CORS 放行/拒绝；全量 `pytest tests/` **73/73 通过**
- **真实集成测试**（uvicorn 8000，2026-10-13）：health `model_loaded=true/37 类`（启动日志证实仅加载一次）；beagle_1.jpg → beagle 0.979491（record 1）；samoyed_1.jpg → samoyed 0.998949（稳态 inference 3.644ms）；错误码实测 400/400/400/413/400；DELETE 联动删图成功；history/stats 真实入库；**CLI 与 API 同图 Top-3 逐位一致**
- **文档**：README 后端章节（API 表、三种计时口径、上传保留与重置策略、UTC 时区、配置说明）、`.env.example`、reports/README.md、三文件更新；git 提交完成
- **未新增依赖**（fastapi/uvicorn/sqlalchemy/python-multipart/httpx 阶段 1 已安装）
