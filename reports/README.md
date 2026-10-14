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
  临时环境（8001/8002 端口 + 临时 DB）完成；本轮测试记录（含一条来源无法追溯、
  创建于本轮测试时间窗内的意外记录，已在报告中如实记录）全部清理
- **缺陷修复**：后端不可用时历史页仅瞬期 toast → 已增加持久错误横幅与"加载失败，请重试"空态
- **耗时差异核查**：DB 均值 921.32ms 由两条首次 CUDA 初始化记录（1441.2/1316.9ms）拉高，
  稳态 2.95–5.8ms；统计接口计算正确，三种计时口径已在文档中区分
- `thesis_materials.md`：论文材料汇总（架构图/业务流程图/ER 图 + API 说明 + 界面截图索引 +
  评估摘要 + 环境部署说明）；图表 PNG 在 `diagrams/`，真实截图在 `screenshots/`（均不入 Git）

## 已知限制

- 验证精度 0.84 为基线水平；尚未做模型对比（MobileNetV3 等）与增强对比实验；
- Softmax 分数是当前类别集合上的归一化分数，不是真实概率；
- 不保证识别训练类别之外的动物或物体。
