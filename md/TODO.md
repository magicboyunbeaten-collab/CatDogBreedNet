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

## 阶段 6：联调、测试与文档 [已完成]
- [x] npm 依赖完整性：`npm ls` 正常、`npm ci` 锁文件干净重装通过（锁文件未改动）、重跑 build+Vitest
- [x] 临时隔离环境 E2E 15 项（8001/8002 端口，含 400/413/404/500/503）
- [x] 正式环境真实 Chrome 联调 8 项；测试前后正式 DB 逐字段一致（3 条演示记录零损坏）
- [x] 缺陷修复：历史页后端不可用时增加持久错误提示
- [x] `reports/system_test_report.md` 功能测试报告
- [x] `reports/thesis_materials.md` + 架构/流程/ER 三张图 + 4 张真实截图
- [x] 统计耗时差异核查结论写入报告（冷启动记录拉高均值，稳态 3–6ms）
- [x] 全量回归：pytest 73/73、Vitest 18/18、build 成功；Git diff 与忽略规则核对；独立提交

## 全部阶段完成 ✅
- 阶段 0-6 均已完成并提交；项目达到 CODEBUDDY.md 定义的交付状态

## 最终验收修复（2026-10-14，已完成）
- [x] 修复重新上传缺陷（根因：el-upload limit/内部列表未清空 + 原生 input 未重置 + 一键清空不联动）；真实浏览器复现→修复→A-E 全序列回归通过
- [x] 新增 8 个上传组件回归测试 + 5 个中文映射测试（Vitest 31/31）
- [x] 新增 `启动系统.bat`/`启动后端.bat`/`启动前端.bat` 并实测成功与失败路径
- [x] 识别页 Top-1/Top-3 中文品种名（37 类映射与 class_names.json 全量核对，英文回退）
- [x] 边境牧羊犬范围核查与模型改进建议（thesis_materials.md 第 9 节；不属 37 类）
- [x] 修正测试报告中记录来源描述（用户手动测试产生）
- [x] 回归：pytest 73/73、Vitest 31/31、build 成功；独立提交

## 界面缺陷修复与模型诊断（2026-10-14，已完成）
- [x] Back 按钮无响应：新增 `frontend/src/utils/navigation.js`（站内历史 router.back() / 无历史回退 /predict）；默认识别页移除死按钮；新增 navigation + router 测试 10 个；真实 Chrome 三页面导航验证
- [x] 统计页两张图表空白：根因 loading 期间 renderCharts 时图表行 v-if 隐藏、ECharts 从未初始化；修复渲染时机 + 加载占位 + 签名去重；标题具体 Top N；x 轴中文品种名；合计口径说明；新增 StatsView 测试 9 个（正常/多品种/多日期/空数据/失败/口径/Back）
- [x] 历史详情中文：`predicted_breed` 与 Top-K `breed` 走 breedNames.js（未映射回退英文；DB/API/权重不变）；新增 HistoryView 测试 4 个；真实浏览器验证记录 #65（萨摩耶犬/荷兰毛狮犬/博美犬）
- [x] 附带修复：element-plus 2.14 appendTo 默认不 teleport 导致详情弹窗关闭按钮被页头遮挡 → `append-to-body`，实测可点击
- [x] 模型诊断：`reports/model_improvement_plan.md`（每类 84-90 张、corr(样本数,F1)=-0.182、最弱斗牛犬/吉娃娃/长毛猫；37 类改进实验 A1-A5 与新类别扩充 B 方案；防泄漏规则）——未重新训练、未覆盖权重
- [x] 真实联调：识别 samoyed_1.jpg → 记录 #65 入库；统计 64→65、分布合计 32→33、趋势合计 65=总数；刷新后持久化；CLI 与 API 同图 Top-3 逐位一致
- [x] 回归：pytest 73/73、Vitest 54/54、build 成功；README/reports/README.md/三文件更新；独立提交

## 模型升级 U1-U2（2026-10-17，已完成）
依据 `md/MODEL_UPGRADE_PLAN (1).md` 推进。

### U1 模型诊断（已完成）
- [x] 新增 `scripts/diagnose_dataset.py`（只读）+ `tests/test_diagnose_dataset.py` 14 个用例
- [x] 逐品种 train/val/test 样本数重新扫描；三个子集标签映射一致（37 类）
- [x] 坏图扫描 7349 张全部可解码（0 坏图）
- [x] MD5 跨子集完全重复 0 组；**pHash 近重复 45 对，其中 25 对跨子集且全部同品种**（距离 0 占 39 对）
- [x] corr(每类 train 样本数, F1) = -0.182；**corr(跨子集近重复数, F1) = 0.4807**（泄漏或抬高相关品种测试分，列为待验证）
- [x] 训练曲线复核：最佳 epoch 8 / val 0.8401；末轮 train/val 差距 0.156（过拟合形态）
- [x] 披露 `reports/split_summary.json` 为早期占位内容（3 类/27 张），与真实数据不符
- [x] 产出 `reports/model_diagnostics.md` + `reports/diagnostics_details.json`；独立提交

### U2 V1.1 训练管线扩展（已完成）
- [x] `ml/model.py`：SUPPORTED_ARCHS（resnet18/resnet50/convnext_tiny/efficientnet_b0），build_model(arch,...) 与 _default_factory 支持新架构
- [x] `ml/dataset.py`：build_transforms 增加 baseline/+colorjitter/+randomerasing 预设；评估管线恒定确定性
- [x] `ml/train.py`：新增 --arch/--augment/--freeze-strategy/--lr-head/--lr-backbone/--label-smoothing/--mixup-alpha；分层 LR 优化器；Mixup 软标签；experiment_config.json 完整记录
- [x] 默认参数与基线逐项一致（已用默认参数冒烟核对 experiment_config.json）
- [x] 修复缺陷：save_checkpoint 未传 arch 导致非 resnet18 权重被误标（A4_resnet50 评估失败根因）；新增 3 个回归测试
- [x] 新增 `scripts/run_improvement_experiments.py`（矩阵 + 断点续跑 + --skip-train）
- [x] `tests/test_train_extensions.py` 27 个用例；pytest **114/114** 全过

### U2 A2-A5 实验（已完成，真实结果）
- [x] A2 增强对照：ColorJitter -0.0069（无提升）、RandomErasing +0.0040（噪声边缘）、Mixup -0.2034（10 轮不适配）
- [x] A3 微调对照：**A3b 分层学习率 +0.0785（val 0.8970 / test 0.8807）**、A3a 解冻 layer4 +0.0610、A3c label smoothing +0.0166、A3d 20 轮+早停 -0.2146（早停过早）
- [x] A4 backbone 对比：EfficientNet-B0 +0.0651 但延迟 +122% 超预算；ConvNeXt-Tiny -0.1222；ResNet50 -0.5717（欠训练，非容量结论）
- [x] A5 难例分析：8 个混淆对抽样 147 个，**无一在 train/val 存在近重复**（误分类与泄漏无关）；图片复制到 `.cache/A5_review/`
- [x] 发现运行间非确定性（同种子轨迹不同，噪声约 ±0.02-0.05），已写入报告作为解读边界
- [x] 产出 `reports/model_experiments_report.md`、`reports/A5_hard_examples.{md,json}`、`reports/exp_results/`
- [x] **基线 `artifacts/best_model.pth` 未被替换**；A3b 候选保存在 `artifacts/exp_A3b_layered_lr/`

## 后续可选（未开始，需用户确认）
- [ ] **A3b 替换基线权重**：需用户确认 + 多 seed（3-5 个）验证稳健性
- [ ] 组合实验：A3b + RandomErasing / + label smoothing 是否叠加
- [ ] EfficientNet-B0 单独调参后在延迟预算内与 ResNet18 公平比较
- [ ] Mixup 延长到 50+ 轮再评估；A2c 多 seed 确认
- [ ] A1 补充真实数据（需许可合规图片 + pHash 去重报告）
- [ ] U3 V2 数据审查（Stanford Dogs 等，需下载与许可审查）
- [ ] U4 V2 训练与评估、U5 可切换版本集成、未知品种拒识
