# U6.1-S0：Git 工作区与保护对象核验（未提交）

> 生成时间：2026-10-20T08:55:30.972474+00:00
> 执行脚本：`scripts/u6_collect_s0_snapshot.py`（**只读，无任何 git 写操作**）

## 1. 结论

**本轮不执行 Git 提交。** 原因：工作区同时混有 U4/U5/U5.1/U5.2/U5.3/U5.4/U5.5/U6
多轮未提交改动与大量历史产物，**无法在不误伤的前提下切分出「仅 U6.1 所需」或
「仅 U5.5 接入所需」的最小提交集**。按任务 §8 要求：无法安全分割则保持未提交、
保存快照并继续实验。

## 2. 当前 Git 状态

- HEAD：`547c55d v2训练前`
- HEAD SHA：`547c55dd96b5d2a9aca71c58458f4192e55b38f5`
- 已跟踪改动：**18** 个文件
- 未跟踪项：**61** 个
- `git diff --check`：无空白/冲突标记问题
- 正式 `data/app.db`：`142` 条，`integrity_check: ok`

## 3. 变更分组清单

| 分组 | 文件数 | 文件 |
|---|---|---|
| U6 训练工具与实验产物 | 16 | `ml/dataset.py`<br>`ml/train.py`<br>`artifacts/v2_2_border_collie_exp01_pair_color_jitter_seed42/`<br>`artifacts/v2_2_border_collie_exp02_pair_sampler_seed42/`<br>`artifacts/v2_2_border_collie_exp04_resolution_seed2024/`<br>`artifacts/v2_2_border_collie_exp04_resolution_seed42/`<br>`artifacts/v2_2_border_collie_exp04_resolution_seed7/`<br>`ml/u6_pair_training.py`<br>`reports/u6_border_collie/`<br>`scripts/u6_baseline_val.py`<br>`scripts/u6_collect_s0.py`<br>`scripts/u6_collect_s0_snapshot.py`<br>`scripts/u6_compare_candidates.py`<br>`scripts/u6_freeze_criteria.py`<br>`scripts/u6_parse_reviews.py`<br>`scripts/u6_run_experiment.py` |
| U5.5 V2.1 默认接入与 136 类映射 | 9 | `backend/app/config.py`<br>`backend/app/main.py`<br>`backend/app/schemas.py`<br>`backend/app/services/predictor.py`<br>`frontend/src/utils/breedNames.js`<br>`frontend/tests/breedNames.test.js`<br>`frontend/tests/historyView.test.js`<br>`tests/test_api.py`<br>`tests/test_predictor_service.py` |
| U5 / U5.2 四类候选组 | 4 | `backend/app/routes/predict.py`<br>`frontend/src/components/PredictionResult.vue`<br>`ml/predict.py`<br>`ml/predictor.py` |
| U4 V2.1 训练扩展 | 1 | `tests/test_train_extensions.py` |
| 其他历史产物 / 未分类 | 49 | `"\345\220\257\345\212\250\345\220\216\347\253\257.bat"`<br>`"\345\220\257\345\212\250\347\263\273\347\273\237.bat"`<br>`artifacts/_v2_1_smoke/`<br>`artifacts/v2_1_136classes_seed42/`<br>`backend/app/services/candidate_group.py`<br>`frontend/tests/predictionResult.test.js`<br>`frontend/tests/predictionResultAcceptance.test.js`<br>`"md/U5.2_\346\226\271\346\241\210B1\345\233\233\347\261\273\347\233\270\350\277\221\347\212\254\347\247\215\345\200\231\351\200\211\347\273\204\346\255\243\345\274\217\345\256\236\347\216\260\344\273\273\345\212\241.md"`<br>`"md/U5.4_\345\200\231\351\200\211\347\273\204\345\220\214\345\233\276\344\270\200\350\207\264\346\200\247\344\270\216\345\211\215\347\253\257\345\233\236\345\275\222\346\265\213\350\257\225\344\273\273\345\212\241.md"`<br>`"md/U5.5_V2.1\346\255\243\345\274\217\346\216\245\345\205\245\344\270\216\350\276\271\347\211\247\345\207\206\347\241\256\347\216\207\346\224\271\350\277\233\350\256\241\345\210\222.md"`<br>`"md/U5_1_APBT\347\272\263\345\205\245\345\233\233\347\261\273\345\200\231\351\200\211\347\273\204\347\246\273\347\272\277\350\257\204\344\274\260\344\273\273\345\212\241.md"`<br>`"md/U6.1_\344\275\216\345\255\246\344\271\240\347\216\207\347\272\240\345\201\217\344\270\216\350\276\271\347\211\247\344\270\223\351\241\271\345\257\271\347\205\247\345\256\236\351\252\214\344\273\273\345\212\241.md"`<br>`"md/V2.1_136\347\261\273\345\210\253\346\250\241\345\236\213\350\256\255\347\273\203\344\273\273\345\212\241.md"`<br>`"md/V2.1_\347\233\270\350\277\221\347\212\254\347\247\215\345\200\231\351\200\211\346\217\220\347\244\272\344\270\216\350\276\271\347\211\247\345\244\215\346\240\270\346\225\264\345\220\210\344\273\273\345\212\241.md"`<br>`"md/V2.1_\350\257\257\345\210\206\347\261\273\350\257\212\346\226\255\344\270\216APBT_AmStaff\346\225\260\346\215\256\345\256\241\350\256\241\344\273\273\345\212\241.md"`<br>`"md/u6_border_collie_improvement_plan_\344\277\256\350\256\242\347\211\210.md"`<br>`reports/u5_5_v2_1_integration/`<br>`reports/v2_1_apbt_four_breed_candidate_eval/`<br>`reports/v2_1_candidate_ui_review/`<br>`reports/v2_1_coat_pitbull_diagnostics/`<br>`reports/v2_1_diagnostics/`<br>`reports/v2_1_four_breed_candidate_implementation/`<br>`reports/v2_1_four_breed_consistency_review/`<br>`reports/v2_1_four_breed_page_acceptance/`<br>`scripts/accept_candidate_group_api.py`<br>`scripts/accept_four_breed_candidate_api.py`<br>`scripts/accept_v2_1_integration.py`<br>`scripts/audit_cross_class_duplicates.py`<br>`scripts/audit_external_sources.py`<br>`scripts/audit_pitbull_labels.py`<br>`scripts/build_manual_review_queue.py`<br>`scripts/check_candidate_consistency.py`<br>`scripts/diagnose_coat_color.py`<br>`scripts/diagnose_v2_1.py`<br>`scripts/diagnostic_protection_snapshot.py`<br>`scripts/evaluate_apbt_four_group.py`<br>`scripts/evaluate_v2_1_subsets.py`<br>`scripts/export_candidate_triggers_val.py`<br>`scripts/finalize_v2_1_candidate.py`<br>`scripts/generate_breed_mapping.py`<br>`scripts/page_accept_four_breed.mjs`<br>`scripts/page_accept_v2_1_integration.mjs`<br>`scripts/reconcile_u5_2_numbers.py`<br>`scripts/run_four_breed_backend.py`<br>`scripts/summarize_coat_review.py`<br>`scripts/summarize_coat_test.py`<br>`scripts/validate_candidate_group_thresholds.py`<br>`scripts/verify_apbt_candidate_limit.py`<br>`tests/test_candidate_group.py` |

## 4. 保护对象哈希（只读核验）

| 文件 | SHA256 |
|---|---|
| `artifacts/best_model.pth` | `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256` |
| `artifacts/class_names.json` | `24120035f4af1c4945ad6e6eb1d82fa1af8b1fd3a9e383ab0246c464dfce75e6` |
| `artifacts/model_version.json` | `377559192e21abfe6ea7735dae1be19a095803ad315a3265050aeb14dca97196` |
| `artifacts/experiment_config.json` | `3823098c4a8fc3fe8a1e15929a00e853e581e8a332b75f6780be12a12d35fa0d` |
| `artifacts/v2_1_136classes_seed42/best_model.pth` | `423e218a29230f8248e071e7fb47b88afb2c1f2b67fb860224f6f319041821e1` |
| `artifacts/v2_1_136classes_seed42/class_names.json` | `216dae77ead6fa5c36499a84ee6092f82a966eb1fae0e43ed9c2930aa07505ad` |
| `artifacts/v2_1_136classes_seed42/model_version.json` | `0b0e5c7f79a000f7f87387c71df213d658f59e12ebfe22f68bf19336fb1cdd08` |
| `artifacts/v2_1_136classes_seed42/experiment_config.json` | `0253416ba4a3f011e87a6b57fb04d62a28bcb1caab2aa6cc9db5d12de4f2439a` |

V1.1 期望值 `89ef468f199c6d1550fec2638c5ea6f8ef7ad543e57f8ec82c4263c121b1a256`；本次实测 **一致**。

## 5. 数据目录与 uploads

| 目录 | 文件数 | 总字节 |
|---|---|---|
| `data/processed/` | 7349 | 790860970 |
| `data/processed_clean/` | 7325 | 787775992 |
| `data/raw/` | 25867 | 1632137687 |
| `data/v2_processed/` | 24098 | 1428084982 |
| `data/v2_processed_prev/` | 29158 | 1622680409 |
| `data/uploads` / `uploads` | 142 | 14678086 |

## 6. 未执行的操作

- 未执行 `git add` / `git commit` / `git reset --hard` / `git clean` / 大范围 `checkout`
- 未删除、覆盖或改写任何文件、报告目录、数据目录、权重或数据库
- 未访问 `data/v2_processed/test`（本阶段不训练、不评估）

## 7. 附件

- `s0/data_inventory.json`
- `s0/git_diff.txt`
- `s0/git_diff_check.txt`
- `s0/git_diff_stat.txt`
- `s0/git_head.txt`
- `s0/git_status_short.txt`
- `s0/tracked_changes.txt`
- `s0/untracked_files.txt`
- `s0/weight_hashes.json`

保护快照：`u6_1_protection_before.json`（`diagnostic_protection_snapshot.py --phase before`）。
