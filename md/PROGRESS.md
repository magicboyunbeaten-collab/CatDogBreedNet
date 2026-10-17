# PROGRESS 当前进度

> 最近更新：2026-10-14

## 当前状态
- **全部 6 个阶段 + 最终验收修复 + 界面缺陷修复轮均已完成**
- 项目达到 CODEBUDDY.md §16 定义的交付状态；模型诊断报告已交付，改进实验待用户确认后执行

## 界面缺陷修复与模型诊断（2026-10-14，commit 8d2f313 之后新一轮）
- **Back 按钮**：根因为 `el-page-header` 的 `back` 事件未绑定处理函数；已新增
  `frontend/src/utils/navigation.js`（站内历史 `router.back()`，直接打开回退 `/predict`），
  默认识别页移除死按钮；真实 Chrome 实测三种导航场景
- **统计图表空白**：根因为 `renderCharts()` 在 `loading` 仍为 true 时执行，图表行
  `v-if="!loading"` 尚未渲染容器，ECharts 从未初始化；已修复为 loading 解除后初始化
  （+加载占位、签名去重、Top N 标题、中文 x 轴、合计口径说明）
- **历史详情中文**：详情弹窗品种名经 `breedNames.js` 映射中文（DB/API/权重不变）；
  附带修复 element-plus 2.14 弹窗未 teleport 导致关闭按钮被遮挡（`append-to-body`）
- **模型诊断**：`reports/model_improvement_plan.md`——每类 84–90 张（均值 89.5，无类别
  不平衡）；Macro-F1 0.8022，最弱两种斗牛犬/吉娃娃/Ragdoll；样本量与 F1 相关系数 -0.182；
  37 类改进实验 A1–A5 与新类别扩充 B 方案；防泄漏规则；**未重新训练、未覆盖权重**
- **测试**：前端新增 navigation/router/statsView/historyView 共 23 个用例，
  Vitest **54/54**；后端 pytest **73/73**；`npm run build` 成功
- **真实联调**：samoyed_1.jpg 识别 → 记录 #65；统计 64→65、分布合计 32→33、
  趋势合计 65=总数，刷新后持久化；CLI 与 API 同图 Top-3 逐位一致
- 本轮测试在正式库新增 1 条记录（#65，用户要求的真实识别联调产生）

## 阻塞 / 等待
- 无（A3b 替换基线权重待用户确认；替换前建议先定 A3b 早停策略）

## 泄漏审查与多种子配对验证（2026-10-17，A3b 替换默认模型的前置检查）
用户要求"在决定是否替换默认模型前，先完成数据泄漏风险检查与多随机种子对比"。

**阶段一 泄漏审查（提交 b751c11）**
- `scripts/review_near_duplicates.py`：25 对跨划分近重复的 MD5/尺寸/均色差/
  灰度相关度/初步分级 + 45 张并排联系表；`--verdicts` 固化人工判定
- **逐张目视核验：25/25 为同一照片变体，0 例 pHash 误报**
  （24 对 train/val→test、1 对 train↔val）——官方数据集固有泄漏
- `scripts/build_clean_split.py`：`data/processed_clean/`
  （train 3288 / val 368 / test 3669，官方 test 原样保留）
  **校验：pHash 跨划分近重复 0、MD5 跨划分 0、跨集合簇 0、37 类一致**
- 修复 2 个缺陷：配对丢失 left/right 归属导致漏排（25 对只排除 23 对）；
  `_blocks` 对 2D 数组扁平切片越界。新增 10 个回归用例

**阶段二 5 种子配对验证（提交 728281f）**
- `scripts/run_seed_validation.py`：baseline 与 A3b × 种子 42/2024/7/123/20261017，
  同一去重划分，两配置仅差学习率策略，val 选模、test 每运行仅评估一次
- baseline：Acc 0.8077±0.0013 / Macro-F1 0.8055±0.0014 / val 0.8370±0.0061 / 2.286ms
- A3b：Acc 0.8729±0.0185 / Macro-F1 0.8715±0.0182 / val 0.8973±0.0068 / 2.191ms
- **配对差值：Acc +0.0652±0.0177 / Macro-F1 +0.0660±0.0171 / Weighted-F1 +0.0663±0.0172，
  5/5 种子全部为正**；最小差值约为基线种子噪声（0.0014）的 29 倍
- 逐类 36/37 提升（最大 chihuahua +0.180、english_cocker_spaniel +0.134）；
  唯一下降 Maine_Coon −0.021
- 泄漏影响：原始划分 0.8035/0.8022 vs 去重划分 0.8077/0.8055，总体仅差约 +0.004；
  少数品种被抬高（japanese_chin 0.9388→0.8778）
- 附带发现：A3b 对早停敏感（2/5 种子 epoch 1 即最佳后回落），+0.066 为稳健下界

**约束遵守**：基线权重与 `data/processed` 零改动（mtime 仍为 10-13 / 仍 3311-369-3669）；
未据 test 调参；未替换默认模型；A5 难例保留人工审查；pytest **124/124**

## 模型升级 U1-U2（2026-10-17，依据 md/MODEL_UPGRADE_PLAN (1).md）
- **U1 诊断**：`scripts/diagnose_dataset.py`（只读）+ `reports/model_diagnostics.md`。
  坏图 0；MD5 跨子集重复 0 组；**pHash 近重复 45 对（25 对跨子集、全同品种）**；
  corr(样本量, F1) = -0.182，**corr(跨子集近重复数, F1) = 0.4807**；
  末轮 train/val 差距 0.156（过拟合）；`split_summary.json` 为占位内容已披露
- **U2 训练管线扩展**：多架构（resnet18/50、convnext_tiny、efficientnet_b0）、
  增强预设、冻结策略、分层 LR、label smoothing、Mixup；默认值与基线逐项一致；
  修复 `save_checkpoint` 未传 `arch` 的缺陷（A4_resnet50 评估失败根因）
- **A2-A5 实验（10 个全部真实完成）**：
  - **A3b 分层学习率最优：Macro-F1 0.8807（+0.0785），延迟与基线持平**
  - A3a 解冻 layer4 +0.0610；A3c label smoothing +0.0166
  - A4 EfficientNet-B0 +0.0651 但延迟 +122% 超预算；ConvNeXt-Tiny/ResNet50 显著更差
    （证明基线配方无法迁移，非架构容量结论）
  - A2c RandomErasing +0.0040（噪声边缘）；A2b ColorJitter -0.0069
  - A2d Mixup -0.2034（轮数不足）；A3d 20 轮+早停 -0.2146（早停过早）
  - A5：147 个难例无一存在 train/val 近重复 → 误分类与泄漏无关
  - 发现运行间非确定性（噪声 ±0.02-0.05），±0.01 内差异不下结论
- **测试**：pytest **114/114**（73 旧 + 14 诊断 + 27 训练管线）
- **基线权重未替换**；A3b 候选在 `artifacts/exp_A3b_layered_lr/`；
  A1/B/U3-U5 因缺合规数据未执行

## 交付物清单

## 最终验收修复完成情况（2026-10-14）
- **重新上传缺陷**：真实浏览器复现成功（清除后再上传被 `on-exceed` 静默阻断）；
  根因为 el-upload `limit=1` + 内部文件列表未清空、原生 input 未重置、
  `PredictView` 一键清空未联动。修复后真实 Chrome A–E 全序列（含同文件重传、
  不清除换图、一键清空后再传）无需刷新页面全部通过
- **测试**：新增 `frontend/tests/imageUploader.test.js` 8 个组件回归用例与
  `frontend/tests/breedNames.test.js` 5 个用例；前端 Vitest **31/31**、
  后端 pytest **73/73**、生产构建成功
- **中文品种名**：`frontend/src/utils/breedNames.js`（37 类，与 `class_names.json`
  全量核对）；识别页显示中文（英文回退），历史/统计保持英文标签；真实浏览器验收通过
- **启动脚本**：`启动系统.bat`/`启动后端.bat`/`启动前端.bat`；已实际执行
  （成功路径双服务拉起；缺失 venv 失败路径 exit 1 + 清晰提示）
- **边牧范围核查**：Border Collie 不在 37 类；改进建议与两种能力区分写入
  `reports/thesis_materials.md` 第 9 节；未改权重/指标/报告
- **数据保护**：仅删除本轮自动化测试自建记录；正式库演示记录与用户手动测试记录保留
- **记录来源修正**：阶段 6"来源无法追溯"记录已更正为用户手动识别测试产生

## 阻塞 / 等待
- 无

## 交付物清单
- 代码：ml/、backend/、frontend/（含 breedNames 中文映射与修复后的上传组件）、tests/、scripts/
- 启动入口：`启动系统.bat` / `启动后端.bat` / `启动前端.bat`
- 产物（本机，不入 Git）：artifacts/best_model.pth、data/processed、data/app.db、
  reports 下 csv/png/日志/diagrams/screenshots
- 文档（入 Git）：README（含快速启动）、reports/{dataset,evaluation_summary,
  system_test_report,thesis_materials,README}.md、md 三文件、.env.example、
  requirements.txt、frontend/package-lock.json