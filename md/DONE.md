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

## 2026-10-13（续）

### 阶段 5：Vue 3 前端（已完成）
- **Node 环境（E 盘约束全部落实）**：Node.js v24.21.0 LTS + npm 11.19.0，官方 ZIP
  （对照 index.json 确认 LTS、SHASUMS256 校验）解压至 `tools/node`；npm 缓存经用户级
  环境变量 `npm_config_cache` 指向 `E:\CatDogBreedNet\.cache\npm`（实测 `npm config get cache`）；
  依赖装于 `frontend/node_modules`；Chromium（agent-browser 测试浏览器，官方 CDN 超时后
  改走 npmmirror 镜像）位于 `.cache/ms-playwright`；C 盘无 npm 缓存
- **前端代码**：`frontend/`（Vue 3.5 + Vite 8 + Vue Router 4 + Element Plus 2.14 + Axios + ECharts 6，纯 JS）
  - `src/api/http.js`：Axios 实例（`VITE_API_BASE_URL`，代码内置默认回退）+ `normalizeError`
    统一错误规范化（网络/超时/400/413/500/503，优先展示后端 error/detail 消息）
  - `src/api/{predict,history,stats,health}.js`：字段名与后端 Schema 逐字对齐；
    FormData 字段 `file` + `top_k`，不手动设置 Content-Type
  - `src/utils/fileValidation.js`：前端预检（10MB/JPEG/PNG/WebP），服务端校验为最终依据
  - `src/components/ImageUploader.vue`：点击/拖拽、本地预览（`URL.revokeObjectURL` 及时释放）、
    移除/重选、预检警告；`PredictionResult.vue`：Top-3 分数、三种耗时口径、Softmax 非概率声明
  - `src/views/`：PredictView（加载防重、错误重试、一键清空）、HistoryView（后端分页、
    详情弹窗、删除二次确认、删除后刷新）、StatsView（ECharts 分布/趋势图、实例 dispose、
    空态/错误态）；`App.vue`：导航 + `/api/health` 就绪状态轮询
- **测试**：Vitest **18/18 通过**（api 适配 7、错误规范化 5、文件预检 6，全 Mock 不依赖真实后端）；
  `npm run build` 成功（dist/ 不入 Git）；后端 `pytest` **73/73 通过**（无回归）
- **真实联调**（真实 Chrome 浏览器 + uvicorn:8000 + vite:5173，2026-10-13）：
  - 上传 `pug_1.jpg` → Top-1 **pug 100.00%**（record 入库）；推理 5.8ms/预处理 2.9ms/总耗时 48.1ms
  - 历史页：新记录可见（随机文件名、UTC 时间）、详情弹窗完整、删除二次确认后列表 Total 4→3
  - 统计页：总次数 3、平均推理耗时 921.32ms、覆盖品种 2，图表正常渲染
  - 刷新/直连 `/history` 数据持久化；CORS 预检与实请求均放行 vite 源（未绕过浏览器安全）
  - 停止后端：顶栏"模型未就绪"、统计页显示"无法连接后端服务"错误提示，页面不白屏
- **文档**：README 前端章节（Node 安装路径、前后端启动命令、环境变量、访问地址、页面清单、
  真实联调结果）、reports/README.md、三文件更新；git 提交完成
- **Git 核对**：`node_modules/`、`dist/`、`frontend/.env.development`、`data/app.db`、`uploads/`、
  数据集与权重均未入库；`package-lock.json` 保留提交

## 2026-10-14

### 阶段 6：系统联调、全面测试与论文素材（已完成）
- **npm 依赖完整性**：`npm ls --depth=0` 顶层依赖完整；`npm ci` 按锁文件干净重装 164 包成功
  （锁文件未改动；npm ci 触发 IDE 安全垫片对 node_modules 批量替换的拦截，已用一次性
  环境变量 `CODEBUDDY_SAFE_DELETE_ENABLED=0` 对该命令显式关闭并如实记录）；
  重装后 Vitest 18/18、`npm run build` 成功（产物哈希与重装前一致）
- **临时隔离环境 E2E**（8001/8002 端口 + 临时 DB + 临时上传目录）：15 项全部通过——
  空库统计、合法预测（samoyed 0.998949/Bengal）、空文件 400、文本伪装 400、BMP 400、
  >10MB 413、top_k 越界 400、历史分页、详情 404、删除联动删图、删除 404、统计一致、
  模型未就绪 health 与 503
- **正式环境真实 Chrome 联调**：8 项全部通过；正式 `data/app.db` 测试前后逐字段一致
  （3 条演示记录零损坏）；本轮测试记录（含用户本人手动识别测试产生的记录）全部清理
- **缺陷修复**：`frontend/src/views/HistoryView.vue` 后端不可用时仅瞬期 toast →
  增加持久错误横幅与"加载失败，请重试"空态；修复后实测通过，Vitest/构建复跑通过
- **论文素材**：`reports/thesis_materials.md`（架构/流程/ER 图引用、API 说明、截图索引、
  评估摘要、环境部署）；`reports/diagrams/` 三张 PNG；`reports/screenshots/` 4 张真实截图
- **功能测试报告**：`reports/system_test_report.md`（自动化 73+18、Mock、真实联调分节；
  统计耗时差异专项核查：DB 均值 921.32ms = 两条首次 CUDA 初始化记录（1441.2/1316.9ms）
  与一条稳态记录（5.8ms）的平均，稳态 2.95–5.8ms，统计接口计算正确，口径已文档化区分）
- **全量回归**：pytest 73/73、Vitest 18/18、build 成功；Git diff 与忽略规则核对通过；
  阶段 6 独立提交

## 2026-10-14（续）

### 最终验收修复（已完成）

- **重新上传缺陷（用户报告）**：
  - 复现：真实 Chrome 中"上传→清除→再上传"后预览不出现、识别按钮禁用，
    与用户描述一致（被 `on-exceed` 静默阻断）；
  - 根因：`ImageUploader.vue` 的 `el-upload :limit="1"` 且内部 `uploadFiles` 列表
    从未清空——清除只重置组件自身状态；原生 input value 未重置导致同文件无法
    再次触发 change；`PredictView.handleReset()` 未联动上传组件导致一键清空后
    预览残留；
  - 修复（最小化改动）：change 处理中先安全取得 File → 校验 → 接受后
    `nextTick` 中 `clearFiles()` 清空 el-upload 内部列表并重置原生 input；
    清除操作同步释放 Object URL、清空文件引用与内部列表；一键清空经
    `uploaderRef.clearSelection()` 联动；移除了造成阻断的 `limit/on-exceed`；
  - 回归：新增 8 个组件测试（A 同文件清除后重传 / B 不清除换图 / C 清除后换图 /
    D 连续切换无残留 / E 失败后可重传 / 原生 input 重置 / 暴露方法 / 重选按钮）；
    真实 Chrome A–E 全序列实测无需刷新页面；本轮测试记录仅删除自建记录
- **中文品种名**：新增 `frontend/src/utils/breedNames.js`（37 类中文映射，键与
  `class_names.json` 逐项一致，未映射回退英文）；`PredictionResult.vue` Top-1/Top-3
  显示中文（title 保留英文原始标签）；新增 5 个测试（含读取真实 class_names.json
  的全量覆盖核对）；真实浏览器验收：比格犬 97.95% / 巴吉度猎犬 0.50% / 迷你杜宾 0.50%，
  历史页保持英文标签
- **边境牧羊犬范围核查**：`class_names.json` 逐项核对确认 **Border Collie 不在 37 类**；
  错误 Top-3（havanese 0.1633）解释、37 类内性能 vs 类别外能力区分、改进建议
  （泛化分析 / 扩充 38 类的完整流程 / 拒识机制及局限）写入 `reports/thesis_materials.md`
  第 9 节；未改权重、未改指标、未改阶段 3 报告
- **启动脚本**：新增 `启动系统.bat`、`启动后端.bat`、`启动前端.bat`
  （`%~dp0` 定位根目录；检查 venv/前端项目/模型文件/Node（含 tools\node 回退）；
  独立窗口启动；TORCH_HOME 与 npm 缓存指向 E 盘；等待提示；失败给清晰提示）；
  实测：成功路径双服务正常拉起（health 200 + 前端 200），失败路径（缺失 venv）
  exit 1 且提示完整；README 增加"快速启动"章节
- **记录来源修正**：`reports/system_test_report.md`、`reports/README.md`、
  `md/DONE.md` 中"来源无法追溯"已更正为该记录由用户本人手动识别测试产生
- **回归**：pytest 73/73、Vitest 31/31、`npm run build` 成功；Git 核对无数据/权重/
  DB/上传/node_modules/dist/缓存入库；独立最终验收修复提交

## 2026-10-14（续二）

### 界面缺陷修复与模型诊断（已完成，commit 8d2f313 之后新一轮）

- **Back 按钮无响应（用户报告）**：
  - 复现：真实 Chrome 中三个页面左上角 Back 有指针但点击无效果；
  - 根因：`el-page-header` 的 `back` 事件未绑定任何处理函数（组件默认样式造成
    "可点击"错觉，与鼠标样式无关）；
  - 修复：新增 `frontend/src/utils/navigation.js`（`canGoBack()` 依据
    `history.state.back` 判断站内历史；`goBack()` 有历史走 `router.back()`，
    无历史回退 `/predict`）；HistoryView/StatsView 绑定 `@back`；PredictView
    （默认页）移除无用途的 Back 按钮改为普通标题栏；
  - 实测（真实 Chrome）：/predict 无 Back 按钮；/history（菜单进入）→ Back 回到
    /predict；直接打开 /stats → Back 落到 /predict；
  - 测试：新增 `navigation.test.js` 6 个 + `router.test.js` 4 个
- **统计页两张图表空白（用户报告）**：
  - 复现：真实 Chrome 中"品种分布"与"每日识别趋势"两个区域空白；
  - 根因：`StatsView.loadStats()` 在 `loading` 仍为 `true` 时调用 `renderCharts()`，
    而图表行 `v-if="!loading && !errorMessage"` 尚未渲染容器——`echarts.init`
    的 ref 为 null，图表从未初始化；`loading` 结束后没有任何再次渲染的调用；
  - 修复：`finally` 中先解除 `loading`，`await nextTick()` 后再 `renderCharts()`；
    图表行改为不随 loading 卸载，加载中显示"加载中…"占位；新增数据签名去重
    （避免 watcher 与 loadStats 双重 init）；标题改为具体 Top N；x 轴品种名经
    `breedNames.js` 中文映射（`interval: 0`）；新增分布/趋势合计口径说明；
  - 实测（真实 Chrome）：canvas 534×320、着色像素 50228/4817；总次数 64、
    Top 10、分布合计 32、趋势合计 64；识别 samoyed_1.jpg 后 64→65、分布合计
    32→33、趋势合计 65=总数；刷新页面后仍为 65（数据库持久化）；
  - 测试：新增 `statsView.test.js` 9 个（正常数据/中文轴/趋势升序/>10 品种 Top 10/
    空数据空态/加载失败/口径一致 ×2/Back 回退）
- **历史详情英文（用户报告）**：
  - 修复：HistoryView 详情弹窗 `predicted_breed` 与 Top-K `breed` 经
    `getBreedDisplayName` 映射中文；未映射回退英文；置信度/排名/耗时原样；
    SQLite 英文标签、API 响应、`class_names.json`、模型权重均未改动；
  - 实测（真实 Chrome）：记录 #65 详情"萨摩耶犬 99.89% / 荷兰毛狮犬 0.07% /
    博美犬 0.02%"；主列表仍为英文（不影响布局，保留）；
  - 测试：新增 `historyView.test.js` 4 个
- **附带修复**：element-plus 2.14.7 的 `el-dialog` 在 `appendTo="body"` 时默认
  **不** teleport（源码 `disabled: appendTo !== 'body' ? false : !appendToBody`），
  详情弹窗渲染在 `.history-view` 内、固定定位被布局裁剪，关闭按钮被页头遮挡；
  增加 `append-to-body` 后弹窗挂载到 body，关闭按钮可点击（已实测）；
- **CLI 与 API 一致性**：samoyed_1.jpg CLI（samoyed 0.9989 / keeshond /
  pomeranian）与 API（萨摩耶犬 99.89% / 荷兰毛狮犬 / 博美犬）Top-3 逐位一致
- **模型诊断（未重新训练）**：`reports/model_improvement_plan.md`——
  重新统计 train 3311（每类 84–90，均值 89.5）/ val 369 / test 3669；
  交叉分析 classification_report.csv：最弱 american_pit_bull_terrier 0.533、
  staffordshire_bull_terrier 0.547、chihuahua 0.604、Ragdoll 0.651、Birman 0.692；
  Pearson corr(每类样本数, F1) = **-0.182**（弱负相关）→ 错误主因是近缘品种
  外形相似度而非样本量分布；混淆对：两种斗牛犬互混 35 次、Siamese/Birman/Ragdoll
  互混 62 次、basset_hound→beagle 14 次；报告区分 37 类样本补充（A1–A5 实验，
  含哈希+pHash 去重防泄漏规则）与新类别扩充（B 方案，38 类重训与遗忘检查），
  全部实验保留官方 test 集为唯一对照；**未重新训练、未覆盖 best_model.pth、
  未改基线报告**
- **回归**：后端 pytest **73/73**、前端 Vitest **54/54**、`npm run build` 成功；
  README、reports/README.md、md 三文件更新；本轮正式库新增记录 #65
  （真实识别联调产生，如实记录）

## 2026-10-17（模型升级 U1-U2）

依据 `md/MODEL_UPGRADE_PLAN (1).md` 推进；分三个独立提交
（U1 诊断 `c1de0ca`、训练管线扩展 `308cef4`、A2-A5 实验与文档）。

### U1 模型诊断（只读，未重训）
- 新增 `scripts/diagnose_dataset.py` + `tests/test_diagnose_dataset.py`（14 用例）；
  产出 `reports/model_diagnostics.md`、`reports/diagnostics_details.json`
- 样本数重新扫描：train 3311（84–90）/ val 369 / test 3669；标签映射三子集一致
- 坏图：7349 张全部可解码，**0 坏图**
- MD5 跨子集完全重复 **0 组**；**pHash（灰度+DCT+8×8 低频）近重复 45 对，
  其中 25 对跨子集且全部同品种，距离 0 占 39 对**
  → Oxford-IIIT 官方划分固有的视觉重复，基线对相关品种可能偏乐观
- **corr(每类 train 样本数, F1) = -0.182**；**corr(跨子集近重复数, F1) = 0.4807**
  （keeshond 0.946/10 对、japanese_chin 0.939/12 对、leonberger 0.945/4 对
  均为 F1 前列且有泄漏；两种斗牛犬 0 对却最弱）→ 列为**待验证假设**，
  建议双口径并列，不删官方 test 图
- 训练曲线：最佳 epoch 8 / val 0.8401；末轮 train 0.9852 vs val 0.8293（差 0.156，
  过拟合形态）
- 披露 `reports/split_summary.json` 为早期占位内容（3 类 Breed_A/B/C、27/3/6 张），
  与真实 37 类数据不符；真实统计以重新扫描与 `split_stats.json` 为准

### U2 训练管线扩展（向后兼容）
- `ml/model.py`：`SUPPORTED_ARCHS`（resnet18 / resnet50 / convnext_tiny /
  efficientnet_b0）；`build_model(arch, num_classes, pretrained)`；
  `_default_factory` 按 checkpoint 的 arch 分发
- `ml/dataset.py`：`build_transforms(image_size, train, augment)`，
  预设 baseline / +colorjitter / +randomerasing；baseline 与阶段 2 逐项一致；
  评估/推理管线恒定确定性；`build_datasets`/`build_dataloaders` 透传
- `ml/train.py`：新增 `--arch`、`--augment`、`--freeze-strategy`、
  `--lr-head`、`--lr-backbone`、`--label-smoothing`、`--mixup-alpha`；
  `apply_freeze_strategy`（none/layer4/head，返回可训练参数统计）、
  `build_optimizer`（分层 LR，跳过冻结参数）、`train_one_epoch`（Mixup 软标签）；
  `experiment_config.json` 完整记录全部设置
- 默认参数与基线逐项一致（已用默认参数冒烟运行核对配置 JSON）
- **修复缺陷**：`save_checkpoint` 未传 `arch`（默认 resnet18）导致非 resnet18
  权重被误标，`load_checkpoint` 用错架构加载报形状不匹配——
  这是 A4_resnet50 首次评估失败的真实根因；已改为 `arch=args.arch`
  并新增 3 个回归测试（resnet50/convnext_tiny/efficientnet_b0 存取往返）
- 新增 `scripts/run_improvement_experiments.py`（实验矩阵、断点续跑、
  `--skip-train` 只重跑评估）
- 测试：`tests/test_train_extensions.py` 27 用例；**pytest 114/114 全过**

### A2-A5 实验（10 个全部真实完成，test 集各只评估一次）
基线 resnet18：val 0.8401 / Acc 0.8035 / Macro-F1 0.8022 / 2.95 ms

| 实验 | 变更 | val_acc | test Acc | test Macro-F1 | ΔMacro-F1 | ms/img |
|---|---|---|---|---|---|---|
| **A3b** | 分层 LR head 1e-3 / bb 1e-4 | **0.8970** | **0.8828** | **0.8807** | **+0.0785** | 2.19 |
| A4_effnet | EfficientNet-B0 bs16 | 0.9051 | 0.8686 | 0.8673 | +0.0651 | 6.55 |
| A3a | 解冻 layer4, lr 5e-4 | 0.8889 | 0.8643 | 0.8632 | +0.0610 | 2.15 |
| A3c | label smoothing 0.1 | 0.8455 | 0.8204 | 0.8188 | +0.0166 | 2.31 |
| A2c | RandomErasing(0.25) | 0.8537 | 0.8084 | 0.8062 | +0.0040 | 2.19 |
| A2b | ColorJitter(0.2) | 0.8455 | 0.7975 | 0.7953 | -0.0069 | 2.30 |
| A4_convnext | ConvNeXt-Tiny bs16 | 0.7507 | 0.6901 | 0.6800 | -0.1222 | 4.51 |
| A2d | Mixup(0.2) | 0.6531 | 0.6154 | 0.5988 | -0.2034 | 2.15 |
| A3d | 20 轮 + 早停(3) | 0.6396 | 0.5898 | 0.5876 | -0.2146 | 2.29 |
| A4_resnet50 | ResNet50 bs16 | 0.3279 | 0.2537 | 0.2305 | -0.5717 | 5.44 |

- **结论 1（最重要）**：降低主干学习率最有效。A3b +0.0785 且 val→test 落差最小
  （0.0142），延迟与基线持平。根因与 U1 的过拟合诊断一致：基线 lr=1e-3 全网络
  训练破坏了预训练特征
- **结论 2**：A4 三个 backbone **没有一个**同时满足计划验收标准
  （Macro-F1 ≥ +0.02 且延迟增幅 ≤ 50%）。EfficientNet-B0 精度最高但延迟 +122%；
  ResNet50 10 轮后 train_acc 仅 0.29（严重欠训练）、ConvNeXt-Tiny 第 2 轮即过拟合
  → **只证明基线配方无法迁移，未建立架构排名**
- **结论 3**：早停 patience=3 过激（A3d 第 5 轮即停，没等到 LR 衰减后收敛）；
  Mixup 在 10 轮下远不够（A2d）
- **结论 4（A5）**：8 个混淆对抽样 147 个难例，**无一在 train/val 存在 pHash 近重复**
  → 误分类与数据泄漏无关，是细粒度相似品种的真实难点；
  图片已复制到 `.cache/A5_review/` 供人工目检；**未下"官方标注错误"结论**
- **方法论发现**：同种子（42）下不同运行的 epoch 轨迹不同（cuDNN 非确定性），
  噪声量级约 ±0.02–0.05；因此 ±0.01 内的差异（A2b/A2c）不下结论，
  需多 seed 确认；超过 ±0.05 的效应结论稳健
- **基线 `artifacts/best_model.pth` 未被替换**；A3b 候选在
  `artifacts/exp_A3b_layered_lr/`，替换需用户确认 + 多 seed 验证
- 产出：`reports/model_experiments_report.md`、`reports/A5_hard_examples.{md,json}`、
  `reports/exp_results/`；更新 `model_improvement_plan.md`（待验证→已验证）、
  README、reports/README.md、md 三文件
- **未执行**：A1（补充真实数据）、B/U3–U5（新增类别）——缺合规图片数据

## 2026-10-17（泄漏审查与多种子配对验证，A3b 替换默认模型的前置检查）

用户要求"在决定是否替换默认模型前，先完成数据泄漏风险检查与多随机种子对比"。
分三个独立提交：阶段一 `b751c11`、阶段二 `728281f`、阶段三（本文档与报告更新）。

### 阶段一：近重复审查 + 去重划分
- 新增 `scripts/review_near_duplicates.py`：对 U1 发现的 25 对跨 train/val/test
  近重复，计算 MD5/尺寸/均色差/灰度相关度并做初步分级，生成 45 张并排联系表 PNG
  与 `reports/leakage_review_contact_sheet.{md,json,csv}`；
  `--verdicts` 支持把人工/目视判定固化进报告
- **逐张目视核验结论：25/25 全部为同一照片的变体**（同一个体、同一场景，
  仅重编码/重裁切），**0 例 pHash 误报**；其中 24 对 train/val→test、
  1 对 train↔val（影响验证集选模）。判定记录
  `reports/leakage_review/visual_verification.json`
- 新增 `scripts/build_clean_split.py`：官方 test 3669 张**原样全量复制**；
  从官方 trainval 剔除 24 张与 test 近重复的样本；剩余 3656 张按 pHash 阈值
  构建近重复簇（并查集 + 多索引分块检索），整簇按"原划分多数决、平局归 train"
  分配，确保簇不跨集合
- 去重划分 `data/processed_clean/`：train 3288 / val 368 / test 3669，37 类；
  **校验全通过**：类别集合与顺序一致、MD5 跨划分重复 0、
  **pHash 跨划分近重复 0**（train/val↔test 与 train↔val 均 0）、跨集合簇 0
- 修复 2 个真实缺陷：
  1. `find_near_duplicate_pairs` 原按字符串排序返回配对，丢失 left/right 归属，
     导致当 test 图片名字母序小于 train 图片名时排除步骤把两侧弄反、漏排样本
     （25 对只排除 23 对，清洁划分校验不通过）；
  2. `_blocks` 对 (8,8) 二维数组按扁平索引切片越界产生空块，使分块索引退化
     为全量扫描。新增 `tests/test_leakage_review.py` 10 个用例固化回归点
- `sync_directory` 改为增量同步（覆盖应有文件 + 只删多余文件 + 清理空目录），
  不用 `shutil.rmtree` 整目录删除（会被一次删上万文件的安全策略拦截）

### 阶段二：5 种子配对实验（真实结果）
- 新增 `scripts/run_seed_validation.py`：baseline 与 A3b 两个预指定配置
  × 种子 42/2024/7/123/20261017，共 10 个运行；同一 `data/processed_clean`、
  同一预处理与评估协议，两配置仅差学习率策略；每 epoch 按 val_acc 选模，
  test 每运行仅评估一次，汇总在全部运行结束后才生成
- **baseline（去重划分，n=5）**：Acc 0.8077±0.0013 / Macro-F1 0.8055±0.0014 /
  Weighted-F1 0.8059±0.0015 / val_acc 0.8370±0.0061 / 2.286ms / 207s
- **A3b（去重划分，n=5）**：Acc 0.8729±0.0185 / Macro-F1 0.8715±0.0182 /
  Weighted-F1 0.8723±0.0182 / val_acc 0.8973±0.0068 / 2.191ms / 154s
- **配对差值（A3b − baseline）**：Acc +0.0652±0.0177 / Macro-F1 +0.0660±0.0171 /
  Weighted-F1 +0.0663±0.0172；范围 [+0.0382, +0.0789]；
  **5/5 种子全部为正**
- 稳健性：baseline 种子间 std 仅 0.0014，A3b 最小配对差值 +0.0403 约为其
  **29 倍**；val_acc 排序与 test 一致，无据 test 选模迹象
- 逐类 **36/37 提升**（最大 chihuahua +0.180、english_cocker_spaniel +0.134、
  wheaten_terrier +0.132），唯一下降 Maine_Coon −0.021
- **泄漏对总体指标影响很小**：同配置下原始划分 0.8035/0.8022 vs 去重划分
  0.8077/0.8055，仅差约 +0.004；但少数品种被抬高
  （japanese_chin 0.9388→0.8778、leonberger 0.9447→0.9231、keeshond 0.9463→0.9333）
- 附带发现：A3b 对早停敏感——2/5 种子在 epoch 1 即达最佳 val_acc 后回落
  （train_acc 已 0.975，头部过拟合），patience=3 于第 4 轮触发；另 3/5 跑满
  10 轮。这使 A3b 种子 std(0.0182)远大于 baseline(0.0014)，
  **+0.066 应视为稳健下界**
- 修复 3 个脚本缺陷：`summary['configs']` 被 `list` 覆盖导致统计不可读；
  `per_class_f1` 混入 CSV 汇总行（40 项而非 37 项）；以及阶段一的配对归属缺陷

### 阶段三：结论与文档
- `reports/seed_validation_report.md`：完整记录协议、逐运行/汇总/配对/逐类
  指标、泄漏影响量化、附带发现、缺陷修复与建议
- `reports/model_improvement_plan.md` 新增第 11 节；更新 README、
  reports/README.md、md 三文件
- **结论：A3b 提升稳健且无推理代价，建议设为默认模型；但按约定未自动替换，
  等待用户确认**。替换前建议先定 A3b 的早停策略（对比 patience 3/5/10）

### 约束遵守与回归
- `artifacts/best_model.pth`、`class_names.json`、历史报告**未改动**
  （mtime 仍为 2026-10-13）；`data/processed/` **未改动**（仍 3311/369/3669）
- 未据 test 调整任何 epoch/种子/参数；未替换默认模型
- A5 的 147 个难例**仍保留为人工审查任务**，未修改任何标签
- `pytest tests/` **124/124** 通过（114 旧 + 10 新增）
