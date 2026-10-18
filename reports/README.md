# 实验报告索引

本目录保存论文/答辩所需的真实实验材料。所有数字均来自实际运行，可追溯到
`artifacts/experiment_config.json` 与训练日志。

## 数据集

- [`dataset.md`](dataset.md)：来源、许可原文、引用、划分方案、37 类统计

## 实验 1：ResNet18 基线（2026-10-13，已完成）

| 项目 | 值 |
|---|---|
| 模型 | torchvision ResNet18，ImageNet V1 预训练权重，全模型微调 |
| 数据 | Oxford-IIIT Pet，37 类；train 3311 / val 369 / test 3669（官方 test 作测试集） |
| 超参数 | AdamW(lr=1e-3, weight_decay=1e-4)，StepLR(step=5, gamma=0.1)，CrossEntropyLoss，batch 32，10 epochs，种子 42 |
| 训练环境 | RTX 4060 Laptop 8GB，torch 2.14.1+cu130，10 epochs 共 198.8s（约 19.9s/epoch） |
| 最佳验证精度 | **0.8401**（epoch 8，按验证集选择，未使用测试集调参） |
| 最终 epoch | train_acc 0.9852 / val_acc 0.8293（epoch 10） |

逐轮指标见 `train_log.csv`（由 `.gitignore` 排除，仅本机留存），曲线见
`loss_curve.png` / `accuracy_curve.png`（同样仅本机留存）。完整超参数与环境
记录在 `artifacts/experiment_config.json`（已提交 Git）。

### 单图预测抽样（真实测试图片，Top-1 全部正确）

| 真实标签 | 预测 Top-1 | 分数 |
|---|---|---|
| Siamese | Siamese | 0.9653 |
| Bengal | Bengal | 0.8569 |
| beagle | beagle | 0.9795 |
| pug | pug | 1.0000 |
| samoyed | samoyed | 0.9989 |
| boxer | boxer | 0.9985 |

抽样方式：每个品种取测试集第一张图片，命令
`python -m ml.predict --image <图片> --top-k 3`。测试集整体指标见下一节。

## 实验 1 补充：完整测试集评估（2026-10-13，阶段 3 完成）

对 `best_model.pth` 在**完整官方 test 集 3669 张**上重新推理（每张只评估一次，
未用测试集调参）：

| 指标 | 值 |
|---|---|
| Top-1 Accuracy | 0.8035 |
| Macro Precision / Recall / **F1** | 0.8123 / 0.8031 / **0.8022** |
| Weighted Precision / Recall / **F1** | 0.8127 / 0.8035 / **0.8026** |

- 37 个类别均至少被预测过一次，`zero_division=0` 未实际生效（策略已在
  `test_metrics.json` 中说明）。
- 最好：keeshond F1 0.946、leonberger 0.945、japanese_chin 0.939；
  最弱：american_pit_bull_terrier 0.533、staffordshire_bull_terrier 0.547。
- 误判集中在近缘品种：两种斗牛犬互混 35 次；Siamese/Birman/Ragdoll 互混 62 次。

推理性能（RTX 4060，torch 2.14.1+cu130，两个口径不可互比）：

| 口径 | 内容 | 结果 |
|---|---|---|
| 模型纯推理 | batch 32，预热 10 + 计时 50 batch，CUDA 同步 | 27.01 ms/batch，1184.9 img/s；单张平均 2.95 / 中位 2.20 / P95 4.93 ms（1600 次） |
| 端到端 | 含文件读取+PIL 解码+预处理，batch 1，100 张 | 平均 7.18 / 中位 5.78 / P95 13.65 ms，139.2 img/s |

产物：`test_metrics.json`、`classification_report.csv`、`confusion_matrix.csv`、
`confusion_matrix.png`、`confusion_matrix_normalized.png`、
`inference_benchmark.json`、`evaluation_summary.md`（详见该报告）。
复现命令：`python -m ml.evaluate`。

## 阶段 4：FastAPI 后端（2026-10-13，已完成）

- 结构：`backend/app/`（main/config/schemas/database/models + routes/{predict,history,stats} + services/{predictor,image_utils}）
- 模型生命周期：`PredictorService`（包装 `ml.predictor.Predictor`，与 CLI 同一实现）在 FastAPI lifespan 中加载一次；启动日志实测 "model ready: 37 classes on cuda"；类别映射与 `class_names.json` 校验一致
- 上传安全：流式 10MB 限制（413）、JPEG/PNG/WebP 白名单 + Pillow 实解析（400）、2500 万像素上限（400）、随机 UUID 文件名、仅限 `uploads/` 目录
- 数据库：SQLite（`data/app.db`）+ SQLAlchemy ORM `prediction_records` 表（id/image_path/predicted_breed/confidence/top_k_json/inference_ms/created_at，UTC ISO 8601）；历史分页/详情/删除（删除先提交 DB 再删目录内图片）；统计全部来自真实记录
- 真实集成测试（uvicorn 8000 端口，2026-10-13）：
  - `/api/health`：`model_loaded=true, num_classes=37`；`/docs` 200
  - `POST /api/predict`（beagle_1.jpg）：Top-1 beagle 0.979491，record_id=1；稳态第二次（samoyed）inference_ms=3.644
  - 错误场景实测：空文件 400、文本伪装 400、BMP 400、>10MB 413、top_k=99 400（错误信息不含路径与堆栈）
  - `DELETE /api/history/2` 联动删除图片成功；历史与统计反映真实入库记录
  - **CLI 与 API 同图 Top-3 逐位一致**（beagle 0.979491 / basset_hound 0.005011 / miniature_pinscher 0.00496）
- 测试：`tests/test_api.py` 31 个用例（假 Predictor + 临时 SQLite + 临时目录，不下载权重）；全量 `pytest tests/` **73/73 通过**
- 未新增依赖（fastapi/uvicorn/sqlalchemy/python-multipart/httpx 阶段 1 已安装）

## 阶段 5：Vue 3 前端（2026-10-13，已完成）

- 环境：Node.js v24.21.0 LTS + npm 11.19.0（官方 ZIP 装于 `tools/node`，SHA256 已验证；
  npm 缓存 `E:\CatDogBreedNet\.cache\npm`，依赖 `frontend/node_modules`，均在 E 盘）
- 技术栈：Vue 3.5 + Vite 8 + Vue Router 4 + Element Plus 2.14 + Axios + ECharts 6（纯 JS）；
  `package-lock.json` 已提交
- 结构：`frontend/src/{api,components,views,router,utils,assets}` + `tests/`（Vitest）
- API 对接：全部字段与后端 Schema 逐字对齐；统一 Axios 实例 + 错误规范化
  （400/413/500/503/网络/超时）；`VITE_API_BASE_URL` 环境变量（默认 `http://127.0.0.1:8000/api`）
- 自动化测试：Vitest **18/18 通过**（API 适配 7、错误规范化 5、文件预检 6，全部 Mock）；
  `npm run build` 成功；后端 `pytest` **73/73 通过**（无回归）
- 真实联调（真实 Chrome 浏览器 + uvicorn:8000 + vite:5173）：
  - 上传 `pug_1.jpg` → Top-1 **pug 100.00%**（record 入库）；三种耗时口径正确展示
  - 历史页分页/详情/删除（二次确认）均正常；删除后列表与统计同步更新
  - 统计页显示真实记录（总次数 3、平均推理耗时 921.32ms、覆盖品种 2）
  - 刷新/直连 `/history` 数据持久化；CORS 实测放行 vite 源（未绕过浏览器安全机制）
  - 停止后端后：顶栏变"模型未就绪"、页面显示"无法连接后端服务"错误提示，不白屏

## 阶段 6：系统联调、全面测试与论文素材（2026-10-14，已完成）

- `system_test_report.md`：功能测试报告——后端 pytest 73/73、前端 Vitest 18/18、构建成功、
  `npm ci` 锁文件干净重装通过（锁文件未改动）；临时隔离环境 15 项真实接口用例
  （400/413/404/500/503 全部分支）；真实 Chrome 联调 8 项全部通过
- **数据保护**：正式 `data/app.db`（3 条演示记录）测试前后逐字段一致；破坏性测试全部在
  临时环境（8001/8002 端口 + 临时 DB）完成；本轮测试记录（含用户本人手动识别测试
  产生的记录）全部清理
- **缺陷修复**：后端不可用时历史页仅瞬期 toast → 已增加持久错误横幅与"加载失败，请重试"空态
- **耗时差异核查**：DB 均值 921.32ms 由两条首次 CUDA 初始化记录（1441.2/1316.9ms）拉高，
  稳态 2.95–5.8ms；统计接口计算正确，三种计时口径已在文档中区分
- `thesis_materials.md`：论文材料汇总（架构图/业务流程图/ER 图 + API 说明 + 界面截图索引 +
  评估摘要 + 环境部署说明）；图表 PNG 在 `diagrams/`，真实截图在 `screenshots/`（均不入 Git）

## 最终验收修复（2026-10-14，已完成）

- **重新上传缺陷修复**：根因——`el-upload` 的 `limit=1` 与内部文件列表在清除后未清空，
  再次选择触发 `on-exceed` 被静默阻断（已真实浏览器复现）。修复：change 处理中先安全
  取得 File，再通过 `clearFiles()` 清空内部列表并重置原生 input（同一文件可再次选择）；
  清除操作同步释放 Object URL 与全部状态；`PredictView` 一键清空联动上传组件。
  新增 8 个组件回归测试（操作序列 A–E），真实 Chrome 全序列验证无需刷新页面
- **中文品种名**：`frontend/src/utils/breedNames.js` 提供 37 类中文映射（与
  `class_names.json` 全量核对，单元测试保证），识别页 Top-1/Top-3 显示中文
  （未映射回退英文）；模型权重、API、数据库与报告保持英文标签
- **模型适用范围核查**：边境牧羊犬不属于 37 类；错误 Top-3 与低置信度（0.1633）的
  原因、两种能力区分与改进建议见 [`thesis_materials.md`](thesis_materials.md) 第 9 节
- **启动脚本**：`启动系统.bat` / `启动后端.bat` / `启动前端.bat`（`%~dp0` 定位、
  依赖检查、独立窗口、E 盘路径）；已实际执行验证成功与失败两条路径
- **记录来源修正**：阶段 6 联调中一条记录为用户本人手动识别测试产生（已在
  `system_test_report.md` 等文档如实修正）
- 回归：后端 pytest 73/73、前端 Vitest 31/31、生产构建成功

## 界面缺陷修复与模型诊断（2026-10-14，已完成，commit 8d2f313 之后新一轮）

三个 UI 缺陷均已在真实 Chrome（uvicorn:8000 + vite:5173）复现并修复，验收截图
`reports/screenshots/10_stats_fixed.png`、`11_history_detail_zh.png`（本地留存）：

1. **Back 按钮无响应**：根因为 `el-page-header` 的 `back` 事件未绑定处理函数。
   修复：新增 `frontend/src/utils/navigation.js`（有站内历史 `router.back()`；
   直接打开 URL 回退 `/predict`）；默认识别页移除无用途 Back 按钮。
   实测：/history → Back 回到 /predict；直接打开 /stats → Back 落到 /predict；
   /predict 无 Back 按钮。新增导航/路由测试 10 个。
2. **统计页两张图表空白**：根因——`renderCharts()` 在 `loading` 仍为 true 时执行，
   图表行被 `v-if="!loading"` 隐藏，ECharts 容器不存在，从未初始化。
   修复：先解除 loading 再初始化 + 加载占位 + 数据签名去重；标题显示具体
   Top N；x 轴中文品种名；补充分布/趋势合计口径说明。实测：识别后统计 64→65、
   分布合计 32→33、趋势合计 65=总数，刷新后仍为 65（来自数据库）。
   新增 StatsView 组件测试 9 个（正常/多品种/多日期/空数据/失败/口径/Back）。
3. **历史详情英文**：详情弹窗 `predicted_breed` 与 Top-K `breed` 经
   `breedNames.js` 映射中文（未映射回退英文；数据库/API/权重不变）。
   实测记录 #65：萨摩耶犬 99.89% / 荷兰毛狮犬 0.07% / 博美犬 0.02%。
   新增 HistoryView 测试 4 个。
4. **附带修复**：element-plus 2.14 的 `appendTo="body"` 默认不 teleport，
   详情弹窗渲染在页内导致关闭按钮被页头遮挡；增加 `append-to-body` 后
   关闭按钮可点击（已实测）。

CLI 与 API 同图一致性（samoyed_1.jpg）：CLI `samoyed 0.9989 / keeshond /
pomeranian`，API 萨摩耶犬 99.89% / 荷兰毛狮犬 / 博美犬——Top-3 逐位一致。

回归：后端 pytest **73/73**、前端 Vitest **54/54**、`npm run build` 成功。

## 模型改进计划与 V1.1 实验（2026-10-17）

**诊断与计划**：[`model_improvement_plan.md`](model_improvement_plan.md)（2026-10-14）

- train 3311（每类 84–90，均值 89.5）/ val 369 / test 3669，**无显著类别不平衡**；
- 测试集 Macro-F1 0.8022；最弱：两种斗牛犬 0.533/0.547、吉娃娃 0.604、
  Ragdoll 0.651；样本量与 F1 的 Pearson 相关系数仅 **-0.182**——错误主因是
  近缘品种外形相似度，而非"哪类样本少"；
- 报告区分"补充现有 37 类样本"（A1–A5 实验，含去重防泄漏规则）与
  "新增品种类别"（B 方案，如边境牧羊犬，含 38 类重训与遗忘检查）；
- 所有实验必须保留官方 test 集为唯一最终对照，禁止按测试集反复调参。

**数据诊断（U1）**：[`model_diagnostics.md`](model_diagnostics.md)

- 7349 张图片全部可正常解码，**坏图 0**；MD5 跨子集完全重复 **0** 组；
- **pHash 近重复 45 对，其中 25 对跨子集且全部同品种**（距离 0 占 39 对）——
  Oxford-IIIT 官方划分固有的视觉重复，意味着基线对相关品种可能偏乐观；
- corr(跨子集近重复数, F1) = **0.4807**：keeshond/japanese_chin/leonberger 等
  F1 前列品种恰恰存在泄漏（列为待验证假设，双口径并列，未删官方 test 图）；
- corr(每类 train 样本数, F1) = −0.182；末轮 train/val 差距 0.156（过拟合形态）；
- `split_summary.json` 为早期占位内容（3 类/27 张），与真实数据不符，已披露。

**泄漏审查与多种子验证（U1.5）**：
[`seed_validation_report.md`](seed_validation_report.md)

- **25 对跨划分近重复逐张目视核验：25/25 为同一照片变体，0 例 pHash 误报**
  （24 对 train/val→test、1 对 train↔val）——官方数据集固有的跨集合泄漏。
  联系表 `leakage_review/`，判定记录 `leakage_review/visual_verification.json`；
- 构建独立去重划分 `data/processed_clean/`（train 3288 / val 368 / test 3669，
  官方 test 原样保留，**pHash 跨划分近重复 0**），清单
  [`clean_split_manifest.json`](clean_split_manifest.json)；
- **泄漏对总体指标影响很小**：同配置下原始划分 0.8035/0.8022 vs 去重划分
  0.8077/0.8055（约 +0.004），但少数品种被抬高
  （japanese_chin 0.9388→0.8778、leonberger 0.9447→0.9231）；
- **A3b 5 种子配对验证**（去重划分，两配置仅差学习率策略）：
  baseline Macro-F1 0.8055±0.0014 → a3b **0.8715±0.0182**，
  **配对差值 +0.0660±0.0171，5/5 种子全部为正**，最小差值约为基线种子
  噪声的 29 倍；val_acc 与 test 排序一致；逐类 36/37 提升；
  A3b 无推理代价（2.191ms vs 2.286ms）；
- 附带发现：A3b 对早停敏感（2/5 种子 epoch 1 即最佳后回落，patience=3 过早），
  **+0.066 应视为稳健下界**；
- **基线权重仍未替换**，A3b 替换建议**待用户确认**；A5 的 147 个难例保留为
  人工审查任务，未改标签。

**早停策略对比（2026-10-18）**：[`earlystop_patience_report.md`](earlystop_patience_report.md)

- A3b 配置下 patience=3/5/10 三组配对实验（5 个相同种子、统一
  `max_epochs=30`，除 `--patience` 外所有训练条件逐项一致）；
  **先用验证集选型，再仅对选定配置做一次 test 评估**（流程上杜绝据 test 挑 patience）；
- 验证集（n=5）：patience=3 val Acc 0.8924±0.0063 / Macro-F1 0.8918±0.0059；
  patience=5 0.9054±0.0101 / 0.9047±0.0102；
  **patience=10 0.9092±0.0056 / 0.9081±0.0059**（均值最高、跨种子最稳、
  train/val 差距最小 0.0957）；
- 配对差值（相对 patience=3）：patience=5 仅 **4/5 为正**（seed7 −0.0027），
  **patience=10 为 +0.0168±0.0059、5/5 全正**；
- **选定 patience=10**；机制：A3b 的 head lr=1e-3 使 val_acc 第 1–2 轮即冲高回落，
  patience=3 第 4 轮即停，错过 StepLR 在 epoch 5/10/15 衰减后的提升
  （p5/p10 最佳 epoch 分别在 6–13 / 6–17）；
- 阶段二 test（仅 patience=10，n=5）：Acc **0.8851±0.0035** /
  Macro-F1 **0.8836±0.0036** / Weighted-F1 0.8844±0.0035 / 延迟 2.2968ms；
  种子间 std（0.0035）约为 A3b patience=3（0.0182）的 **1/5**；
- 相对同划分 baseline（0.8055）为 Macro-F1 **+0.0781**，延迟与基线持平；
- **建议采用 A3b + patience=10，但未自动替换默认模型，待用户确认**；
  权重在 `artifacts/exp_esp_p10_seed*/`；
- 修复 3 个被本轮暴露的缺陷（控制台编码崩溃 / `--no-benchmark` 汇总崩溃 /
  汇总键名被列表覆盖），`pytest 133/133`。

**实验结果（U2）**：[`model_experiments_report.md`](model_experiments_report.md)

- 10 个实验全部真实完成，`pytest 114/114` 通过；
- **最优：A3b 分层学习率（head 1e-3 / backbone 1e-4），test Macro-F1 0.8807（+0.0785）**，
  延迟与基线持平；其次 A3a 解冻 layer4（+0.0610）、A4 EfficientNet-B0（+0.0651 但延迟 +122%）；
- 反向结果同样重要：A3d 早停过早（−0.2146）、A2d Mixup 轮数不足（−0.2034）、
  A4 ResNet50/ConvNeXt-Tiny 证明**基线配方无法迁移到其他架构**；
- 发现运行间非确定性（同种子轨迹不同），噪声量级约 ±0.02–0.05，
  故 ±0.01 内的差异不下结论；
- **基线权重未被替换**，A3b 候选在 `artifacts/exp_A3b_layered_lr/`；
  A1（补充真实数据）与 B/U3–U5（新增类别）**未执行**（缺合规数据）。

## 已知限制

- 验证精度 0.84 为基线水平；A2–A4 实验、5 种子配对验证与早停 patience 对比
  均已完成，最优候选为 **A3b + patience=10**（去重划分上 test Macro-F1
  0.8836±0.0036），但**尚未替换为默认模型**（需用户确认）；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物或物体。
