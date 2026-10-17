# A5 难例分析：混淆对抽样与人工复核清单

- 生成时间：2026-10-17T03:55:00.943851+00:00
- 权重：`E:\CatDogBreedNet\artifacts\best_model.pth`（基线，未重训）
- 测试集：3669 张，误分类 721 张（19.65%）
- pHash 近重复阈值：≤ 5；抽样种子：42
- 抽样图片已复制到：`E:\CatDogBreedNet\.cache\A5_review\<真实品种>_to_<误判品种>\`
- **本报告不下“标注错误”的最终结论**：是否标签噪声必须人工目检后判定；此处只提供可复核的证据。

## 混淆对抽样清单

| 真实品种 | 误判为 | 该对错误总数 | 抽样数 | 错误平均置信度 |
|---|---|---|---|---|
| Siamese | Birman | 26 | 20 | 0.7328 |
| american_pit_bull_terrier | staffordshire_bull_terrier | 19 | 19 | 0.5899 |
| Birman | Ragdoll | 18 | 18 | 0.7152 |
| Ragdoll | Birman | 18 | 18 | 0.7515 |
| wheaten_terrier | havanese | 17 | 17 | 0.6404 |
| staffordshire_bull_terrier | american_pit_bull_terrier | 16 | 16 | 0.6034 |
| chihuahua | Sphynx | 15 | 15 | 0.6717 |
| basset_hound | beagle | 14 | 14 | 0.7183 |

## 逐对明细（抽样样本）

### Siamese → Birman（26 个错误，抽样 20 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `Siamese_63.jpg` | 0.6443 | 0 | 0 |
| `Siamese_240.jpg` | 0.5787 | 0 | 0 |
| `Siamese_21.jpg` | 0.5825 | 0 | 0 |
| `Siamese_39.jpg` | 0.5385 | 0 | 0 |
| `Siamese_36.jpg` | 0.7916 | 0 | 0 |
| `Siamese_78.jpg` | 0.8128 | 0 | 0 |
| `Siamese_28.jpg` | 0.5418 | 0 | 0 |
| `Siamese_88.jpg` | 0.7387 | 0 | 0 |
| `Siamese_56.jpg` | 0.9776 | 0 | 0 |
| `Siamese_228.jpg` | 0.9265 | 0 | 0 |
| `Siamese_51.jpg` | 0.9775 | 0 | 0 |
| `Siamese_84.jpg` | 0.8589 | 0 | 0 |
| `Siamese_52.jpg` | 0.9181 | 0 | 0 |
| `Siamese_227.jpg` | 0.9366 | 0 | 0 |
| `Siamese_58.jpg` | 0.5000 | 0 | 0 |
| `Siamese_48.jpg` | 0.7554 | 0 | 0 |
| `Siamese_81.jpg` | 0.9589 | 0 | 0 |
| `Siamese_53.jpg` | 0.8671 | 0 | 0 |
| `Siamese_47.jpg` | 0.8647 | 0 | 0 |
| `Siamese_32.jpg` | 0.3415 | 0 | 0 |

### american_pit_bull_terrier → staffordshire_bull_terrier（19 个错误，抽样 19 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `american_pit_bull_terrier_1.jpg` | 0.6797 | 0 | 0 |
| `american_pit_bull_terrier_23.jpg` | 0.3426 | 0 | 0 |
| `american_pit_bull_terrier_27.jpg` | 0.5593 | 0 | 0 |
| `american_pit_bull_terrier_32.jpg` | 0.6466 | 0 | 0 |
| `american_pit_bull_terrier_38.jpg` | 0.2316 | 0 | 0 |
| `american_pit_bull_terrier_4.jpg` | 0.7888 | 0 | 0 |
| `american_pit_bull_terrier_43.jpg` | 0.6712 | 0 | 0 |
| `american_pit_bull_terrier_46.jpg` | 0.7091 | 0 | 0 |
| `american_pit_bull_terrier_48.jpg` | 0.3365 | 0 | 0 |
| `american_pit_bull_terrier_54.jpg` | 0.9800 | 0 | 0 |
| `american_pit_bull_terrier_57.jpg` | 0.6564 | 0 | 0 |
| `american_pit_bull_terrier_64.jpg` | 0.9054 | 0 | 0 |
| `american_pit_bull_terrier_65.jpg` | 0.8065 | 0 | 0 |
| `american_pit_bull_terrier_66.jpg` | 0.7466 | 0 | 0 |
| `american_pit_bull_terrier_7.jpg` | 0.3618 | 0 | 0 |
| `american_pit_bull_terrier_88.jpg` | 0.5721 | 0 | 0 |
| `american_pit_bull_terrier_89.jpg` | 0.3980 | 0 | 0 |
| `american_pit_bull_terrier_90.jpg` | 0.5122 | 0 | 0 |
| `american_pit_bull_terrier_99.jpg` | 0.3042 | 0 | 0 |

### Birman → Ragdoll（18 个错误，抽样 18 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `Birman_196.jpg` | 0.7565 | 0 | 0 |
| `Birman_197.jpg` | 0.5698 | 0 | 0 |
| `Birman_26.jpg` | 0.6655 | 0 | 0 |
| `Birman_28.jpg` | 0.5140 | 0 | 0 |
| `Birman_3.jpg` | 0.8419 | 0 | 0 |
| `Birman_30.jpg` | 0.6896 | 0 | 0 |
| `Birman_36.jpg` | 0.9529 | 0 | 0 |
| `Birman_37.jpg` | 0.8656 | 0 | 0 |
| `Birman_38.jpg` | 0.7059 | 0 | 0 |
| `Birman_54.jpg` | 0.7038 | 0 | 0 |
| `Birman_59.jpg` | 0.6716 | 0 | 0 |
| `Birman_67.jpg` | 0.7191 | 0 | 0 |
| `Birman_79.jpg` | 0.9416 | 0 | 0 |
| `Birman_82.jpg` | 0.6919 | 0 | 0 |
| `Birman_92.jpg` | 0.5654 | 0 | 0 |
| `Birman_94.jpg` | 0.7720 | 0 | 0 |
| `Birman_98.jpg` | 0.5760 | 0 | 0 |
| `Birman_99.jpg` | 0.6703 | 0 | 0 |

### Ragdoll → Birman（18 个错误，抽样 18 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `Ragdoll_203.jpg` | 0.6254 | 0 | 0 |
| `Ragdoll_208.jpg` | 0.8817 | 0 | 0 |
| `Ragdoll_219.jpg` | 0.9865 | 0 | 0 |
| `Ragdoll_228.jpg` | 0.9745 | 0 | 0 |
| `Ragdoll_24.jpg` | 0.9334 | 0 | 0 |
| `Ragdoll_245.jpg` | 0.5409 | 0 | 0 |
| `Ragdoll_252.jpg` | 0.9698 | 0 | 0 |
| `Ragdoll_255.jpg` | 0.2381 | 0 | 0 |
| `Ragdoll_29.jpg` | 0.8922 | 0 | 0 |
| `Ragdoll_35.jpg` | 0.6984 | 0 | 0 |
| `Ragdoll_49.jpg` | 0.5039 | 0 | 0 |
| `Ragdoll_52.jpg` | 0.9207 | 0 | 0 |
| `Ragdoll_53.jpg` | 0.9210 | 0 | 0 |
| `Ragdoll_57.jpg` | 0.8265 | 0 | 0 |
| `Ragdoll_67.jpg` | 0.3699 | 0 | 0 |
| `Ragdoll_81.jpg` | 0.8960 | 0 | 0 |
| `Ragdoll_88.jpg` | 0.6366 | 0 | 0 |
| `Ragdoll_94.jpg` | 0.7110 | 0 | 0 |

### wheaten_terrier → havanese（17 个错误，抽样 17 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `wheaten_terrier_1.jpg` | 0.6698 | 0 | 0 |
| `wheaten_terrier_19.jpg` | 0.4367 | 0 | 0 |
| `wheaten_terrier_198.jpg` | 0.8387 | 0 | 0 |
| `wheaten_terrier_28.jpg` | 0.8376 | 0 | 0 |
| `wheaten_terrier_3.jpg` | 0.5835 | 0 | 0 |
| `wheaten_terrier_36.jpg` | 0.4500 | 0 | 0 |
| `wheaten_terrier_47.jpg` | 0.3876 | 0 | 0 |
| `wheaten_terrier_57.jpg` | 0.8791 | 0 | 0 |
| `wheaten_terrier_67.jpg` | 0.6463 | 0 | 0 |
| `wheaten_terrier_73.jpg` | 0.4629 | 0 | 0 |
| `wheaten_terrier_74.jpg` | 0.7842 | 0 | 0 |
| `wheaten_terrier_79.jpg` | 0.4051 | 0 | 0 |
| `wheaten_terrier_80.jpg` | 0.8864 | 0 | 0 |
| `wheaten_terrier_9.jpg` | 0.6931 | 0 | 0 |
| `wheaten_terrier_90.jpg` | 0.9041 | 0 | 0 |
| `wheaten_terrier_92.jpg` | 0.3961 | 0 | 0 |
| `wheaten_terrier_98.jpg` | 0.6256 | 0 | 0 |

### staffordshire_bull_terrier → american_pit_bull_terrier（16 个错误，抽样 16 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `staffordshire_bull_terrier_24.jpg` | 0.4284 | 0 | 0 |
| `staffordshire_bull_terrier_27.jpg` | 0.6351 | 0 | 0 |
| `staffordshire_bull_terrier_3.jpg` | 0.5191 | 0 | 0 |
| `staffordshire_bull_terrier_32.jpg` | 0.6996 | 0 | 0 |
| `staffordshire_bull_terrier_38.jpg` | 0.5447 | 0 | 0 |
| `staffordshire_bull_terrier_40.jpg` | 0.5210 | 0 | 0 |
| `staffordshire_bull_terrier_42.jpg` | 0.5004 | 0 | 0 |
| `staffordshire_bull_terrier_47.jpg` | 0.4869 | 0 | 0 |
| `staffordshire_bull_terrier_49.jpg` | 0.5432 | 0 | 0 |
| `staffordshire_bull_terrier_54.jpg` | 0.5275 | 0 | 0 |
| `staffordshire_bull_terrier_59.jpg` | 0.7626 | 0 | 0 |
| `staffordshire_bull_terrier_62.jpg` | 0.4137 | 0 | 0 |
| `staffordshire_bull_terrier_66.jpg` | 0.8172 | 0 | 0 |
| `staffordshire_bull_terrier_70.jpg` | 0.8857 | 0 | 0 |
| `staffordshire_bull_terrier_71.jpg` | 0.8851 | 0 | 0 |
| `staffordshire_bull_terrier_93.jpg` | 0.4839 | 0 | 0 |

### chihuahua → Sphynx（15 个错误，抽样 15 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `chihuahua_19.jpg` | 0.9515 | 0 | 0 |
| `chihuahua_25.jpg` | 0.9049 | 0 | 0 |
| `chihuahua_28.jpg` | 0.4778 | 0 | 0 |
| `chihuahua_36.jpg` | 0.4520 | 0 | 0 |
| `chihuahua_41.jpg` | 0.5768 | 0 | 0 |
| `chihuahua_42.jpg` | 0.5738 | 0 | 0 |
| `chihuahua_60.jpg` | 0.6561 | 0 | 0 |
| `chihuahua_63.jpg` | 0.9020 | 0 | 0 |
| `chihuahua_65.jpg` | 0.4605 | 0 | 0 |
| `chihuahua_67.jpg` | 0.7303 | 0 | 0 |
| `chihuahua_75.jpg` | 0.3600 | 0 | 0 |
| `chihuahua_80.jpg` | 0.7906 | 0 | 0 |
| `chihuahua_90.jpg` | 0.6335 | 0 | 0 |
| `chihuahua_91.jpg` | 0.6198 | 0 | 0 |
| `chihuahua_98.jpg` | 0.9856 | 0 | 0 |

### basset_hound → beagle（14 个错误，抽样 14 个）

| 样本文件 | 预测置信度 | train/val 中同标签近重复 | train/val 中异标签近重复 |
|---|---|---|---|
| `basset_hound_198.jpg` | 0.4702 | 0 | 0 |
| `basset_hound_20.jpg` | 0.5571 | 0 | 0 |
| `basset_hound_200.jpg` | 0.9798 | 0 | 0 |
| `basset_hound_23.jpg` | 0.8670 | 0 | 0 |
| `basset_hound_30.jpg` | 0.8533 | 0 | 0 |
| `basset_hound_32.jpg` | 0.8343 | 0 | 0 |
| `basset_hound_4.jpg` | 0.7370 | 0 | 0 |
| `basset_hound_40.jpg` | 0.6591 | 0 | 0 |
| `basset_hound_66.jpg` | 0.5257 | 0 | 0 |
| `basset_hound_68.jpg` | 0.9656 | 0 | 0 |
| `basset_hound_7.jpg` | 0.7958 | 0 | 0 |
| `basset_hound_71.jpg` | 0.4741 | 0 | 0 |
| `basset_hound_81.jpg` | 0.9308 | 0 | 0 |
| `basset_hound_96.jpg` | 0.4069 | 0 | 0 |

## 人工复核方法建议

1. 打开上表中`review_copy`对应的图片（已按混淆对分文件夹复制）；
2. 判断真实品种标签是否正确：若图片实际属于误判品种，则为 Oxford 官方标注错误；
3. 若标签正确但外形确实相近，则记为“真实相似”，说明需要更强的细粒度特征或补充数据；
4. 复核结论回填到本表，作为 A4（补充数据）与 V2 数据清洗的输入。

**约束**：发现官方标注问题也只记录 case，**不修改**官方 test 标注（否则基线不可比）。
