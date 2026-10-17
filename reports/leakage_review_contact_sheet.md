# 近重复图片人工审查联系表（泄漏风险检查）

- 生成时间：2026-10-17T04:21:42.227085+00:00
- pHash 阈值：≤ 5（与 U1 诊断同口径）
- 近重复对总数：**45**（跨 train/val/test **25** 对，划分内部 20 对）
- MD5 完全相同的对数：0
- pHash 距离复算与记录不一致的对数：0

## 初步分级统计

| 分级 | 对数 |
|---|---|
| 极可能同一照片变体 | 39 |
| 很可能同一照片变体 | 4 |
| 疑似 pHash 误报 | 0 |
| 需人工确认 | 2 |

> **重要**：以上分级仅由 pHash 距离与像素相关度自动得出。pHash 距离小既可能来自同一照片的不同压缩/裁切，也可能来自构图相似的**不同**照片（误报）。

## 目视核验结果

- 已核验对数：**25** / 45
- 跨划分对中，目视确认**为同一照片变体（构成泄漏）**：**25** / 25
- 跨划分对中，判定为 pHash 误报（不构成泄漏）：0
- 跨划分对中，尚未核验：0

> 核验方式：逐张打开 `reports/leakage_review/contact_sheet_*.png` 左右并排比对个体、姿态、场景与背景；判定记录见 `reports/leakage_review/visual_verification.json`。**用户的最终复核结论可覆盖此结果。**

## 审查方法

1. 打开 `reports/leakage_review/contact_sheet_*.png`，左右并排比对；
2. 若为同一只宠物、同一拍摄批次的不同帧/裁切 → 记为“同一照片变体”（构成跨集合泄漏）；
3. 若为不同个体、仅品种与构图相似 → 记为“pHash 误报”（不构成泄漏）；
4. 在 CSV 的 `grade` 列后追加 `人工判定` 与 `备注` 两列并回填；
5. 判定结果将决定 `scripts/build_clean_split.py` 的排除范围。

## 逐对明细

| # | 跨划分 | pHash 距离 | 复算 | MD5 相同 | 灰度相关度 | 灰度 MAE | 初步分级 |
|---|---|---|---|---|---|---|---|
| 1 | 是 | 0 | 0 | 否 | 0.99997 | 0.06 | 极可能为同一照片的变体（pHash 完全相同） |
| 2 | 否 | 0 | 0 | 否 | 0.99999 | 0.06 | 极可能为同一照片的变体（pHash 完全相同） |
| 3 | 是 | 0 | 0 | 否 | 0.99998 | 0.067 | 极可能为同一照片的变体（pHash 完全相同） |
| 4 | 否 | 0 | 0 | 否 | 0.98225 | 3.76 | 极可能为同一照片的变体（pHash 完全相同） |
| 5 | 是 | 0 | 0 | 否 | 0.99998 | 0.058 | 极可能为同一照片的变体（pHash 完全相同） |
| 6 | 是 | 0 | 0 | 否 | 0.99998 | 0.059 | 极可能为同一照片的变体（pHash 完全相同） |
| 7 | 是 | 0 | 0 | 否 | 0.99999 | 0.051 | 极可能为同一照片的变体（pHash 完全相同） |
| 8 | 否 | 0 | 0 | 否 | 0.99979 | 2.047 | 极可能为同一照片的变体（pHash 完全相同） |
| 9 | 是 | 0 | 0 | 否 | 0.99998 | 0.076 | 极可能为同一照片的变体（pHash 完全相同） |
| 10 | 是 | 0 | 0 | 否 | 0.99999 | 0.057 | 极可能为同一照片的变体（pHash 完全相同） |
| 11 | 是 | 0 | 0 | 否 | 0.99999 | 0.06 | 极可能为同一照片的变体（pHash 完全相同） |
| 12 | 否 | 0 | 0 | 否 | 0.99999 | 0.069 | 极可能为同一照片的变体（pHash 完全相同） |
| 13 | 是 | 0 | 0 | 否 | 0.99999 | 0.074 | 极可能为同一照片的变体（pHash 完全相同） |
| 14 | 否 | 0 | 0 | 否 | 0.99999 | 0.062 | 极可能为同一照片的变体（pHash 完全相同） |
| 15 | 否 | 0 | 0 | 否 | 0.99998 | 0.162 | 极可能为同一照片的变体（pHash 完全相同） |
| 16 | 是 | 0 | 0 | 否 | 0.99999 | 0.069 | 极可能为同一照片的变体（pHash 完全相同） |
| 17 | 否 | 0 | 0 | 否 | 0.99997 | 0.22 | 极可能为同一照片的变体（pHash 完全相同） |
| 18 | 否 | 0 | 0 | 否 | 0.99992 | 0.805 | 极可能为同一照片的变体（pHash 完全相同） |
| 19 | 否 | 0 | 0 | 否 | 0.99984 | 2.324 | 极可能为同一照片的变体（pHash 完全相同） |
| 20 | 是 | 0 | 0 | 否 | 0.99995 | 0.058 | 极可能为同一照片的变体（pHash 完全相同） |
| 21 | 否 | 0 | 0 | 否 | 0.99978 | 12.584 | 极可能为同一照片的变体（pHash 完全相同） |
| 22 | 是 | 0 | 0 | 否 | 0.99999 | 0.07 | 极可能为同一照片的变体（pHash 完全相同） |
| 23 | 是 | 0 | 0 | 否 | 0.99999 | 0.055 | 极可能为同一照片的变体（pHash 完全相同） |
| 24 | 是 | 0 | 0 | 否 | 0.99985 | 0.285 | 极可能为同一照片的变体（pHash 完全相同） |
| 25 | 是 | 0 | 0 | 否 | 0.99999 | 0.062 | 极可能为同一照片的变体（pHash 完全相同） |
| 26 | 是 | 0 | 0 | 否 | 0.99996 | 0.064 | 极可能为同一照片的变体（pHash 完全相同） |
| 27 | 是 | 0 | 0 | 否 | 0.99997 | 0.055 | 极可能为同一照片的变体（pHash 完全相同） |
| 28 | 是 | 0 | 0 | 否 | 0.99999 | 0.076 | 极可能为同一照片的变体（pHash 完全相同） |
| 29 | 是 | 0 | 0 | 否 | 0.99999 | 0.055 | 极可能为同一照片的变体（pHash 完全相同） |
| 30 | 否 | 0 | 0 | 否 | 0.9999 | 0.577 | 极可能为同一照片的变体（pHash 完全相同） |
| 31 | 否 | 0 | 0 | 否 | 0.99994 | 1.056 | 极可能为同一照片的变体（pHash 完全相同） |
| 32 | 否 | 0 | 0 | 否 | 0.99994 | 0.778 | 极可能为同一照片的变体（pHash 完全相同） |
| 33 | 是 | 0 | 0 | 否 | 0.99993 | 6.327 | 极可能为同一照片的变体（pHash 完全相同） |
| 34 | 是 | 0 | 0 | 否 | 0.99969 | 2.271 | 极可能为同一照片的变体（pHash 完全相同） |
| 35 | 是 | 0 | 0 | 否 | 0.99997 | 0.181 | 极可能为同一照片的变体（pHash 完全相同） |
| 36 | 是 | 0 | 0 | 否 | 0.99999 | 0.053 | 极可能为同一照片的变体（pHash 完全相同） |
| 37 | 否 | 0 | 0 | 否 | 0.99997 | 0.49 | 极可能为同一照片的变体（pHash 完全相同） |
| 38 | 否 | 0 | 0 | 否 | 0.99485 | 2.748 | 极可能为同一照片的变体（pHash 完全相同） |
| 39 | 否 | 0 | 0 | 否 | 0.99997 | 0.289 | 极可能为同一照片的变体（pHash 完全相同） |
| 40 | 否 | 2 | 2 | 否 | 0.99745 | 1.446 | 很可能为同一照片的变体（pHash 距离 2） |
| 41 | 否 | 2 | 2 | 否 | 0.97917 | 8.591 | 很可能为同一照片的变体（pHash 距离 2） |
| 42 | 否 | 2 | 2 | 否 | 0.99872 | 0.373 | 很可能为同一照片的变体（pHash 距离 2） |
| 43 | 否 | 4 | 4 | 否 | 0.90962 | 18.086 | 需人工确认（pHash 距离 4） |
| 44 | 是 | 4 | 4 | 否 | 0.90957 | 18.089 | 需人工确认（pHash 距离 4） |
| 45 | 是 | 4 | 4 | 否 | 0.98288 | 2.81 | 很可能为同一照片的变体（pHash 距离 4） |

## 跨划分逐对明细（含路径）

### #1 pHash 距离 0（复算 0）

- A：`train` / great_pyrenees / `E:\CatDogBreedNet\data\processed\train\great_pyrenees\great_pyrenees_173.jpg`（500×357）
- B：`test` / great_pyrenees / `E:\CatDogBreedNet\data\processed\test\great_pyrenees\great_pyrenees_89.jpg`（500×357）
- MD5 相同：否；灰度相关度 0.99997；灰度 MAE 0.06；RGB MAE 0.081
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（大白熊犬同一姿态坐于同一草地背景，仅裁切不同）

### #3 pHash 距离 0（复算 0）

- A：`train` / keeshond / `E:\CatDogBreedNet\data\processed\train\keeshond\keeshond_140.jpg`（500×375）
- B：`test` / keeshond / `E:\CatDogBreedNet\data\processed\test\keeshond\keeshond_97.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99998；灰度 MAE 0.067；RGB MAE 0.087
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（keeshond 同一犬只、同一厨房背景、蓝色项圈，姿态一致）

### #5 pHash 距离 0（复算 0）

- A：`train` / British_Shorthair / `E:\CatDogBreedNet\data\processed\train\British_Shorthair\British_Shorthair_160.jpg`（500×333）
- B：`test` / British_Shorthair / `E:\CatDogBreedNet\data\processed\test\British_Shorthair\British_Shorthair_278.jpg`（500×333）
- MD5 相同：否；灰度相关度 0.99998；灰度 MAE 0.058；RGB MAE 0.069
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（英国短毛猫同一只、同一粉色靠垫背景，头部角度几乎一致）

### #6 pHash 距离 0（复算 0）

- A：`train` / keeshond / `E:\CatDogBreedNet\data\processed\train\keeshond\keeshond_175.jpg`（500×375）
- B：`test` / keeshond / `E:\CatDogBreedNet\data\processed\test\keeshond\keeshond_27.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99998；灰度 MAE 0.059；RGB MAE 0.078
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（keeshond 同一犬只俯身于同一草地，背景花丛一致）

### #7 pHash 距离 0（复算 0）

- A：`train` / keeshond / `E:\CatDogBreedNet\data\processed\train\keeshond\keeshond_152.jpg`（500×375）
- B：`test` / keeshond / `E:\CatDogBreedNet\data\processed\test\keeshond\keeshond_99.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.051；RGB MAE 0.073
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（keeshond 同一犬只趴于同一木地板，前伸姿势一致）

### #9 pHash 距离 0（复算 0）

- A：`train` / leonberger / `E:\CatDogBreedNet\data\processed\train\leonberger\leonberger_189.jpg`（500×334）
- B：`test` / leonberger / `E:\CatDogBreedNet\data\processed\test\leonberger\leonberger_2.jpg`（500×334）
- MD5 相同：否；灰度相关度 0.99998；灰度 MAE 0.076；RGB MAE 0.084
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（leonberger 同一犬只同一仰头角度，背景一致）

### #10 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_188.jpg`（500×375）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_78.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.057；RGB MAE 0.067
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只吐舌，同一门廊背景）

### #11 pHash 距离 0（复算 0）

- A：`train` / keeshond / `E:\CatDogBreedNet\data\processed\train\keeshond\keeshond_141.jpg`（500×375）
- B：`test` / keeshond / `E:\CatDogBreedNet\data\processed\test\keeshond\keeshond_47.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.06；RGB MAE 0.077
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（keeshond 同一犬只趴于同一草地）

### #13 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_140.jpg`（500×375）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_88.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.074；RGB MAE 0.09
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只立于同一泥土地）

### #16 pHash 距离 0（复算 0）

- A：`train` / german_shorthaired / `E:\CatDogBreedNet\data\processed\train\german_shorthaired\german_shorthaired_179.jpg`（500×375）
- B：`test` / german_shorthaired / `E:\CatDogBreedNet\data\processed\test\german_shorthaired\german_shorthaired_19.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.069；RGB MAE 0.1
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（德国短毛指示犬同一犬只吐舌，同一小径背景）

### #20 pHash 距离 0（复算 0）

- A：`train` / german_shorthaired / `E:\CatDogBreedNet\data\processed\train\german_shorthaired\german_shorthaired_150.jpg`（333×500）
- B：`test` / german_shorthaired / `E:\CatDogBreedNet\data\processed\test\german_shorthaired\german_shorthaired_3.jpg`（333×500）
- MD5 相同：否；灰度相关度 0.99995；灰度 MAE 0.058；RGB MAE 0.073
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（德国短毛指示犬同一犬只低头嗅同一彩色球，背景房屋一致）

### #22 pHash 距离 0（复算 0）

- A：`train` / newfoundland / `E:\CatDogBreedNet\data\processed\train\newfoundland\newfoundland_149.jpg`（500×333）
- B：`test` / newfoundland / `E:\CatDogBreedNet\data\processed\test\newfoundland\newfoundland_2.jpg`（500×333）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.07；RGB MAE 0.095
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（纽芬兰犬同一幼犬趴于同一橙色坐垫，客厅背景一致）

### #23 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_137.jpg`（500×428）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_85.jpg`（500×428）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.055；RGB MAE 0.082
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只坐于同一草地，背景灌木一致）

### #24 pHash 距离 0（复算 0）

- A：`train` / Egyptian_Mau / `E:\CatDogBreedNet\data\processed\train\Egyptian_Mau\Egyptian_Mau_186.jpg`（183×275）
- B：`test` / Egyptian_Mau / `E:\CatDogBreedNet\data\processed\test\Egyptian_Mau\Egyptian_Mau_6.jpg`（183×275）
- MD5 相同：否；灰度相关度 0.99985；灰度 MAE 0.285；RGB MAE 1.138
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（埃及猫同一只、同一蓝色展台背景、左上角同一赛事标志）

### #25 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_158.jpg`（500×375）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_81.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.062；RGB MAE 0.085
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只立于同一花纹垫子）

### #26 pHash 距离 0（复算 0）

- A：`train` / keeshond / `E:\CatDogBreedNet\data\processed\train\keeshond\keeshond_162.jpg`（375×500）
- B：`val` / keeshond / `E:\CatDogBreedNet\data\processed\val\keeshond\keeshond_101.jpg`（375×500）
- MD5 相同：否；灰度相关度 0.99996；灰度 MAE 0.064；RGB MAE 0.092
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（keeshond 同一犬只叼同一树枝；注意本对是 train↔val 泄漏，影响验证集选模）

### #27 pHash 距离 0（复算 0）

- A：`train` / leonberger / `E:\CatDogBreedNet\data\processed\train\leonberger\leonberger_187.jpg`（396×500）
- B：`test` / leonberger / `E:\CatDogBreedNet\data\processed\test\leonberger\leonberger_1.jpg`（396×500）
- MD5 相同：否；灰度相关度 0.99997；灰度 MAE 0.055；RGB MAE 0.076
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（leonberger 同一犬只同一头部特写）

### #28 pHash 距离 0（复算 0）

- A：`train` / german_shorthaired / `E:\CatDogBreedNet\data\processed\train\german_shorthaired\german_shorthaired_180.jpg`（375×500）
- B：`test` / german_shorthaired / `E:\CatDogBreedNet\data\processed\test\german_shorthaired\german_shorthaired_20.jpg`（375×500）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.076；RGB MAE 0.115
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（德国短毛指示犬同一犬只与同一红蓝球，人手入镜一致）

### #29 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_176.jpg`（375×500）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_20.jpg`（375×500）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.055；RGB MAE 0.076
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只（穿同款毛衣）坐于同一棕色沙发）

### #33 pHash 距离 0（复算 0）

- A：`train` / British_Shorthair / `E:\CatDogBreedNet\data\processed\train\British_Shorthair\British_Shorthair_186.jpg`（500×375）
- B：`test` / British_Shorthair / `E:\CatDogBreedNet\data\processed\test\British_Shorthair\British_Shorthair_271.jpg`（636×477）
- MD5 相同：否；灰度相关度 0.99993；灰度 MAE 6.327；RGB MAE 6.352
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（英国短毛猫同一只、琥珀色眼睛、同一趴姿（取景略不同））

### #34 pHash 距离 0（复算 0）

- A：`train` / Bombay / `E:\CatDogBreedNet\data\processed\train\Bombay\Bombay_146.jpg`（220×165）
- B：`test` / Bombay / `E:\CatDogBreedNet\data\processed\test\Bombay\Bombay_82.jpg`（240×180）
- MD5 相同：否；灰度相关度 0.99969；灰度 MAE 2.271；RGB MAE 2.563
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（孟买猫同一只黑猫趴于同花纹沙发，嘴里同叼一物）

### #35 pHash 距离 0（复算 0）

- A：`train` / Egyptian_Mau / `E:\CatDogBreedNet\data\processed\train\Egyptian_Mau\Egyptian_Mau_138.jpg`（448×336）
- B：`test` / Egyptian_Mau / `E:\CatDogBreedNet\data\processed\test\Egyptian_Mau\Egyptian_Mau_219.jpg`（448×336）
- MD5 相同：否；灰度相关度 0.99997；灰度 MAE 0.181；RGB MAE 1.257
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（埃及猫同一幼猫伸懒腰于同一条纹床品）

### #36 pHash 距离 0（复算 0）

- A：`train` / japanese_chin / `E:\CatDogBreedNet\data\processed\train\japanese_chin\japanese_chin_187.jpg`（500×375）
- B：`test` / japanese_chin / `E:\CatDogBreedNet\data\processed\test\japanese_chin\japanese_chin_200.jpg`（500×375）
- MD5 相同：否；灰度相关度 0.99999；灰度 MAE 0.053；RGB MAE 0.074
- 初步分级：**极可能为同一照片的变体（pHash 完全相同）**
- 依据：pHash 距离为 0，两张图的感知哈希逐位相同
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（日本狆同一犬只吐舌立于同一门前）

### #44 pHash 距离 4（复算 4）

- A：`train` / newfoundland / `E:\CatDogBreedNet\data\processed\train\newfoundland\newfoundland_172.jpg`（500×333）
- B：`test` / newfoundland / `E:\CatDogBreedNet\data\processed\test\newfoundland\newfoundland_2.jpg`（500×333）
- MD5 相同：否；灰度相关度 0.90957；灰度 MAE 18.089；RGB MAE 18.774
- 初步分级：**需人工确认（pHash 距离 4）**
- 依据：像素相关度 0.90957，证据不充分，必须人工目检
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（纽芬兰犬同一幼犬趴于同一橙色坐垫，取景与缩放不同）

### #45 pHash 距离 4（复算 4）

- A：`train` / Abyssinian / `E:\CatDogBreedNet\data\processed\train\Abyssinian\Abyssinian_151.jpg`（350×233）
- B：`test` / Abyssinian / `E:\CatDogBreedNet\data\processed\test\Abyssinian\Abyssinian_99.jpg`（450×299）
- MD5 相同：否；灰度相关度 0.98288；灰度 MAE 2.81；RGB MAE 3.198
- 初步分级：**很可能为同一照片的变体（pHash 距离 4）**
- 依据：像素相关度 0.983 ≥ 0.9 且平均灰度差 2.81 ≤ 12.0
- 联系表：`None`
- 目视核验：**同一照片变体（构成泄漏）**（阿比西尼亚猫同一只坐于同一柳条家具旁，两张均带同一 superstock.com 水印（同一张库存照片））

## 划分内部的近重复（不构成跨集合泄漏，仅记录）

| # | 集合 | 品种 | pHash 距离 | 灰度相关度 |
|---|---|---|---|---|
| 2 | test/test | japanese_chin | 0 | 0.99999 |
| 4 | train/train | Bombay | 0 | 0.98225 |
| 8 | train/train | Abyssinian | 0 | 0.99979 |
| 12 | train/train | keeshond | 0 | 0.99999 |
| 14 | train/train | keeshond | 0 | 0.99999 |
| 15 | test/test | Bombay | 0 | 0.99998 |
| 17 | test/test | Birman | 0 | 0.99997 |
| 18 | train/train | Bombay | 0 | 0.99992 |
| 19 | train/train | Abyssinian | 0 | 0.99984 |
| 21 | test/test | scottish_terrier | 0 | 0.99978 |
| 30 | test/test | Abyssinian | 0 | 0.9999 |
| 31 | train/train | Bombay | 0 | 0.99994 |
| 32 | train/train | Bombay | 0 | 0.99994 |
| 37 | test/test | Bombay | 0 | 0.99997 |
| 38 | test/test | Abyssinian | 0 | 0.99485 |
| 39 | train/train | Bombay | 0 | 0.99997 |
| 40 | test/test | Abyssinian | 2 | 0.99745 |
| 41 | train/train | boxer | 2 | 0.97917 |
| 42 | train/train | Bombay | 2 | 0.99872 |
| 43 | train/train | newfoundland | 4 | 0.90962 |
