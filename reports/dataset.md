# 数据集报告：Oxford-IIIT Pet Dataset

> 本文件记录数据集的真实来源、许可、引用与划分方案。所有数字来自 2026-10-12 的实际下载与统计，可复现。

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 数据集名称 | Oxford-IIIT Pet Dataset（Oxford-IIIT 宠物数据集） |
| 官方主页 | https://www.robots.ox.ac.uk/~vgg/data/pets/ |
| 实际下载地址 | https://thor.robots.ox.ac.uk/pets/images.tar.gz（由官方页重定向） |
| 下载日期 | 2026-10-12 |
| 类别数 | 37（12 个猫品种 + 25 个狗品种） |
| 图片总数 | 7349 张 |
| 标注内容 | 品种标签（list.txt）、官方 trainval/test 划分、头部边界框（xmls）、像素级 trimap |

## 2. 下载文件与校验

| 文件 | 大小（字节） | MD5 | 服务器 Content-Length |
|---|---|---|---|
| images.tar.gz | 791,918,971 | `5c4f3ee8e5d25df40f4fd59a7f44e54c` | 791,918,971（一致） |
| annotations.tar.gz | 19,173,078 | `95a8c909bbe2e81eed6a22bccdf3f68f` | 19,173,078（一致） |

说明：官方页面不公布 MD5 校验值。校验依据为：文件大小与服务器 `Content-Length` 完全一致，且 tar 解压过程完整成功（解压失败会直接报错）。MD5 同时记录在 `data/raw/download_manifest.json`。

## 3. 许可（官方 README 原文）

> Dataset is made available for research purposes only. Use of these images must respect the corresponding terms of use of original websites from which they are taken. See [1] for list of websites.

即：数据集仅限研究用途；图片使用须遵守其原始网站的使用条款。论文与系统文档中均已按此声明。

## 4. 引用

官方 README 指定文献：

```bibtex
@inproceedings{parkhi2012cats,
  title     = {Cats and Dogs},
  author    = {Parkhi, O. M. and Vedaldi, A. and Zisserman, A. and Jawahar, C. V.},
  booktitle = {IEEE Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2012}
}
```

## 5. 数据划分方案（如实记录）

- `test` = **官方 test 划分**（3669 张），仅用于最终评估，不参与调参；
- `train`/`val` = **官方 trainval 划分**（3680 张）按类别分层切分：每类取 10%（四舍五入，样本数 ≥10 的类至少保留 1 张验证样本）作为 `val`，其余为 `train`；随机种子 **42**；
- 结果：train 3311 张、val 369 张、test 3669 张；
- 官方 trainval/test 文件每行为 `image_id class_id species breed_id` 四列，只取 image_id。

### 可复现性与泄漏检查（均由 `scripts/prepare_dataset.py` 自动执行）

1. 相同种子（42）重复构建，train 文件清单逐项一致（已验证）；
2. 三个子集的图片 ID 两两无交集（断言）；
3. 三个子集的图片内容 MD5 两两无重复（断言，防同图不同名泄漏）；
4. 三个子集的类别集合完全一致，类别到索引映射（ImageFolder 按类名字母序）一致（断言）；
5. 每个类别在 train/val/test 中均有样本（见统计表）。

## 6. 类别统计（实际运行输出）

| class | train | val | test |
|---|---|---|---|
| Abyssinian | 90 | 10 | 98 |
| Bengal | 90 | 10 | 100 |
| Birman | 90 | 10 | 100 |
| Bombay | 86 | 10 | 88 |
| British_Shorthair | 90 | 10 | 100 |
| Egyptian_Mau | 84 | 9 | 97 |
| Maine_Coon | 90 | 10 | 100 |
| Persian | 90 | 10 | 100 |
| Ragdoll | 90 | 10 | 100 |
| Russian_Blue | 90 | 10 | 100 |
| Siamese | 89 | 10 | 100 |
| Sphynx | 90 | 10 | 100 |
| american_bulldog | 90 | 10 | 100 |
| american_pit_bull_terrier | 90 | 10 | 100 |
| basset_hound | 90 | 10 | 100 |
| beagle | 90 | 10 | 100 |
| boxer | 90 | 10 | 99 |
| chihuahua | 90 | 10 | 100 |
| english_cocker_spaniel | 86 | 10 | 100 |
| english_setter | 90 | 10 | 100 |
| german_shorthaired | 90 | 10 | 100 |
| great_pyrenees | 90 | 10 | 100 |
| havanese | 90 | 10 | 100 |
| japanese_chin | 90 | 10 | 100 |
| keeshond | 90 | 10 | 99 |
| leonberger | 90 | 10 | 100 |
| miniature_pinscher | 90 | 10 | 100 |
| newfoundland | 86 | 10 | 100 |
| pomeranian | 90 | 10 | 100 |
| pug | 90 | 10 | 100 |
| saint_bernard | 90 | 10 | 100 |
| samoyed | 90 | 10 | 100 |
| scottish_terrier | 90 | 10 | 99 |
| shiba_inu | 90 | 10 | 100 |
| staffordshire_bull_terrier | 90 | 10 | 89 |
| wheaten_terrier | 90 | 10 | 100 |
| yorkshire_terrier | 90 | 10 | 100 |
| **TOTAL** | **3311** | **369** | **3669** |

机器可读版本：`reports/split_stats.json`、`reports/split_summary.json`。

## 7. 预处理标准（阶段 2 起使用，与训练/推理保持一致）

- RGB 三通道、224×224；
- ImageNet mean `[0.485, 0.456, 0.406]`、std `[0.229, 0.224, 0.225]`；
- 训练可用适度随机增强（水平翻转、轻微旋转）；验证/测试/线上推理不使用随机增强；
- 配置集中在 `ml/config.py`。

## 8. 已知数据情况

- 数据存在一定类别不平衡（如 Bombay train 86、Egyptian_Mau train 84），幅度不大，暂不做重采样，训练时如实记录；
- 个别图片可能损坏或尺寸异常，阶段 2 数据加载时将报告实际发现的坏图数量（不预设结论）。
