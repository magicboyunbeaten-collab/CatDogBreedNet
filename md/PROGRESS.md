# PROGRESS 当前进度

> 最近更新：2026-10-13

## 当前状态
- 所处阶段：**阶段 3 已完成，等待进入阶段 4（后端 API）**
- 计划状态：阶段 3 执行完毕（评估、性能测试、单元测试、文档、提交全部完成）

## 阶段 3 完成情况（2026-10-13）
- 代码：`ml/evaluate.py`（类别映射校验、全量 test 推理、指标、混淆矩阵 CSV/PNG、双口径 benchmark、CLI）
- 测试：`pytest tests/` **42/42 通过**（阶段 1 的 9 + 阶段 2 的 20 + 阶段 3 新增 13）
- 真实评估：3669 张官方 test 图全量推理（39.46s），Accuracy **0.8035**、Macro-F1 **0.8022**、Weighted-F1 **0.8026**
- 零样本类别：无（37 类均被预测过；`zero_division=0` 策略已记录未生效）
- 性能测试：模型纯推理 1184.9 img/s（batch 32，预热 10 + 计时 50 batch，CUDA 同步，单张平均 2.95/中位 2.20/P95 4.93 ms，1600 次）；端到端（含文件读取与预处理）平均 7.18/中位 5.78/P95 13.65 ms（100 张）
- 产物：reports/ 下 test_metrics.json、classification_report.csv、confusion_matrix.csv、confusion_matrix.png、confusion_matrix_normalized.png、inference_benchmark.json、evaluation_summary.md
- 易混淆：两种斗牛犬互混 35 次；Siamese/Birman/Ragdoll 互混 62 次；basset_hound→beagle 14 次
- 文档：README、reports/README.md、evaluation_summary.md、三文件更新；git 提交完成

## 阻塞 / 等待
- 无

## 下一步（阶段 4 预览）
- `backend/app/`：FastAPI 健康检查、`POST /api/predict`（复用 `ml.predict.predict_image`）、
  文件校验（大小/格式/像素上限）、SQLite 历史记录与统计