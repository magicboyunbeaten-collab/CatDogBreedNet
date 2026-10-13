# TODO 待办事项

> 三文件模式：TODO.md 记录待办，PROGRESS.md 记录当前进度，DONE.md 记录已完成。

## 阶段 0：仓库检查与计划 [已完成]
- [x] 通读 `md/CODEBUDDY.md` 开发规范
- [x] 检查仓库结构、Python/Node/Git 环境、硬件（RTX 4060 8GB）
- [x] 与用户确认三项决策：工具安装 Python/Node（非 C 盘）、阶段 1 下载 Oxford-IIIT Pet、CUDA 版 PyTorch
- [x] 制定阶段 0 检查结论与阶段 1 实施计划并获用户确认

## 阶段 1：环境与数据管道 [已完成]
- [x] E 盘部署 Python 3.11.9（`tools/python`，SHA256 验证；安装工具默认落在 C 盘，已按回退方案改到 E 盘）
- [x] 缓存环境变量指向 E 盘（PIP_CACHE_DIR / TORCH_HOME）
- [x] 创建项目骨架：目录、`.gitignore`、`requirements.txt`、`ml/config.py`
- [x] `.venv` 安装 CUDA 版 PyTorch 2.14.1+cu130，验证 `torch.cuda.is_available() == True`
- [x] 下载 Oxford-IIIT Pet Dataset（792MB+19MB），大小与服务器 Content-Length 一致
- [x] 构建 ImageFolder 划分 train 3311 / val 369 / test 3669（种子 42，可复现）
- [x] class_to_idx 一致性、ID/内容 MD5 泄漏检查通过
- [x] `reports/dataset.md` 记录来源、许可、引用、划分、类别统计
- [x] 单元测试 9/9 通过；README 完成
- [x] Git 初始化与首次提交（用户手动安装 Git 后完成，commit 171688d）

## 阶段 2：模型基线 [已完成]
- [x] 删除 C 盘 Python 残留（126.4MB，已获用户批准）
- [x] `ml/dataset.py`：ImageFolder + transforms + 类别映射一致性检查
- [x] `ml/model.py`：ResNet18 预训练 + fc 换 37 类 + 检查点保存/加载校验
- [x] `ml/train.py`：AdamW + 调度器 + 验证集选最佳 + 日志/曲线/实验配置
- [x] `ml/predict.py`：单图 Top-3 预测
- [x] 新增 `tests/test_model_predict.py`
- [x] 冒烟训练 1 epoch → 完整训练 10 epochs（val_acc 0.8401）→ 真实图片预测 6/6 正确
- [x] 更新 README 与三文件，git 提交（950423c）

## 阶段 3：评估实验 [已完成]
- [x] `ml/evaluate.py`：完整 test 集（3669 张）评估，Accuracy/逐类 P/R/F1/Macro/Weighted、混淆矩阵 CSV+双 PNG
- [x] 推理耗时双口径测量（预热 + CUDA 同步；模型纯推理与端到端分开）
- [x] 新增 `tests/test_evaluate.py`
- [x] 真实结果：Accuracy 0.8035 / Macro-F1 0.8022 / Weighted-F1 0.8026
- [x] `reports/evaluation_summary.md` 等 7 个产物生成并核对
- [x] 文档更新与 git 提交（17d688b）

## 阶段 4：后端 [已完成]
- [x] `backend/app/` 全套模块：lifespan 一次性加载模型的 PredictorService、上传安全校验、SQLite+SQLAlchemy 历史与统计
- [x] `ml/predictor.py` 共享 Predictor 类，CLI 与后端复用同一实现
- [x] API：`GET /api/health`、`POST /api/predict`、`GET /api/history`、`GET /api/history/{id}`、`DELETE /api/history/{id}`、`GET /api/stats`
- [x] 新增 `tests/test_api.py` 31 个用例；全量 `pytest tests/` 73/73 通过
- [x] 真实集成测试：health/docs/真实预测/历史/统计/错误场景全部实测；CLI 与 API 同图 Top-3 逐位一致
- [x] `.env.example`、README、reports/README.md、三文件更新；git 提交完成

## 阶段 5：前端 [已完成]
- [x] E 盘安装 Node.js v24.21.0 LTS（官方 ZIP，SHA256 校验；npm 缓存指向 E 盘）
- [x] `frontend/`：Vue 3 + Vite + Vue Router + Element Plus + Axios + ECharts（纯 JS）
- [x] API 层按后端真实 Schema 对接 + 统一错误规范化；`package-lock.json` 提交
- [x] 识别/历史/统计三页 + 上传组件 + 结果组件
- [x] Vitest 18/18 通过；`npm run build` 成功；后端 pytest 73/73 无回归
- [x] 真实联调（真实 Chrome）：识别/历史/删除/统计/刷新持久化/CORS/后端降级全部实测
- [x] README、reports/README.md、三文件更新；git 提交完成

## 阶段 6：联调、测试与文档 [未开始]
- [ ] 全流程手工测试表、论文素材（界面截图/功能测试表）、README 终稿

## 阶段 6：联调、测试与文档 [未开始]
- [ ] 自动化测试与手工测试、README 与论文素材完善
