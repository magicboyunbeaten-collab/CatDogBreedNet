# 系统白屏故障恢复报告

> 日期：2026-10-15
> 恢复目标提交：`d8198ec`（2026-10-14 18:57「修复三个前端缺陷并完成模型数据不足诊断」）
> 结论：**已恢复可用**。白屏与启动脚本失效均已修复，未使用 `git reset --hard` / `git clean -fd`，未触碰数据库/数据集/权重/上传/缓存。

## 1. 事件摘要

- **现象**：前端白屏——HTML 仍含 `<div id="app"></div>` 与
  `<script type="module" src="/src/main.js">`，但页面不渲染；三个启动 `.bat` 变为空文件。
- **真实原因**：**工作区中一批已跟踪源文件被清空或截断**（并非 Git 回退导致）。
  此前拟定的 `git checkout -- .` / `git clean -fd` 命令因工具报错**从未执行**，
  提交历史与 `HEAD` 始终完好。

## 2. 白屏根因

`frontend/src/main.js` 与 `frontend/src/App.vue` 被清空为 **0 字节**：

- `main.js` 中的 `createApp(App).use(router).use(ElementPlus).mount('#app')` 消失，
  Vue 应用从未挂载 → `#app` 内无任何节点 → 白屏；
- `index.html` 与 Vite 入口正常，因此 HTML 里仍有 `/src/main.js` 引用，但该文件为空。

## 3. 损坏范围（相对 d8198ec）

**被清空为 0 字节（17 个）**：
`frontend/src/App.vue`、`main.js`、`api/health.js`、`assets/styles.css`、
`router/index.js`、`utils/breedNames.js`、`utils/fileValidation.js`、`utils/navigation.js`、
`tests/{api,breedNames,imageUploader,router,statsView}.test.js`、
`reports/model_improvement_plan.md`、`启动系统.bat`、`启动后端.bat`、`启动前端.bat`

**被截断（6 个）**：`frontend/src/views/PredictView.vue`（15B）、`README.md`、
`.gitignore`、`md/DONE.md`、`md/PROGRESS.md`、`md/TODO.md`、`reports/README.md`

合计 23 个已跟踪文件、净删除 2075 行。

## 4. 恢复所用提交与理由

选用 **`d8198ec`**（上一轮真实浏览器实测通过后的最后一个正常版本），
**没有**退回更早的 `8d2f313` / `e111909`。提交历史与 `git reflog` 完整，无丢失。

## 5. 恢复操作（安全、非破坏）

1. **备份**（先做）：`.cache/recovery_backup/`
   - `status.txt`、`log.txt`、`reflog.txt`
   - `worktree_full.diff`（完整工作区差异 117KB）
   - `corrupted/`（各损坏文件原始副本）
2. **恢复**：`git checkout HEAD -- .`
   - 仅把**已跟踪文件**还原到 `HEAD`；
   - **未**执行 `git reset --hard`、**未**执行 `git clean -fd`；
   - 未移动分支/`HEAD`，未删除未跟踪文件。
3. **未触碰**：`data/app.db`、`data/processed/`、`artifacts/*.pth`、`uploads/`、`.cache/`、
   `frontend/node_modules/`。

## 6. 修改文件（相对 d8198ec，仅 1 处）

- `frontend/tests/historyView.test.js`：修正 `dialogBody()` 查询方式。
  因 `HistoryView.vue` 的弹窗使用 `append-to-body`（jsdom 中内容 teleport 到
  `document.body`），原测试在 `wrapper` 内查找必然失败；改为优先从 `document`
  查询并回退 `wrapper`。修复 3 个失败用例。**运行时行为未变。**

## 7. 验证结果

| 项目 | 结果 |
|---|---|
| `npm run build` | 成功（2262 模块，11.0s；仅既有 chunk 体积告警） |
| Vitest | **54/54 通过** |
| pytest | **73/73 通过** |
| 后端 `/api/health` | `model_loaded:true`、`num_classes:37` |
| `/src/main.js` / `/src/App.vue` | HTTP 200，分别 2021 / 19269 字节 |
| 真实浏览器 `/predict` | 正常渲染（标题、菜单、模型已就绪、上传控件） |
| 真实浏览器 `/stats` | 两张图表渲染（canvas 534×320），标题「品种分布（Top N）」 |
| 真实浏览器 `/history` | 10 行记录；详情弹窗中文正常（荷兰毛狮犬 91.75% / 莱昂贝格犬 / 博美犬） |
| 数据库 | `integrity_check: ok`；`prediction_records` 64 行（id 1..64）；与 uploads 64 个文件一致 |

## 8. 仍未解决的问题 / 待确认

1. **数据库最新记录为 #64**（keeshond，2026-10-14 17:18 本地）。上一轮联调产生的
   #65（samoyed）**当前不在库中**；`data/app.db` 文件修改时间为今天 11:38
   （早于文件被清空的 11:44）。疑似同一异常事件所致，**未做任何写入或补偿**，
   保持原样。
2. **未确定「文件被清空」的触发原因**（时间窗 2026-10-15 11:38–11:44）。
3. 第 6 节的测试修复**尚未提交**（工作区当前仅此 1 处未提交修改）。
4. 未跟踪目录 `reports/diagrams/`、`reports/screenshots/` 保留未动。
5. 模型改进实验（A1–A5 / B 方案）已按要求暂停，未执行。
