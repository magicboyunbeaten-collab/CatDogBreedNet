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
- [ ] Git 初始化与首次提交（等待用户安装 Git）

## 阶段 2：模型基线 [未开始]
- [ ] `ml/dataset.py`、`ml/model.py`、`ml/train.py`：ResNet18 迁移学习
- [ ] 训练并保存 `artifacts/best_model.pth`、`class_names.json`、`experiment_config.json`
- [ ] 训练曲线与日志；单图预测脚本 `ml/predict.py`

## 阶段 3：评估实验 [未开始]
- [ ] `ml/evaluate.py`：测试集指标、分类报告、混淆矩阵

## 阶段 4：后端 [未开始]
- [ ] FastAPI：健康检查、预测 API、文件校验、SQLite 历史与统计

## 阶段 5：前端 [未开始]
- [ ] Vue 3 + Vite + Element Plus：上传识别页、历史页、统计页（Node 需按非 C 盘规则安装）

## 阶段 6：联调、测试与文档 [未开始]
- [ ] 自动化测试与手工测试、README 与论文素材完善
