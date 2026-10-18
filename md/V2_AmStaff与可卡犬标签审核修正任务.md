# V2.1 标签口径修正、AmStaff 纳入与数据集复核任务

> 项目：`E:\CatDogBreedNet`  
> 阶段：V2 数据准备修订（U3.1）  
> 本任务只修改标签规则、V2 数据、校验结果和相关报告；**不训练模型，不切换当前正式模型**。

## 1. 任务目标

根据人工审核结果修正 V2 犬种标签口径，之后重新构建 V2 数据集并完整执行质量和防泄漏验证。

最终原则：

1. 原有 Oxford-IIIT Pet 的 37 类及其数据保持不变。
2. Stanford Dogs 中的 `Border_collie`（边境牧羊犬）必须作为独立类别，不能与 `collie`（柯利牧羊犬）或 `Border_terrier`（边境梗）合并。
3. 将 `American_Staffordshire_terrier`（American Staffordshire Terrier，AmStaff，美国斯塔福郡梗）纳入 V2，作为**独立新增类别**。
4. 原有 `american_pit_bull_terrier`（American Pit Bull Terrier，APBT，美国比特斗牛梗）保持独立；不得把 AmStaff 当作 APBT 的别名，也不得将两类图片合并。
5. Stanford Dogs 中标签含糊的 `cocker_spaniel` 继续排除，不将它猜测性地重标为 American Cocker Spaniel 或 English Cocker Spaniel。
6. Oxford 原有 `english_cocker_spaniel`（英国可卡犬）类别、标签及图片完整保留，不与 Stanford 的 `cocker_spaniel` 合并。
7. 修正数据质量报告对犬种匹配关系的描述，使报告、类别目录、排除清单、数据集 manifest 和实际数据目录一致。

## 2. 分类依据与口径说明

### 2.1 AmStaff 与 APBT

本项目按明确的犬种标签及选定的犬种登记口径组织分类。AmStaff 在本次 V2 中单独成类；APBT 保留原标签和原始数据。两者可能存在外观相似、历史来源相关或不同登记体系界定不一致的情况，但不能仅凭外观相似就合并标签。

**标注执行规则：**

- Stanford Dogs 来源目录 `n02093428-American_Staffordshire_terrier`（实际目录名以本地解包结果为准）映射到新的 canonical label `american_staffordshire_terrier`。
- 中文显示名统一为“美国斯塔福郡梗”；如项目现有中文名规范使用其他译名，先检查并统一全项目使用，不得同一类别多个名称。
- 不把 `american_staffordshire_terrier` 加入 `american_pit_bull_terrier` 的 alias 列表。
- 不移动、不重命名、不重新标注 `data/processed_clean/` 中 APBT 的文件。
- 不因 AmStaff 与 APBT 外观相似而擅自删除图像；按来源标注处理，并照常做完全重复、近重复及图像质量检查。
- 在数据源/类别审核文档中简要注明：AmStaff 与 APBT 在部分登记体系和日常用语中存在边界差异；本项目选择按独立犬种标签分别分类。这属于项目分类口径，不要声称所有组织都采用相同定义。

> 注意：如本地 Stanford 解包目录名与上面的示例不一致，以实际目录和源标签为准，先检查再修改；不得根据猜测硬编码错误目录名。

### 2.2 Cocker Spaniel 与 English Cocker Spaniel

- Stanford Dogs 的 `cocker_spaniel` 标签本身没有充分说明是美国可卡犬还是英国可卡犬。
- 本轮将该 Stanford 类别保留在排除规则中，原因写为 `excluded_ambiguous_naming`，并明确说明“来源标签无法可靠区分美式/英式可卡犬；不进行猜测性重标”。
- Oxford 原有 `english_cocker_spaniel` 类别继续保留，不改名、不删除、不与 `cocker_spaniel` 合并。
- 不得仅根据图像外观，把 Stanford 的 `cocker_spaniel` 改为美国可卡犬或英国可卡犬。
- 只有未来取得具有明确来源和明确标注的 American Cocker Spaniel 数据时，才另行评估是否新增美国可卡犬类别；本任务不搜索或引入新数据源。

## 3. 预期类别数量

当前审核结果是 135 个有效类别（原有 37 类 + 98 个新增犬种），类别目录中另外记录了 2 个被排除候选类别。

本次将 AmStaff 从排除候选改为有效类别，而 `cocker_spaniel` 继续排除。因此，预期为：

- **最终有效类别数：136 类**；
- 原有类别：37 类，必须保持原样；
- 新增有效类别：99 类；
- 排除的歧义候选类别：至少保留 `cocker_spaniel` 这一项；
- `american_staffordshire_terrier` 在 train、val、test 三个 split 中都必须出现。

以上为目标值。重建后必须从实际数据和 manifest 计算类别数、图像数，不得为了匹配目标数而虚构样本或手工填数。如果计算结果不是 136 类，先查明并报告具体差异，不允许带着不一致结果进入后续训练阶段。

## 4. 必须检查和修改的文件

先阅读当前文件及相关脚本，按实际内容做最小修改，不得盲目全文替换。

### 4.1 类别目录与构建规则

- `scripts/build_v2_class_catalog.py`
- `reports/v2_class_catalog.csv`
- `reports/v2_class_catalog.json`

要求：

1. 增加 `american_staffordshire_terrier` 的 canonical label、源标签、中文名、纳入状态和来源信息。
2. 不把 AmStaff 配置为 APBT 的 alias。
3. 将 `cocker_spaniel` 保持为排除候选，并给出明确、稳定、可复现的排除原因。
4. 检查 `scottish_terrier` 与 `Scotch_terrier` 的别名映射。若当前目录已有 `verified_alias` 且实际规则正确，应保留，不要回退或重复创建类别。
5. 检查 `border_collie`、`collie`、`border_terrier` 三类映射，必须是三个不同的 canonical label。
6. 类别目录应明确区分有效类别与排除候选，避免把目录行数误报为有效类别总数。

### 4.2 数据构建及校验脚本

- `scripts/build_v2_dataset.py`
- `scripts/verify_v2_dataset.py`
- 如有必要，仅修改与本任务直接相关的测试文件。

要求：

1. 将 AmStaff 的有效图像纳入 V2，并按现有可复现的分层/近重复簇原子分配规则划分 train/val/test。
2. 保持 Stanford 同一犬种中近重复图片簇不可跨 split 的规则。
3. `cocker_spaniel` 继续不进入任何有效 split。
4. V2 原有 37 类继续从 `data/processed_clean/` 使用现有数据构建，不能重新标注、删图或覆盖原目录。
5. 不要将 Stanford 中已与原有类别重叠的犬种图片额外混入原类别，除非当前既定构建逻辑已经明确允许且本任务有依据；本任务不应改变其余 37 类的数据策略。
6. 对异常样本、完全重复样本和近重复样本重新计算，不要沿用修改前的旧统计数字。
7. 如果发现新旧测试集之间的 pHash 近重复，必须先分析并报告，不得静默忽略或通过删除原有测试图片来让校验通过。

### 4.3 报告和清单

- `reports/v2_data_source_audit.md`
- `reports/v2_data_quality_report.md`
- `reports/v2_class_counts.csv`
- `reports/v2_exclusion_manifest.csv`
- `data/v2_processed/manifest.json`

要求：

1. 重建或更新以上由脚本产出的报告/清单，避免只手工改报告却不改生成逻辑。
2. AmStaff 不得继续被列为 `excluded_ambiguous_naming`；`cocker_spaniel` 应保留为此类排除项。
3. 更新排除原因数量、有效类别数、图片数、各 split 数量、每类样本量、质量检查和防泄漏统计。
4. 修正 `v2_data_quality_report.md` 关于 Oxford 与 Stanford 犬种匹配的过时/不准确文字：
   - `scottish_terrier` 与 `Scotch_terrier` 当前若已通过验证别名对应，应描述为匹配，不要再称其因命名歧义而未匹配。
   - `american_pit_bull_terrier` 不与 AmStaff 合并；应说明原有 APBT 保留，而 Stanford AmStaff 按独立标签纳入。
   - `english_cocker_spaniel` 保留原有类；Stanford `cocker_spaniel` 因标签不明确而排除。
   - 对 `american_bulldog`、`havanese`、`shiba_inu` 等真正没有对应 Stanford 类别的原有类别，按实际类别目录和构建代码准确说明。
5. 报告要区分“类别目录候选行数”和“最终有效类别数”。最终有效类别数应从实际 manifest/数据目录中计算。
6. 许可说明沿用当前审查结论：Stanford Dogs 是 ImageNet 衍生数据集，官方页面未声明独立许可证；本项目按已审核的本地非商业教育研究用途处理，不公开再分发原始图片或处理图片。论文需要按现有审核报告要求引用数据集论文。不得宣称图片可自由再分发。

## 5. 数据保护和禁止操作（必须遵守）

本项目之前发生过批量回退/覆盖导致文件被清空或截断的问题，因此本任务必须优先保护现有成果。

### 严禁

- **严禁训练任何模型**；不得启动训练脚本、长时间训练任务或任何可能覆盖 checkpoint 的流程。
- 不得覆盖、删除或重命名 `artifacts/best_model.pth`。
- 不得修改或删除 `artifacts/backup_v1_20261018/` 中的备份。
- 不得修改正式 V1.1 模型、模型版本号或生产加载指向。
- 不得修改或删除 `data/processed/`、`data/processed_clean/` 原有数据。
- 不得删除、清空、重建或迁移 SQLite 数据库、上传记录或用户上传图片；例如不得触碰现有数据库及 `uploads/` 目录。
- 不得批量清空目录，不得运行 `git reset --hard`、`git clean -fd`、大范围 `git checkout -- .`、大范围 revert，或其他会丢弃用户现有修改的命令。
- 不得通过删除原有测试集图片来解决泄漏检查问题。
- 不得把数据集原始图片或处理后的图片添加到 Git 版本库或提交到公开附件中。

### 必须执行的保护步骤

1. 修改前先运行并记录 `git status --short`、当前分支和最近提交；检查是否存在用户未提交修改。
2. 检查所有待改文件当前内容，逐项小范围编辑。遇到非预期改动、文件为空、内容异常或和任务预期不符时，先停止相关修改并报告，不得自行大范围恢复。
3. V2 处理数据只能写入 `data/v2_processed/`；原始 Stanford 数据只读使用，通常位于 `data/external_raw/`。
4. 若需要重建 `data/v2_processed/`，先确认目标目录确实是 V2 生成目录，并核对路径；不得把清理操作应用于任何其他目录。优先采用项目脚本已有的安全、可复现流程。
5. 任务结束再次检查 `git status --short`、文件差异与关键文件是否存在。不得自动提交，除非项目负责人另行要求。

## 6. 执行顺序

### 阶段 A：检查现状

1. 查看 Git 状态、当前分支、最新提交。
2. 阅读本任务列出的脚本和报告，以及当前测试对类别数、目录和 manifest 的假设。
3. 确认 Stanford 解包目录中 AmStaff 与 `cocker_spaniel` 的真实目录名和样本数。
4. 记录本次修改前 V2 manifest、旧数据目录和正式模型 checkpoint 的存在状态；**不打开或改写 checkpoint，不进行训练**。

### 阶段 B：最小修改规则

1. 仅将 AmStaff 从排除候选调整为独立有效类别。
2. 保留 APBT 原有类别，不加 AmStaff alias。
3. 继续排除未明确细分的 Stanford `cocker_spaniel`。
4. 保留边境牧羊犬、柯利牧羊犬、边境梗的三分类关系。
5. 修正 Scottish/Scotch Terrier 匹配说明及 Oxford/Stanford 其他犬种对应说明。
6. 更新/补齐测试，确保上述标签规则不被后续改动意外破坏。

### 阶段 C：重建 V2 数据

1. 使用项目现有虚拟环境和脚本执行类别目录生成、数据构建。
2. 在构建前检查脚本目标路径，确保不会修改旧数据目录。
3. 让构建脚本重新计算去重、近重复簇、split 分配和所有统计。
4. 如果构建失败，不要使用旧统计数字伪装成功；保留日志并报告实际失败步骤。

项目根目录和解释器：

```powershell
cd E:\CatDogBreedNet
.venv\Scripts\python.exe scripts\build_v2_class_catalog.py
.venv\Scripts\python.exe scripts\build_v2_dataset.py
.venv\Scripts\python.exe scripts\verify_v2_dataset.py
```

> 上述命令只在确认脚本没有隐含训练操作、输出路径正确后执行。若脚本接口或参数已经变化，以实际代码为准；不要猜参数，不要运行任何训练脚本。

### 阶段 D：测试与报告核对

1. 运行项目测试：

   ```powershell
   cd E:\CatDogBreedNet
   .venv\Scripts\python.exe -m pytest tests/
   ```

2. 如果测试失败，先区分是否由本次标签口径变更引起；只修复与本任务有关的问题。
3. 逐项核对类别目录、排除清单、manifest、每类数量表、质量报告中的数字和文字一致。
4. 检查关键类别在 train/val/test 中的数量，不能只有一个 split 有样本。
5. 检查 V2 内部 MD5 完全重复和 pHash 近重复没有跨 split；检查 V2 新增数据与旧测试集之间是否出现近重复。
6. 对 `border_collie`、`collie`、`border_terrier` 抽查标签及样本路径，确认三类仍互相独立。
7. 检查 AmStaff 样本路径都进入 `american_staffordshire_terrier`，没有进入 APBT；检查 `cocker_spaniel` 没有进入有效 split。

## 7. 验收标准

只有全部满足以下条件，任务才算完成：

- [ ] 最终 V2 有效类别数为 136；如果实际不符，已定位原因并暂停后续阶段，不以手工改数掩盖问题。
- [ ] 原有 37 类的标签和 `data/processed_clean/` 数据完整、未改变。
- [ ] `american_staffordshire_terrier` 是独立有效类别，train/val/test 均有样本。
- [ ] `american_pit_bull_terrier` 保留原有类别，不与 AmStaff 合并或互设别名。
- [ ] Stanford `cocker_spaniel` 继续被排除；Oxford `english_cocker_spaniel` 完整保留。
- [ ] `border_collie`、`collie`、`border_terrier` 是三个独立类别。
- [ ] `scottish_terrier` / `Scotch_terrier` 的别名规则和报告说明一致。
- [ ] 类别数、各 split 总量、逐类数量、排除清单、manifest 和报告统计一致。
- [ ] 图片解码失败数、低分辨率数、MD5 重复和 pHash 近重复统计均由本次运行重新生成。
- [ ] MD5 完全重复图片不跨 split；pHash 阈值按现有脚本规则执行且近重复簇整体分配到单一 split。
- [ ] 没有通过删除或覆盖旧测试集图片来通过防泄漏检查。
- [ ] `pytest tests/` 全部通过；若未通过，准确列出失败测试和原因，不得声称通过。
- [ ] 未训练模型；正式 V1.1 checkpoint、V1 备份、数据库、uploads 及前端文件未改变。
- [ ] Git 状态和最终差异已核对；没有执行大范围回退、清理或自动提交。

## 8. 完成后给用户的报告格式

Agent 完成后，应输出：

1. **改动文件清单**：每个脚本/报告修改的原因。
2. **类别结果**：最终有效类别数、原有/新增类别数、AmStaff 数量及 train/val/test 分布。
3. **歧义类别处理**：确认 AmStaff 已纳入且独立于 APBT；`cocker_spaniel` 仍被排除；English Cocker 保留。
4. **数据质量与防泄漏结果**：坏图、低分辨率、MD5 重复、pHash 近重复、跨 split 和新旧测试集比较结果。
5. **测试结果**：通过/失败数量及失败详情。
6. **保护检查**：明确确认未训练、未修改旧数据、未覆盖任何模型 checkpoint、未触碰数据库或 uploads。
7. **未解决事项**：所有无法确认或不符合验收标准的内容，必须明示；不得自行推断完成。

**本任务完成后仍不要启动 V2 训练。** 先把结果、报告和数据统计交给项目负责人复核，再决定是否进入训练阶段。
