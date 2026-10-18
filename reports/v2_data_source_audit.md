# V2 数据源审核报告（U3）

> 生成时间：2026-10-18T09:14:16.565546+00:00
> 阶段：MODEL_UPGRADE_PLAN **U3 — V2 数据源审查与准备**
> 本阶段**不训练模型**，不修改 V1.1 正式模型、V1 备份与既有数据目录。

## 1. 审核结论摘要

| 数据源 | 实测可达性 | 许可状态 | 结论 |
|---|---|---|---|
| Stanford Dogs | 可达（HTTP 200） | 源页面未声明独立许可证（正文无 license 段落）；上游 ImageNet | **有条件通过（本地非商业教育研究用途）** |
| Oxford-IIIT Pet | 既有本地数据 | CC BY-SA 4.0（项目既有 37 类数据来源） | 采用（既有基线，本阶段不重新下载） |
| CatInBeard（HuggingFace） | **401 Unauthorized** | 无法核实（接口返回 401，未取得任何元数据） | **排除（需授权凭据，无法审核）** |
| COCO | https 证书失败；http 可达 | COCO 自身有使用条款；但其类别体系为 80 个通用物体类 | **排除（无品种细分标签，不适用于品种分类）** |
| afifizzul/cat-breeds | 可达 | cc0-1.0（HF 元数据声明） | **排除（仅 1 类 Birman，已在现有 37 类中，无新增品种价值）** |
| harish03/catbreed | 可达 | apache-2.0（HF 元数据声明），但加载脚本 _LICENSE 为空 | **排除（类别为野生猫科动物，非家猫品种；自述 demo 数据集；三个 split 复用同一迭代器，必然跨集合重复）** |

**唯一通过审核、可用于新增品种的数据源是 Stanford Dogs。**
其余来源均因「需授权」「无品种标签」「无新增品种」「类别不符」被排除，详见第 3 节逐源说明。

## 2. Stanford Dogs 详审（唯一通过项）

- 官方主页：http://vision.stanford.edu/aditya86/ImageNetDogs/
- 官方声明规模：**120 类 / 20,580 张**
- 实际解包规模：**120 类 / 20,580 张**（与官方声明一致）
- 标注：类别标签 + 边界框
- 官方划分：官方 train 12,000 张（每类 100）/ test 8,580 张
- **许可状态**：源页面未声明独立许可证（正文无 license 段落）
- **上游来源**：由 ImageNet 图片与标注构建
- **适用条款**：ImageNet 使用条款：仅限非商业研究与教育用途；不得再分发原始图片；引用 Khosla et al. (FGVC@CVPR 2011) 与 Deng et al. (CVPR 2009)
- **审核结论**：有条件通过（本地非商业教育研究用途）

### 2.1 使用限制（必须遵守）

- 仅用于本项目（本科毕业设计）的非商业研究与教育目的
- 原始压缩包、解包图片与处理后图片全部留在 Git 忽略目录，不提交、不作为公开附件分发
- 论文与文档中必须引用上述两篇论文
- 不得声称拥有图片版权或可自由再分发

### 2.2 下载文件与校验信息

| 文件 | 字节数 | 服务器 Content-Length | 大小一致 | 本地 SHA256（完整性指纹） |
|---|---|---|---|---|
| `images.tar` | 793,579,520 | 793579520 | True | `a443fc2f9a851aa1a7b8e4fa4af94b84…` |
| `lists.tar` | 481,280 | 481280 | True | `34b47cacd9a98b5d150e084f24d29391…` |
| `annotation.tar` | 21,852,160 | 21852160 | True | `662ed36f707be6b195c2fda392d8e153…` |

> **哈希口径说明（重要）**：官方**未发布**可核对的 SHA256。
> 上表的 SHA256 是**本地完整性指纹**，只用于确认文件未损坏、两次下载一致，
> **不能**用它独立证明文件来源真实性。
> 可核对的官方信息是**服务器 `Content-Length`**（已逐文件比对一致）以及服务器 `Last-Modified`：
> - `images.tar`：`Thu, 20 Oct 2011 22:38:12 GMT`
> - `lists.tar`：`Tue, 17 Jan 2012 22:53:00 GMT`
> - `annotation.tar`：`Mon, 24 Oct 2011 03:46:41 GMT`

### 2.3 解包后的实际统计

- 类别目录数：**120**
- 图片总数：**20,580**
- 总字节：777,706,781（741.7 MiB）
- 每类图片数：min **148** / max **252** / mean 171.5

> 官方声明与本机解包结果一致，说明下载完整、未损坏。

### 2.4 Border Collie 核实（用户重点要求）

| 项目 | 值 |
|---|---|
| Stanford 标签 | `n02106166-Border_collie` |
| 标准标签（canonical） | `border_collie` |
| 中文名 | 边境牧羊犬 |
| 总图片数 | **150** |
| 官方 train / test | 100 / 50 |
| 是否新增品种 | **是**（不在现有 37 类中） |

> **细粒度陷阱提示**：Stanford Dogs 中同时存在 `Border_terrier`（边境梗，172 张）、
> `collie`（柯利牧羊犬，153 张）与 `Border_collie`（边境牧羊犬，150 张），
> 这是**三个不同品种**，不得合并。

## 3. 逐源审核与排除理由

### 3.1 CatInBeard/cat-breeds-dataset（HuggingFace）

- 用途预期：补充家猫品种
- **实测**：数据集页与 API 均返回 **HTTP 401**，响应体 `{"error":"Invalid username or password."}`
- **结论**：**排除**。未取得访问授权，无法核对 README / LICENSE /
  images_metadata.csv，也无法核对每张图片的作者、原始来源与许可。
- 若后续取得访问凭据，可按同一审核流程重新评估。

### 3.2 COCO

- 用途预期：补充猫狗图片
- **实测**：`https://images.cocodataset.org` SSL 证书验证失败；
  `http://images.cocodataset.org` 可达
- **结论**：**排除**。COCO 是通用目标检测数据集，类别体系为 80 个物体类，
  仅有 `cat` / `dog` 两个粗粒度类，**没有品种标签**，无法用于品种分类扩充。

### 3.3 afifizzul/cat-breeds（HuggingFace）

- 用途预期：补充家猫品种
- **实测**：公开可访问，license `cc0-1.0`，imagefolder 格式，**仅 200 张图片、1 个类别（Birman）**
- **结论**：**排除**。Birman 已在现有 37 类中，无新增品种价值。

### 3.4 harish03/catbreed（HuggingFace）

- 用途预期：补充家猫品种
- **实测**：公开可访问，license `apache-2.0`，`images.tar.gz`（29 MB）
- **类别**：`AFRICAN_LEOPARD`、`CARACAL`、`CHEETAH`、`CLOUDED_LEOPARD`、
  `JAGUAR`、`LION`、`OCELOT`、`PUMA`、`SNOW_LEOPARD`、`TIGER`
- **结论**：**排除**。三个独立原因：
  1. 类别为**野生猫科动物**，不是家猫品种，超出本项目「猫狗品种」范围；
  2. 自述为 `Demo dataset for testing or showing image-classification capabilities`；
  3. 加载脚本的 `_split_generators` 让 train/test/validation 三个 split 
     复用同一迭代器，必然产生跨集合重复。

### 3.5 Oxford-IIIT Pet Dataset

- **结论**：采用（既有基线，本阶段不重新下载）
- 现有 37 类（12 猫 + 25 狗）继续作为标准标签参考与历史基准；
  本阶段**不重新下载、不修改** `data/processed/` 与 `data/processed_clean/`。

## 4. 实测端点明细

| 端点 | 方法 | 结果 | Content-Length | 耗时 |
|---|---|---|---|---|
| Stanford Dogs 官方主页 | HEAD | HTTP 200 | 8,439 | 1.82s |
| Stanford Dogs images.tar | HEAD | HTTP 200 | 793,579,520 | 1.62s |
| Stanford Dogs lists.tar | HEAD | HTTP 200 | 481,280 | 1.63s |
| Stanford Dogs annotation.tar | HEAD | HTTP 200 | 21,852,160 | 1.64s |
| CatInBeard 数据集页 | HEAD | HTTP 401 Unauthorized | — | 2.11s |
| CatInBeard 数据集 API | HEAD | HTTP 401 Unauthorized | — | 1.84s |
| afifizzul/cat-breeds API | HEAD | HTTP 200 | 8,043 | 1.96s |
| harish03/catbreed API | HEAD | HTTP 200 | 816 | 1.95s |
| COCO 图片站（https） | HEAD | 失败：URLError: <urlopen error [SSL: CERTIFICA | — | 1.9s |
| COCO 图片站（http） | HEAD | HTTP 200 | — | 1.7s |
| Oxford-IIIT Pet 官网 | HEAD | HTTP 200 | — | 2.98s |

> 上表为本次运行的实际探测结果；网络环境变化可能导致可达性不同。

## 5. 许可与合规声明

1. **Stanford Dogs 为 ImageNet 衍生数据集**，官方页面未声明独立许可证。
   本项目仅将其用于**本地非商业教育研究**（本科毕业设计），不对外分发。
2. 所有原始压缩包、解包图片与后续处理图片均位于 **Git 忽略目录**
   （`data/external_raw/`、`data/v2_processed/`），**不进入版本库、
   不作为公开附件分发**。
3. 若后续需要公开发布模型或数据集衍生物，必须先重新评估 ImageNet 条款，
   **不得**默认图片可自由再分发。
4. 论文与文档中必须引用：
   - 由 ImageNet 图片与标注构建（Deng et al., CVPR 2009）
   - Khosla, Jayadevaprakash, Yao, Fei-Fei. *Novel dataset for Fine-Grained Visual Categorization.* FGVC @ CVPR 2011.

## 6. 复现方式

```powershell
cd E:\CatDogBreedNet
# 1) 下载并校验（幂等，已存在且大小一致则跳过）
.venv\Scripts\python.exe scripts\fetch_stanford_dogs.py
# 2) 重新生成本审核报告
.venv\Scripts\python.exe scripts\audit_v2_data_sources.py
# 3) 生成类别目录
.venv\Scripts\python.exe scripts\build_v2_class_catalog.py
```
