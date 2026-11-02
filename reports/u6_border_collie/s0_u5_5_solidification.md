# S0：U5.5 轻量安全固化记录（未提交）

> 生成时间：2026-10-20T02:44:47.257983+00:00
> 执行脚本：`scripts/u6_collect_s0.py`（**只读 git，无任何写操作**）

## 1. 结论：本轮**未执行 Git 提交**

按计划 §2.2 的退路执行：工作区同时混有 **U5.2 / U5.3 / U5.4 / U5.5** 四轮
未提交改动与大量历史产物，**无法在不误伤的前提下切分出"仅 U5.5 接入所需"**
的最小提交集。强行提交会把无关改动混入或漏掉运行依赖，风险高于收益。

因此本阶段只做**可恢复与可追溯**：保存完整快照、差异清单与权重哈希，
并在此记录阻塞点，随后直接进入 U6-A（不因提交整理阻塞边牧诊断）。

## 2. 当前 Git 状态

- HEAD：`547c55d v2训练前`
- HEAD SHA：`547c55dd96b5d2a9aca71c58458f4192e55b38f5`
- 已跟踪改动文件数：**17**
- 未跟踪项数：**47**
- `git diff --check`：无空白/冲突标记问题

### 2.1 已跟踪改动（按阶段归类）

| 阶段 | 文件 |
|---|---|
| U5.5 V2.1 默认接入与 136 类映射 | `backend/app/config.py`<br>`backend/app/main.py`<br>`backend/app/schemas.py`<br>`backend/app/services/predictor.py`<br>`frontend/src/utils/breedNames.js`<br>`frontend/tests/breedNames.test.js`<br>`frontend/tests/historyView.test.js`<br>`tests/test_api.py`<br>`tests/test_predictor_service.py` |
| U5/U5.2 四类候选组 | `backend/app/routes/predict.py`<br>`frontend/src/components/PredictionResult.vue`<br>`ml/predict.py`<br>`ml/predictor.py` |
| U4 V2.1 训练扩展 | `ml/train.py`<br>`tests/test_train_extensions.py` |
| 未归类 | `"\345\220\257\345\212\250\345\220\216\347\253\257.bat"`<br>`"\345\220\257\345\212\250\347\263\273\347\273\237.bat"` |

### 2.2 未跟踪项（节选，完整见 `s0/untracked_files.txt`）

- `artifacts/_v2_1_smoke/`
- `artifacts/v2_1_136classes_seed42/`
- `backend/app/services/candidate_group.py`
- `frontend/tests/predictionResult.test.js`
- `frontend/tests/predictionResultAcceptance.test.js`
- `"md/U5.2_\346\226\271\346\241\210B1\345\233\233\347\261\273\347\233\270\350\277\221\347\212\254\347\247\215\345\200\231\351\200\211\347\273\204\346\255\243\345\274\217\345\256\236\347\216\260\344\273\273\345\212\241.md"`
- `"md/U5.4_\345\200\231\351\200\211\347\273\204\345\220\214\345\233\276\344\270\200\350\207\264\346\200\247\344\270\216\345\211\215\347\253\257\345\233\236\345\275\222\346\265\213\350\257\225\344\273\273\345\212\241.md"`
- `"md/U5.5_V2.1\346\255\243\345\274\217\346\216\245\345\205\245\344\270\216\350\276\271\347\211\247\345\207\206\347\241\256\347\216\207\346\224\271\350\277\233\350\256\241\345\210\222.md"`
- `"md/U5_1_APBT\347\272\263\345\205\245\345\233\233\347\261\273\345\200\231\351\200\211\347\273\204\347\246\273\347\272\277\350\257\204\344\274\260\344\273\273\345\212\241.md"`
- `"md/V2.1_136\347\261\273\345\210\253\346\250\241\345\236\213\350\256\255\347\273\203\344\273\273\345\212\241.md"`
- `"md/V2.1_\347\233\270\350\277\221\347\212\254\347\247\215\345\200\231\351\200\211\346\217\220\347\244\272\344\270\216\350\276\271\347\211\247\345\244\215\346\240\270\346\225\264\345\220\210\344\273\273\345\212\241.md"`
- `"md/V2.1_\350\257\257\345\210\206\347\261\273\350\257\212\346\226\255\344\270\216APBT_AmStaff\346\225\260\346\215\256\345\256\241\350\256\241\344\273\273\345\212\241.md"`
- `"md/u6_border_collie_improvement_plan_\344\277\256\350\256\242\347\211\210.md"`
- `reports/u5_5_v2_1_integration/`
- `reports/v2_1_apbt_four_breed_candidate_eval/`
- `reports/v2_1_candidate_ui_review/`
- `reports/v2_1_coat_pitbull_diagnostics/`
- `reports/v2_1_diagnostics/`
- `reports/v2_1_four_breed_candidate_implementation/`
- `reports/v2_1_four_breed_consistency_review/`
- `reports/v2_1_four_breed_page_acceptance/`
- `scripts/accept_candidate_group_api.py`
- `scripts/accept_four_breed_candidate_api.py`
- `scripts/accept_v2_1_integration.py`
- `scripts/audit_cross_class_duplicates.py`
- `scripts/audit_external_sources.py`
- `scripts/audit_pitbull_labels.py`
- `scripts/build_manual_review_queue.py`
- `scripts/check_candidate_consistency.py`
- `scripts/diagnose_coat_color.py`
- `scripts/diagnose_v2_1.py`
- `scripts/diagnostic_protection_snapshot.py`
- `scripts/evaluate_apbt_four_group.py`
- `scripts/evaluate_v2_1_subsets.py`
- `scripts/export_candidate_triggers_val.py`
- `scripts/finalize_v2_1_candidate.py`
- `scripts/generate_breed_mapping.py`
- `scripts/page_accept_four_breed.mjs`
- `scripts/page_accept_v2_1_integration.mjs`
- `scripts/reconcile_u5_2_numbers.py`
- …其余 7 项见文件

## 3. 权重与配置哈希（只读核验）

| 文件 | SHA256 |
|---|---|
| `artifacts/best_model.pth` | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` |
| `artifacts/class_names.json` | `24120035f4af1c4945ad6e6eb1d82fa1af8b1fd3a9e383ab0246c464dfce75e6` |
| `artifacts/v2_1_136classes_seed42/best_model.pth` | `423e218a29230f8248e071e7fb47b88afb2c1f2b67fb860224f6f319041821e1` |
| `artifacts/v2_1_136classes_seed42/class_names.json` | `216dae77ead6fa5c36499a84ee6092f82a966eb1fae0e43ed9c2930aa07505ad` |
| `artifacts/v2_1_136classes_seed42/model_version.json` | `0b0e5c7f79a000f7f87387c71df213d658f59e12ebfe22f68bf19336fb1cdd08` |
| `artifacts/v2_1_136classes_seed42/experiment_config.json` | `0253416ba4a3f011e87a6b57fb04d62a28bcb1caab2aa6cc9db5d12de4f2439a` |

V1.1 `artifacts/best_model.pth` 期望值 `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256`；
本次实测**一致**。

## 4. 若要提交，人工切分建议

1. 先确认 U5.5 接入所依赖的最小集合（建议：第 2.1 节第 1 组的 11 个文件，
   加上未跟踪的 `backend/app/services/candidate_group.py`、
   `frontend/tests/predictionResult*.test.js`、`tests/test_candidate_group.py`、
   `scripts/run_four_breed_backend.py` 等运行/测试依赖）。
2. 逐文件 `git diff` 审阅，确认没有把 U5.1/U5.2 的实验脚本混入。
3. `git add <显式文件列表>`（**不要 `git add .`**），随后
   `git diff --cached --name-status` 二次核对。
4. 排除项：`artifacts/v2_1_136classes_seed42/`、`artifacts/_v2_1_smoke/`、
   任何 `reports/` 目录、`data/`、`uploads/`、`.cache/`、`*.pth`。
5. 本轮**不执行上述步骤**，留待人工决定。

## 5. 未处理的工作区项

- 17 个已跟踪改动、47 个未跟踪项**全部原样保留**。
- 未执行 `git add` / `git commit` / `git reset --hard` / `git clean` / 大范围 `checkout`。
- 未删除任何报告、数据目录或权重文件。

## 6. 附件清单

- `s0/git_diff.txt`
- `s0/git_diff_check.txt`
- `s0/git_diff_stat.txt`
- `s0/git_head.txt`
- `s0/git_status_short.txt`
- `s0/tracked_changes.txt`
- `s0/untracked_files.txt`
- `s0/weight_hashes.json`
