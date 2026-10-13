# PROGRESS 当前进度

> 最近更新：2026-10-13

## 当前状态
- 所处阶段：**阶段 4 已完成，等待进入阶段 5（Vue 3 前端）**
- 计划状态：阶段 4 执行完毕（后端、测试、集成测试、文档、提交全部完成）

## 阶段 4 完成情况（2026-10-13）
- 代码：`backend/app/`（config/schemas/database/models/main + routes×3 + services×2）；`ml/predictor.py` 新增共享 Predictor 类，`ml/predict.py` CLI 重构为复用同一类（签名与返回结构不变）；`verify_class_mapping` 移至 `ml/model.py`
- 测试：`tests/test_api.py` 31 个用例（假 Predictor + 临时 SQLite + 临时目录）；全量 `pytest tests/` **73/73 通过**（9+20+13+31）
- 真实集成测试（uvicorn:8000，best_model.pth）：
  - health：`model_loaded=true, num_classes=37`；启动日志证实模型仅加载一次；/docs 200
  - predict：beagle_1.jpg → beagle 0.979491（record 1）；samoyed_1.jpg → samoyed 0.998949（record 2，稳态 inference 3.644ms）
  - 错误场景：空文件/文本伪装/BMP 400，>10MB 413，top_k=99 400（无路径/堆栈泄露）
  - DELETE /api/history/2 联动删图成功；history/stats 反映真实入库记录
  - CLI 与 API 同图 Top-3 逐位一致
- 配置：`.env.example`（CATDOG_* 环境变量，默认仅本地 CORS）；未新增依赖
- 文档：README 后端章节（API 表、计时口径、上传保留策略、UTC 时区约定）、reports/README.md、三文件更新；git 提交完成

## 阻塞 / 等待
- 无

## 下一步（阶段 5 预览）
- `frontend/`：Vue 3 + Vite + Element Plus；页面：上传识别（拖拽/预览/Top-K/耗时）、历史（分页/详情/删除）、统计（ECharts）；API base URL 走 `.env.development`；Node 安装需遵守非 C 盘约束