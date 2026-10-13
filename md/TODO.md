# TODO 待办事项

> 三文件模式：TODO.md 记录待办，PROGRESS.md 记录当前进度，DONE.md 记录已完成。

## 阶段 0：仓库检查与计划 [已完成]
- [x] 通读 `md/CODEBUDDY.md` 开发规范
- [x] 检查仓库结构、Python/Node/Git 环境、硬件（RTX 4060 8GB）
- [x] 与用户确认三项决策：工具安装 Python/Node（非 C 盘）、阶段 1 下载 Oxford-IIIT Pet、CUDA 版 PyTorch
- [x] 制定阶段 0 检查结论与阶段 1 实施计划并获用户确认

## 阶段 1：环境与数据管道 [已完成]
- [x] E 盘部署 Python 3.11.9（`tools/python`，SHA256 验证；安装工具默认落在 C 盘，已按其回退方案改到 E 盘）
- [x] 缓存环境变量指向 E 盘（PIP_CACHE_DIR / TORCH_HOME）
- [x] 创建项目骨架：目录、`.gitignore`、`requirements.txt`、`ml/config.py`
- [x] `.venv` 安装 CUDA 版 PyTorch 2.14.1+cu130，验证 `torch.cuda.is_available() == True`
- [x] 下载 Oxford-IIIT Pet Dataset（792MB+19MB），大小与服务器 Content-Length 一致
- [x] 构建 ImageFolder 划分 train 3311 / val 369 / test 3669（种子 42，可复现）
- [x] class_to_idx 一致性、ID/内容 MD5 泄漏检查通过
- [x] `reports/dataset.md` 记录来源、许可、引用、划分、类别统计
- [x] 单元测试 9/9 通过；README 完成
- [ ] Git 初始化与首次提交（等待用户安装 Git）→ 用户已于 2026-10-13 前完成（commit 171688d，14 个文件，已验证）

## 阶段 2：模型基线 [已完成]
- [x] 删除 C 盘 Python 残留（126.4MB，已获用户批准）
- [x] `ml/dataset.py`：ImageFolder + transforms + 类别映射一致性检查
- [x] `ml/model.py`：ResNet18 预训练 + fc 换 37 类 + 检查点保存/加载校验
- [x] `ml/train.py`：AdamW + 调度器 + 验证集选最佳 + 日志/曲线/实验配置
- [x] `ml/predict.py`：单图 Top-3 预测
- [x] 新增 `tests/test_model_predict.py`（29/29 通过）
- [x] 冒烟训练 1 epoch → 完整训练 10 epochs（val_acc 0.8401）→ 真实图片预测 6/6 正确
- [x] 更新 README 与三文件，git 提交

## 阶段 3：评估实验 [已完成]
- [x] `ml/evaluate.py`：完整 test 集（3669 张）评估，Accuracy/逐类 P/R/F1/Macro/Weighted、混淆矩阵 CSV+双 PNG
- [x] 推理耗时双口径测量（预热 + CUDA 同步；模型纯推理与端到端分开）
- [x] 新增 `tests/test_evaluate.py`（pytest 42/42 通过）
- [x] 真实结果：Accuracy 0.8035 / Macro-F1 0.8022 / Weighted-F1 0.8026
- [x] `reports/evaluation_summary.md` 等 7 个产物生成并核对
- [x] 文档更新与 git 提交

## 阶段 4：后端 [未开始]
- [ ] FastAPI：健康检查、预测 API、文件校验、SQLite 历史与统计

## 阶段 3：评估实验 [未开始]
- [ ] `ml/evaluate.py`：测试集指标、分类报告、混淆矩阵

## 阶段 4：后端 [未开始]
- [ ] FastAPI：健康检查、预测 API、文件校验、SQLite 历史与统计

## 阶段 5：前端 [未开始]
- [ ] Vue 3 + Vite + Element Plus：上传识别页、历史页、统计页（Node 需按非 C 盘规则安装）

## 阶段 6：联调、测试与文档 [未开始]
- [ ] 自动化测试与手工测试、README 与论文素材完善
