# U5.5 验收清单（对照任务单 D1–D4）

> 每一项都标注**实际执行方式**与**证据文件**。未执行的项目不会出现在本表。
> 执行时间：2026-10-19

---

## D1. 模型与类别表

| # | 要求 | 结果 | 证据 |
|---|---|---|---|
| D1-1 | 默认加载模型身份为 V2.1、类别数精确 136 | **PASS** | 真实入口 `/api/health` → `num_classes:136`；日志 `model ready: version=v2_1_136classes_candidate ... classes=136`（`real_launcher_backend_stderr.log`） |
| D1-2 | checkpoint 与 `class_names.json` 一一匹配、label 不重复、顺序一致 | **PASS** | `class_names.json` 136 唯一；checkpoint `num_classes=136`、`class_names` 顺序比对 `True`；`fc.weight (136,512)` |
| D1-3 | 人为制造 37/136 类路径错配的单测必须失败并给出清楚错误 | **PASS** | `tests/test_predictor_service.py::test_class_count_mismatch_names_both_sides`（断言消息含 `class count mismatch` + 两侧计数 + 两个文件名）、`test_class_count_mismatch_does_not_silently_fall_back` |
| D1-4 | 根目录 V1.1 权重/类表/版本文件 SHA256 不变 | **PASS** | `protection_snapshot_before/after.json` 自动比对「全部受保护对象一致」；V1.1 `best_model.pth` = `89ef468f…a256` |

## D2. 预测和四类候选（全部使用 validation 样本）

| # | 场景 | 结果 | 证据 |
|---|---|---|---|
| D2-1 | APBT/AmStaff 竞争样本按 B1 显示四类候选 | **PASS** | `acceptance_v2_1_default.json`（A 组）；`page_acceptance_on.json` 场景 1 |
| D2-2 | APBT 为 Top-1 时候选组含 APBT，原始 Top-1 不被替换 | **PASS** | 同上（B 组）；页面场景 2：Top-1 = 美国比特斗牛梗、候选区含 APBT、原始分 46.72% |
| D2-3 | SBT / American Bulldog 对应触发样本 | **PASS（含如实说明）** | SBT：真实 val 触发样本 `staffordshire_bull_terrier_160.jpg`（mass 0.4579 / margin 0.3946）通过；**American Bulldog：val 中 9 张 Top-1=AmBull，0 张满足阈值**，故改用函数级合成样本验证触发与 Top-1 保留，并在报告中如实记录（**未编造样本、未调阈值**） |
| D2-4 | 非候选组猫图不出现候选区 | **PASS** | API：`triggered=False`、`reason="top-1 不在候选组内"`；页面场景 5：候选区完全不出现，猫显示「阿比西尼亚猫」 |
| D2-5 | 候选功能环境变量关闭后候选区不显示，原始 Top-1/Top-K/分数不变 | **PASS** | API（E 组）：`candidate_group` 缺失 + `predictions` 逐位相同；页面场景 7：候选区消失、Top-1 仍为「美国比特斗牛梗」 |
| D2-6 | 同一图片同配置连续 5 次稳定 | **PASS** | `same_image_repeated_requests_default.csv`：`triggered` 全 True、候选顺序全同、Top-1 标签全同、**`max_abs_diff = 0.000e+00`**、组内得分和 `[100.0 ×5]` |

## D3. 前端与历史

| # | 要求 | 结果 | 证据 |
|---|---|---|---|
| D3-1 | 136 类都显示合适中文名，英文下划线不作主标签 | **PASS** | 映射 136 条、缺失 0；页面场景 6：所有 Top-K 主标签无 `_`；`breedNames.test.js`「never renders an English underscore label as the main name」 |
| D3-2 | 四类候选中文名与 `group_score` 正确、标注「候选组内相对得分」 | **PASS** | 页面场景 1：四候选名与面板一致、`sum=100.01%`、图例含「候选组内相对得分」 |
| D3-3 | 文案不暗示四候选中一定有正确答案 | **PASS** | `predictionResult.test.js` 用例 H（断言不含「其中必有一个 / 必然 / 一定是」） |
| D3-4 | 用户选择不替换模型预测、不写库、不当训练标签 | **PASS** | 页面场景 3：选择后「模型首选仍为…未被替换」、Top-K 未变；DB 表无候选组字段（U5.2 验收 + 本轮隔离 DB 复核） |
| D3-5 | 历史页/详情/统计页正常，142 条记录未被重写，新旧英文标签都能显示 | **PASS** | `historyView.test.js` 新增「旧 37 类与新 99 类的历史标签都能显示中文」；`statsView`/`router` 测试通过；正式 DB 行数 **142 未变** |
| D3-6 | 边牧 / 柯利 / 边境梗名称互不混淆 | **PASS** | `breedNames.test.js`「keeps border collie / collie / border terrier distinct」：边境牧羊犬 / 柯利牧羊犬 / 边境梗 |

## D4. 数据与系统

| # | 要求 | 结果 | 证据 |
|---|---|---|---|
| D4-1 | `pytest tests/ -q` 全部通过 | **PASS** | **250 passed**（基线 244 + 新增 6） |
| D4-2 | `cd frontend; npm test` 全部通过 | **PASS** | **79 passed / 11 files** |
| D4-3 | `cd frontend; npm run build` 成功 | **PASS** | `built in 855ms` |
| D4-4 | 真实日常启动入口启动并记录 `/api/health` | **PASS** | `cmd /c 启动后端.bat` → `{"num_classes":136,"model_weights":"best_model.pth","model_loaded":true}` |
| D4-5 | 正式 SQLite `integrity_check: ok`，行数仍为 142 | **PASS** | `records = 142`、`integrity = ok`（真实入口只调 health，未发起预测） |
| D4-6 | 数据目录与 uploads 与开始前一致 | **PASS** | `protection_snapshot` 前后比对一致；`uploads = 142` |
| D4-7 | V1.1 / V1 备份 / V2.1 哈希均一致 | **PASS** | 同上（V2.1 四文件 SHA256 一致） |

---

## 附：隔离与真实入口的分工（避免污染正式历史）

| 层级 | 用途 | 存储 | 是否写正式 DB |
|---|---|---|---|
| 隔离 API 验收（`accept_v2_1_integration.py`） | 六场景 + 5 次一致性 | `runtime_isolated_on/off`、`runtime_default_on/off` | **否**（临时 SQLite） |
| 真实启动入口（`启动后端.bat`） | 只调 `/api/health` 取证 | 正式 `data/app.db` | **否**（未发起预测） |
| 浏览器验收（`page_accept_v2_1_integration.mjs`） | 上传 + 截图 | `runtime_web/`（`CATDOG_DB_PATH` / `CATDOG_UPLOAD_DIR` 覆盖） | **否** |
| 回退验证 | health + 1 次预测 | `runtime_rollback/` | **否** |

---

## 汇总

| 类别 | 通过 | 失败 |
|---|---|---|
| D1 模型与类别表 | 4 | 0 |
| D2 预测与四类候选 | 6 | 0 |
| D3 前端与历史 | 6 | 0 |
| D4 数据与系统 | 7 | 0 |
| **合计** | **23** | **0** |

另附独立自动化验收：

| 验收 | 结果 |
|---|---|
| 隔离模式 API（`--mode isolated`） | **43 / 43** |
| 默认配置 API（`--mode default`） | **43 / 43** |
| 浏览器（候选开启） | **23 / 23** |
| 浏览器（候选关闭） | **4 / 4** |
