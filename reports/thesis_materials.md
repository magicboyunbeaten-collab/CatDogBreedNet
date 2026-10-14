# 毕业论文材料汇总

> 本文件汇总毕业设计所需的系统材料。所有指标与截图均来自真实运行（2026-10-13 / 10-14），
> 可追溯到 `artifacts/experiment_config.json`、`reports/test_metrics.json` 与训练日志。
>
> 说明：`diagrams/`（架构/流程/ER 图）与 `screenshots/`（界面截图）为二进制产物，
> 按仓库约定（与训练曲线、混淆矩阵等生成产物一致）不入 Git，仅本机留存；
> 论文定稿时可将这两个目录一并打包。

## 1. 课题与系统边界

- 题目：基于深度学习的猫狗品种分类识别系统的设计与实现
- 方案：单模型多类别品种分类（方案 B）——一个多类别分类器直接预测 37 个具体猫狗品种，
  不是 Cat/Dog 二分类
- 数据集：Oxford-IIIT Pet Dataset（37 类 = 12 猫品种 + 25 狗品种，7349 张；仅限研究用途，
  详见 [`dataset.md`](dataset.md)）
- 已实现：数据管道、ResNet18 基线训练、独立测试集评估、FastAPI 后端、Vue 3 前端
- 未实现（论文中不得写成已完成）：登录/权限、云部署、模型对比实验（MobileNetV3 等）、
  生产级并发压测

## 2. 系统总体架构图

![系统总体架构图](diagrams/architecture.png)

分层说明：

| 层 | 组成 | 职责 |
|---|---|---|
| 前端展示层 | Vue 3 + Vite + Vue Router + Element Plus + ECharts | 上传识别、历史查询、统计可视化 |
| 后端服务层 | FastAPI + Uvicorn | REST API、CORS、异常处理 |
| 服务层 | `services/predictor.py` + `services/image_utils.py` | 共享推理服务、上传安全校验 |
| 模型/存储层 | ResNet18 权重 + SQLite | 模型文件与识别记录持久化 |

## 3. 图片识别业务流程图

![图片识别业务流程图](diagrams/predict_flow.png)

关键路径：上传 → 流式大小校验（413）→ Pillow 实解析 + 格式/像素校验（400）→
随机文件名保存 → 预处理 + ResNet18 推理（`model.eval()` + `inference_mode`）→
Softmax Top-3 → 写入 SQLite → 返回 `record_id` 与预测结果。权重加载失败时
`/api/predict` 返回 503，不返回伪造结果。

## 4. 数据库 ER 图

![数据库 ER 图](diagrams/er_diagram.png)

`prediction_records` 表 7 个字段：`id`（主键）、`image_path`、`predicted_breed`、
`confidence`、`top_k_json`、`inference_ms`、`created_at`（UTC ISO 8601）。
MVP 不包含用户表；时间戳统一为 UTC 并在接口文档中说明。

## 5. API 接口说明

Base URL：`http://127.0.0.1:8000/api`（前端经 `VITE_API_BASE_URL` 配置）。
交互式文档：`/docs`（Swagger UI，由 FastAPI 自动生成）。

| 方法 | 路径 | 请求 | 成功响应 | 错误响应 |
|---|---|---|---|---|
| GET | `/api/health` | — | `{status, model_loaded, num_classes, model_error, version, time}` | — |
| POST | `/api/predict` | multipart/form-data：`file`（图片）、`top_k`（可选，默认 3） | `{success, record_id, predictions:[{breed, confidence}], elapsed_ms, inference_ms, preprocess_ms, top_k, num_classes, note}` | 400 空文件/格式/像素/参数越界；413 超过 10MB；500 推理或入库失败；503 模型未就绪 |
| GET | `/api/history` | query：`page`（默认 1）、`page_size`（默认 20，≤100） | `{success, total, page, page_size, items:[...]}` | 500 查询异常 |
| GET | `/api/history/{id}` | path：记录 ID | `{success, item}` | 404 记录不存在 |
| DELETE | `/api/history/{id}` | path：记录 ID | `{success, deleted_id, image_deleted}` | 404 记录不存在；500 删除异常 |
| GET | `/api/stats` | — | `{success, total_predictions, breed_distribution:[{breed,count}], daily_trend:[{date,count}], avg_inference_ms}` | 500 查询异常 |

错误响应统一为 `{success: false, error: "..."}`，不返回绝对路径与堆栈。
计时口径：`inference_ms` 仅模型前向；`preprocess_ms` 仅图片解码与变换；
`elapsed_ms` 为服务端处理总耗时（上传校验 + 预处理 + 推理），三者不可互比。
`confidence` 为 Softmax 在训练类别集合上的归一化分数，不是真实正确概率。

## 6. 主要系统界面截图（真实运行页面）

截图来自 2026-10-14 真实 Chrome 浏览器联调（uvicorn:8000 + vite:5173）：

| 截图 | 内容 |
|---|---|
| [`screenshots/01_predict_page.png`](screenshots/01_predict_page.png) | 图片识别页（上传前） |
| [`screenshots/02_predict_result.png`](screenshots/02_predict_result.png) | 识别结果（Bengal，Top-3 + 三种耗时） |
| [`screenshots/03_history_page.png`](screenshots/03_history_page.png) | 识别历史页（分页列表） |
| [`screenshots/04_stats_page.png`](screenshots/04_stats_page.png) | 识别统计页（品种分布 + 每日趋势） |

## 7. 模型评估结果与实验摘要

完整报告见 [`evaluation_summary.md`](evaluation_summary.md)。核心指标
（ResNet18 基线，官方 test 划分 3669 张，未参与调参）：

| 指标 | 值 |
|---|---|
| 类别数 | 37 |
| 测试集样本数 | 3669 |
| Top-1 Accuracy | 0.8035 |
| Macro-F1 | 0.8022 |
| Weighted-F1 | 0.8026 |
| 最佳验证精度（阶段 2，用于选模） | 0.8401（epoch 8） |

训练配置：AdamW(lr=1e-3, weight_decay=1e-4) + StepLR(step=5, γ=0.1) +
CrossEntropyLoss，batch 32，10 epochs，全模型微调，种子 42。
易混淆品种：两种斗牛犬互混 35 次；Siamese/Birman/Ragdoll 互混 62 次。

## 8. 软件环境与部署说明

| 组件 | 版本 / 路径 |
|---|---|
| 操作系统 | Windows 11 x64 |
| Python | 3.11.9（`tools/python`，E 盘独立运行时） |
| 深度学习框架 | PyTorch 2.14.1+cu130 / torchvision 0.29.1+cu130 |
| GPU | NVIDIA RTX 4060 Laptop 8GB（驱动 610.47） |
| 后端 | FastAPI 0.143.0 + Uvicorn 0.54.0 + SQLAlchemy 2.1.4 + SQLite |
| 前端 | Node.js v24.21.0 LTS（`tools/node`）+ Vue 3.5.44 + Vite 8.3.4 + Element Plus 2.14.7 + ECharts 6.1.0 |
| 测试 | pytest 73 项（后端）+ Vitest 18 项（前端）+ 真实浏览器联调 |

部署/复现步骤（新环境）：

1. 准备 Python 3.11.9 虚拟环境（或使用 `tools/python`），`pip install -r requirements.txt`，
   GPU 机器按 README 安装 CUDA 版 PyTorch；
2. 准备模型文件 `artifacts/best_model.pth` 与 `artifacts/class_names.json`
   （由 `python -m ml.train` 训练产生；Git 不提交权重）；
3. 启动后端：`python -m uvicorn backend.app.main:app --port 8000`；
4. 安装 Node.js LTS，进入 `frontend/` 执行 `npm install` 与 `npm run dev`；
5. 访问 <http://127.0.0.1:5173>，先后端后前端即可完整使用。

配置均通过环境变量覆盖（后端 `CATDOG_*`，见 `.env.example`；前端 `VITE_API_BASE_URL`，
见 `frontend/.env.example`），默认值面向本地开发，不依赖任何绝对路径。

## 9. 模型适用范围核查：边境牧羊犬（Border Collie）案例分析

### 9.1 类别范围核对结论（2026-10-14 实测）

对 `artifacts/class_names.json` 逐项核对：当前模型的 37 个类别为
12 个猫品种 + 25 个狗品种（阿比西尼亚猫、孟加拉猫、伯曼猫、孟买猫、英国短毛猫、
埃及猫、缅因猫、波斯猫、布偶猫、俄罗斯蓝猫、暹罗猫、斯芬克斯猫；美国斗牛犬、
美国比特斗牛梗、巴吉度猎犬、比格犬、拳师犬、吉娃娃、英国可卡犬、英国塞特犬、
德国短毛指示犬、大白熊犬、哈瓦那犬、日本狆、荷兰毛狮犬、莱昂贝格犬、迷你杜宾、
纽芬兰犬、博美犬、巴哥犬、圣伯纳犬、萨摩耶犬、苏格兰梗、柴犬、斯塔福郡斗牛梗、
软毛麦色梗、约克夏梗）。

**边境牧羊犬（Border Collie）不属于上述 37 个类别。** 用户上传边牧图片时，
模型只能在既有 37 类中给出一个"最接近"的答案——阶段 6 真实记录显示输出为
havanese（哈瓦那犬）且置信度仅 0.1633，即模型自身也"不确定"。
这是训练类别之外（out-of-distribution）输入的正常表现，不是模型缺陷，
也不构成"模型支持边牧"的证据。

### 9.2 两种能力必须区分

| 能力 | 含义 | 当前状态 |
|---|---|---|
| 37 类内分类性能 | 对训练时包含的 37 个品种的分类准确率 | 已测量：测试集 Accuracy 0.8035 / Macro-F1 0.8022（见 §7） |
| 类别外识别/拒识 | 对训练类别之外品种（如边牧）的正确处理 | **不具备**：Softmax 强制在 37 类上归一化，必然输出其中一个类别 |

普通分类器不保证识别训练类别之外的动物、物体或无效图片；低置信度分数
（如 0.16）可作为"不在训练范围内"的弱信号，但不能作为可靠的拒识依据。

### 9.3 模型改进建议（按需要选择，均需重新实验验证）

1. **若维持 37 类**：补充泛化能力分析——在同一测试集上做分层错误分析
   （近缘品种互混矩阵，见 `evaluation_summary.md`）、遮挡/尺度/光照鲁棒性抽查、
   置信度校准分析（如 ECE）；这些分析不改变模型，只用于论文讨论。
2. **若要支持边境牧羊犬**（会影响现有基线，需明确立项后执行）：
   - 扩充数据集：从许可合适的来源采集边牧图片（建议每类 ≥100 张，与现有类别规模相当）；
   - 重新划分：将边牧并入 38 类后按既有策略重划 train/val/test（官方 test 保持不变或
     统一重划并如实记录），保持三集无泄漏、类别映射一致；
   - 重新训练与验证：以阶段 2 流程重训基线，按验证集选模，禁止按测试集调参；
   - 独立测试：在未参与任何调参的测试集上报告 38 类指标，与 37 类结果并列对比；
   - 同步更新 `class_names.json`、前端中文映射（新增"边境牧羊犬"）与本文档。
3. **未知类别拒识机制（可选，且有局限）**：可增加"背景/其他"类别或基于置信度阈值
   的拒识分支。局限：阈值需要额外验证集标定；低置信度也可能来自域内难样本，
   拒识会牺牲部分域内准确率；不能宣称"能识别所有猫狗品种"。

> 约束：在未制定并确认扩充类别方案前，不覆盖 `best_model.pth`、不改动 37 类映射、
> 不修改阶段 3 测试指标；不得为单张边牧图片硬编码答案或针对性过拟合。

## 10. 已知限制（论文中需如实说明）

- 基线模型测试集 Accuracy 0.8035，尚未做模型对比与数据增强对比实验；
- Softmax 分数不是真实概率；不保证识别训练类别之外的动物、物体或无效图片；
- 未做登录/权限、云部署与生产级并发压测；单卡 GPU 推理已加串行锁；
- 数据集仅限研究用途（Oxford-IIIT Pet 许可，见 [`dataset.md`](dataset.md)）。
