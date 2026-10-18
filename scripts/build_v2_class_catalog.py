#!/usr/bin/env python
"""构建 V2 类别目录：标准标签 + 中文名 + 来源 + 许可 + 样本数 + 重叠标记。

用法（在仓库根目录执行）::

    python scripts/build_v2_class_catalog.py
    python scripts/build_v2_class_catalog.py --out-dir reports

前置条件：``scripts/fetch_stanford_dogs.py`` 已下载并解包
``data/external_raw/stanford_dogs/lists/``。

设计原则（对应 MODEL_UPGRADE_PLAN 的标签标准化要求）：

* **不做模糊自动合并**。名称匹配只接受两类：(a) 归一化后完全相等；
  (b) 命中下方**人工核验的高置信别名表**。其余一律进
  ``ambiguous`` / ``unmatched`` 列表交人工确认，绝不静默把两个不同品种合并。
* **细粒度陷阱显式列出**：例如 Stanford 的 ``Border_terrier``（边境梗）、
  ``collie``（柯利牧羊犬）、``Border_collie``（边境牧羊犬）是**三个不同品种**；
  ``American_Staffordshire_terrier`` 与 ``Staffordshire_bullterrier`` 也是两个
  不同品种，均不可与 Oxford 的 ``american_pit_bull_terrier`` 混为一谈。
* **类别数由真实并集决定**，132/140 只是规划参考，不硬编码。
* 本脚本**只读** ``artifacts/class_names.json`` 与 Stanford 标签文件，
  只写 ``reports/v2_class_catalog.{csv,json}``，不碰任何数据目录或权重。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

STANFORD_LISTS = (_REPO_ROOT / "data" / "external_raw" / "stanford_dogs"
                  / "lists")
OXFORD_CLASS_NAMES = _REPO_ROOT / "artifacts" / "class_names.json"
PROCESSED_CLEAN = _REPO_ROOT / "data" / "processed_clean"

STANFORD_CITATION = (
    "Aditya Khosla, Nityananda Jayadevaprakash, Bangpeng Yao, Li Fei-Fei. "
    "Novel dataset for Fine-Grained Image Categorization. FGVC @ CVPR 2011. "
    "(built from ImageNet images and annotations; "
    "secondary citation: Deng et al., ImageNet, CVPR 2009)")
STANFORD_LICENSE = (
    "ImageNet 衍生数据集；官方页面未声明独立许可证。按 ImageNet 使用条款："
    "仅限非商业研究与教育用途，不得再分发，须引用上述论文。")
OXFORD_CITATION = (
    "Oxford-IIIT Pet Dataset (Viswww / Omohundro). "
    "现有 37 类（12 猫 + 25 狗）的标准标签与历史数据来源。")
OXFORD_LICENSE = "Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)"

# ---------------------------------------------------------------------------
# 人工核验的标签映射表
# ---------------------------------------------------------------------------

#: 高置信同义别名：Oxford canonical -> Stanford 标签名。
#: 每一项都是"同一品种的不同叫法"，已逐项人工核对；目标必须存在于 Stanford 清单。
CONFIDENT_ALIASES: dict[str, str] = {
    # Oxford 名称是 ImageNet 全名的截断/别称
    "german_shorthaired": "German_short-haired_pointer",   # 德国短毛指示犬
    "wheaten_terrier": "soft-coated_wheaten_terrier",      # 软毛麦色梗
    "basset_hound": "basset",                              # 巴吉度猎犬
    "japanese_chin": "Japanese_spaniel",                   # 日本狆
    "staffordshire_bull_terrier": "Staffordshire_bullterrier",  # 斯塔福郡斗牛梗
    "leonberger": "Leonberg",                              # 莱昂贝格犬
    # Scotch Terrier 是 Scottish Terrier 的旧同义名（AKC 现行名为
    # Scottish Terrier，历史上称 Scotch Terrier），同一品种，非两个品种。
    "scottish_terrier": "Scotch_terrier",                  # 苏格兰梗
    # 仅大小写差异
    "beagle": "beagle",
    "boxer": "boxer",
    "chihuahua": "Chihuahua",
    "english_setter": "English_setter",
    "great_pyrenees": "Great_Pyrenees",
    "keeshond": "keeshond",
    "miniature_pinscher": "miniature_pinscher",
    "newfoundland": "Newfoundland",
    "pomeranian": "Pomeranian",
    "pug": "pug",
    "saint_bernard": "Saint_Bernard",
    "samoyed": "Samoyed",
    "yorkshire_terrier": "Yorkshire_terrier",
}

#: 歧义别名：Oxford canonical -> 多个 Stanford 候选。
#: **不自动合并**——必须人工确认后才能决定。
#:
#: V2.1 修订：原先涉及的两项歧义已由人工审核全部裁定，故当前为空：
#:   * ``american_pit_bull_terrier`` → Stanford 的 AmStaff 按**独立品种**纳入
#:     （canonical ``american_staffordshire_terrier``），不作为 APBT 的别名；
#:   * ``english_cocker_spaniel``    → Stanford 的 ``cocker_spaniel`` 来源标签
#:     无法可靠区分美式/英式，**保持排除**，不合并。
#: 保留该机制以便将来出现新的歧义时使用，仍坚持"不做模糊自动合并"。
AMBIGUOUS_ALIASES: dict[str, list[str]] = {}

#: 因来源标签无法可靠细分而**不纳入 V2** 的 Stanford 类别。
#: 这些 Stanford 图片仍留在审计目录并计入审计统计，但不进入任何有效 split。
EXCLUDED_STANFORD_CLASSES: dict[str, str] = {
    "cocker_spaniel": (
        "来源标签无法可靠区分美式/英式可卡犬（ImageNet 仅标注为 "
        "cocker_spaniel）；不进行猜测性重标，故本阶段不纳入 V2。"
        "Oxford 的 english_cocker_spaniel 类别完整保留，不与本类合并。"),
}

#: Oxford 犬种在 Stanford 中存在相似类别、但按项目口径**保留独立、不合并**的原因。
#: 与 :data:`EXPECTED_NO_MATCH`（确实没有对应类别）区分开，避免报告含混。
NOT_MERGED_REASONS: dict[str, str] = {
    "american_pit_bull_terrier": (
        "American Pit Bull Terrier（APBT）保留原有类别与原始数据不变；"
        "Stanford 的 American_Staffordshire_terrier（AmStaff）按**独立新增类别**"
        "纳入 V2（canonical: american_staffordshire_terrier），"
        "不作为 APBT 的别名，两类图片不合并"),
    "english_cocker_spaniel": (
        "english_cocker_spaniel 类别完整保留，不改名、不删除；"
        "Stanford 的 cocker_spaniel 因来源标签无法可靠区分美式/英式可卡犬"
        "而保持排除，不与本类合并"),
}

#: 独立纳入的新增品种的补充说明（只影响目录 note 字段，不影响匹配逻辑）。
NEW_BREED_NOTES: dict[str, str] = {
    "American_Staffordshire_terrier": (
        "AmStaff 作为**独立新增类别**纳入 V2（canonical: "
        "american_staffordshire_terrier，中文名：美国斯塔福郡梗）。"
        "与 Oxford 的 american_pit_bull_terrier（APBT）保持独立："
        "两者在部分登记体系与日常用语中存在边界差异，本项目按独立犬种标签"
        "分别分类，不互设别名、不合并图片，也不因外观相似而删除任何图像。"),
}

#: Oxford 37 类中的 12 个猫品种（Stanford Dogs 仅含犬种，故无对应属预期）。
CAT_BREEDS = {
    "Abyssinian", "Bengal", "Birman", "Bombay", "British_Shorthair",
    "Egyptian_Mau", "Maine_Coon", "Persian", "Ragdoll", "Russian_Blue",
    "Siamese", "Sphynx",
}

#: Oxford 37 类中经核对在 Stanford Dogs 无对应的**犬**品种（记录原因，不强行匹配）。
EXPECTED_NO_MATCH = {
    "american_bulldog": "Stanford Dogs（ImageNet 120 犬种）中无 American "
                        "Bulldog synset，仅有 French_bulldog 等",
    "havanese": "Stanford Dogs 中无 Havanese synset",
    "shiba_inu": "Stanford Dogs 中无 Shiba Inu synset（该数据集以西方犬种为主）",
}

#: 中文品种名。前 37 项与 frontend/src/utils/breedNames.js 保持一致；
#: 其余为 Stanford Dogs 新增品种的中文名（U3 阶段建立，供数据管线与报告使用；
#: 前端展示映射的扩展属于 U5 可切换版本集成范围）。
CHINESE_NAMES: dict[str, str] = {
    # --- 12 猫（Oxford 现有）---
    "Abyssinian": "阿比西尼亚猫", "Bengal": "孟加拉猫", "Birman": "伯曼猫",
    "Bombay": "孟买猫", "British_Shorthair": "英国短毛猫",
    "Egyptian_Mau": "埃及猫", "Maine_Coon": "缅因猫", "Persian": "波斯猫",
    "Ragdoll": "布偶猫", "Russian_Blue": "俄罗斯蓝猫", "Siamese": "暹罗猫",
    "Sphynx": "斯芬克斯猫",
    # --- 25 狗（Oxford 现有）---
    "american_bulldog": "美国斗牛犬", "american_pit_bull_terrier": "美国比特斗牛梗",
    "basset_hound": "巴吉度猎犬", "beagle": "比格犬", "boxer": "拳师犬",
    "chihuahua": "吉娃娃", "english_cocker_spaniel": "英国可卡犬",
    "english_setter": "英国塞特犬", "german_shorthaired": "德国短毛指示犬",
    "great_pyrenees": "大白熊犬", "havanese": "哈瓦那犬",
    "japanese_chin": "日本狆", "keeshond": "荷兰毛狮犬",
    "leonberger": "莱昂贝格犬", "miniature_pinscher": "迷你杜宾",
    "newfoundland": "纽芬兰犬", "pomeranian": "博美犬", "pug": "巴哥犬",
    "saint_bernard": "圣伯纳犬", "samoyed": "萨摩耶犬",
    "scottish_terrier": "苏格兰梗", "shiba_inu": "柴犬",
    "staffordshire_bull_terrier": "斯塔福郡斗牛梗",
    "wheaten_terrier": "软毛麦色梗", "yorkshire_terrier": "约克夏梗",
    # --- Stanford Dogs 新增犬种 ---
    "affenpinscher": "猴面梗", "afghan_hound": "阿富汗猎犬",
    "airedale": "艾尔谷梗", "australian_terrier": "澳大利亚梗",
    "african_hunting_dog": "非洲野犬", "appenzeller": "阿彭策尔山犬",
    # AmStaff：与 staffordshire_bull_terrier（斯塔福郡斗牛梗）区分，
    # 采用「美国斯塔福郡梗」作为唯一中文名（全项目统一，不得多名称并存）
    "american_staffordshire_terrier": "美国斯塔福郡梗",
    "basenj": "巴仙吉犬", "basset": "巴吉度猎犬",
    "bedlington_terrier": "贝灵顿梗", "bernese_mountain_dog": "伯恩山犬",
    "black_and_tan_coonhound": "黑褐猎浣熊犬", "blenheim_spaniel": "布伦海姆西班牙猎犬",
    "bloodhound": "寻血猎犬", "bluetick": "蓝斑猎浣熊犬",
    "border_collie": "边境牧羊犬", "border_terrier": "边境梗",
    "borzoi": "苏俄猎狼犬", "boston_bull": "波士顿梗",
    "bouvier_des_flandres": "佛兰德牧牛犬", "brabancon_griffon": "布拉班松格里芬犬",
    "briard": "布里牧羊犬", "brittany_spaniel": "布列塔尼西班牙猎犬",
    "bull_mastiff": "斗牛獒犬", "cairn": "凯恩梗", "cardigan": "卡迪根威尔士柯基犬",
    "chesapeake_bay_retriever": "切萨皮克湾寻回犬", "chihuahua": "吉娃娃",
    "chow": "松狮犬", "clumber": "克伦伯西班牙猎犬",
    "collie": "柯利牧羊犬", "cocker_spaniel": "可卡犬",
    "curly_coated_retriever": "卷毛寻回犬", "dandie_dinmont": "丹迪丁蒙梗",
    "dhole": "豺", "dingo": "澳洲野犬", "doberman": "杜宾犬",
    "english_foxhound": "英国猎狐犬", "english_springer": "英国跳猎犬",
    "entlebucher": "恩特布赫山犬", "eskimo_dog": "爱斯基摩犬",
    "flat_coated_retriever": "平毛寻回犬", "french_bulldog": "法国斗牛犬",
    "german_shepherd": "德国牧羊犬", "german_short_haired_pointer": "德国短毛指示犬",
    "giant_schnauzer": "巨型雪纳瑞", "golden_retriever": "金毛寻回犬",
    "gordon_setter": "戈登塞特犬", "great_dane": "大丹犬",
    "greater_swiss_mountain_dog": "大瑞士山地犬", "groenendael": "格罗安达牧羊犬",
    "ibizan_hound": "伊比赞猎犬", "irish_setter": "爱尔兰塞特犬",
    "irish_terrier": "爱尔兰梗", "irish_water_spaniel": "爱尔兰水猎犬",
    "irish_wolfhound": "爱尔兰猎狼犬", "italian_greyhound": "意大利灵缇",
    "japanese_spaniel": "日本狆", "kelpie": "凯尔皮牧羊犬",
    "kerry_blue_terrier": "凯利蓝梗", "komondor": "可蒙犬",
    "kuvasz": "库瓦兹犬", "labrador_retriever": "拉布拉多寻回犬",
    "lakeland_terrier": "湖畔梗", "lhasa": "拉萨犬",
    "leonberg": "莱昂贝格犬", "malamute": "阿拉斯加马拉缪特",
    "malinois": "马里努阿犬", "maltese_dog": "马尔济斯犬",
    "mexican_hairless": "墨西哥无毛犬", "miniature_pinscher": "迷你杜宾",
    "miniature_poodle": "迷你贵宾犬", "miniature_schnauzer": "迷你雪纳瑞",
    "newfoundland": "纽芬兰犬", "norfolk_terrier": "诺福克梗",
    "norwegian_elkhound": "挪威猎麋犬", "norwich_terrier": "诺里奇梗",
    "old_english_sheepdog": "英国古代牧羊犬", "otterhound": "水獭猎犬",
    "papillon": "蝴蝶犬", "pekinese": "京巴犬", "pembroke": "彭布罗克威尔士柯基犬",
    "pomeranian": "博美犬", "pug": "巴哥犬", "redbone": "红骨猎浣熊犬",
    "rhodesian_ridgeback": "罗得西亚脊背犬", "rottweiler": "罗威纳犬",
    "saint_bernard": "圣伯纳犬", "saluki": "萨卢基猎犬",
    "samoyed": "萨摩耶犬", "schipperke": "西帕基犬",
    "scotch_terrier": "苏格兰梗", "scottish_deerhound": "苏格兰猎鹿犬",
    "sealyham": "西里汉梗", "shetland_sheepdog": "喜乐蒂牧羊犬",
    "shih_tzu": "西施犬", "siberian_husky": "西伯利亚哈士奇",
    "silky_terrier": "丝毛梗", "soft_coated_wheaten_terrier": "软毛麦色梗",
    "staffordshire_bullterrier": "斯塔福郡斗牛梗",
    "standard_poodle": "标准贵宾犬", "standard_schnauzer": "标准雪纳瑞",
    "sussex_spaniel": "苏塞克斯西班牙猎犬", "tibetan_mastiff": "藏獒",
    "tibetan_terrier": "西藏梗", "toy_poodle": "玩具贵宾犬",
    "toy_terrier": "玩具梗", "vizsla": "维兹拉犬",
    "walker_hound": "沃克猎狐犬", "weimaraner": "魏玛犬",
    "welsh_springer_spaniel": "威尔士跳猎犬", "west_highland_white_terrier": "西高地白梗",
    "wheaten_terrier": "软毛麦色梗", "whippet": "惠比特犬",
    "wire_haired_fox_terrier": "刚毛猎狐梗",
    "yorkshire_terrier": "约克夏梗",
}


def normalize(name: str) -> str:
    """标签归一化：小写、去首尾空白、连字符/空格转下划线。"""
    return (name.strip().lower().replace("-", "_").replace(" ", "_"))


def load_stanford_classes() -> dict[int, dict]:
    """从 lists/file_list.mat 解析 120 个类别及其图片数。"""
    import numpy as np  # noqa: F401
    import scipy.io

    path = STANFORD_LISTS / "file_list.mat"
    if not path.exists():
        raise FileNotFoundError(
            f"缺少 {path}；请先运行 scripts/fetch_stanford_dogs.py 并解包 lists.tar")

    data = scipy.io.loadmat(str(path))
    file_list = data["file_list"]
    labels = [int(v) for v in np.asarray(data["labels"]).ravel()]

    def to_texts(array):
        texts = []
        for item in np.asarray(array).ravel():
            if isinstance(item, np.ndarray):
                item = item.ravel()
                if item.size:
                    item = item[0]
            texts.append(str(item))
        return texts

    paths = to_texts(file_list)
    if len(paths) != len(labels):
        raise ValueError(f"file_list({len(paths)}) 与 labels({len(labels)}) 长度不一致")

    by_label: dict[int, dict] = {}
    for label, rel in zip(labels, paths):
        folder = rel.strip().split("/")[0]
        name = folder.split("-", 1)[1] if "-" in folder else folder
        entry = by_label.setdefault(label, {"folder": folder,
                                            "stanford_label": name,
                                            "images": 0})
        entry["images"] += 1
    return by_label


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path,
                        default=_REPO_ROOT / "reports")
    args = parser.parse_args(argv)

    stanford = load_stanford_classes()
    oxford = json.loads(OXFORD_CLASS_NAMES.read_text(encoding="utf-8"))

    # 现有 37 类在清洁划分中的实际样本数（用于目录的 raw/available 计数）
    oxford_counts = {}
    if PROCESSED_CLEAN.is_dir():
        for split in ("train", "val", "test"):
            split_dir = PROCESSED_CLEAN / split
            if not split_dir.is_dir():
                continue
            for class_dir in sorted(split_dir.iterdir()):
                if class_dir.is_dir():
                    oxford_counts[class_dir.name] = oxford_counts.get(
                        class_dir.name, 0) + len(list(class_dir.glob("*.jpg")))

    stanford_by_norm = {normalize(info["stanford_label"]): (label, info)
                        for label, info in stanford.items()}

    rows: list[dict] = []
    matched_stanford_labels: set[int] = set()
    ambiguous: list[dict] = []
    unmatched: list[dict] = []

    # ---- 1. Oxford 37 类 ----
    for canonical in oxford:
        norm = normalize(canonical)
        stanford_label = None
        match_basis = None
        if norm in stanford_by_norm:
            stanford_label, _ = stanford_by_norm[norm]
            match_basis = "normalized_exact"
        elif canonical in CONFIDENT_ALIASES:
            target = normalize(CONFIDENT_ALIASES[canonical])
            if target in stanford_by_norm:
                stanford_label, _ = stanford_by_norm[target]
                match_basis = f"verified_alias:{CONFIDENT_ALIASES[canonical]}"
            else:
                unmatched.append({
                    "canonical_label": canonical,
                    "reason": f"别名表目标 "
                              f"'{CONFIDENT_ALIASES[canonical]}' 不在 Stanford 清单中",
                })

        if canonical in AMBIGUOUS_ALIASES and match_basis is None:
            candidates = AMBIGUOUS_ALIASES[canonical]
            ambiguous.append({
                "canonical_label": canonical,
                "stanford_candidates": candidates,
                "reason": "命名可能对应多个 Stanford 品种，需人工确认后才可合并",
            })
        elif match_basis is None and canonical not in unmatched_names(
                unmatched) and canonical not in NOT_MERGED_REASONS:
            if canonical in EXPECTED_NO_MATCH:
                unmatched.append({"canonical_label": canonical,
                                  "is_cat": False,
                                  "reason": EXPECTED_NO_MATCH[canonical]})
            elif canonical in CAT_BREEDS:
                unmatched.append({
                    "canonical_label": canonical,
                    "is_cat": True,
                    "reason": "猫品种；Stanford Dogs 仅含犬种，无对应属预期",
                })
            else:
                unmatched.append({
                    "canonical_label": canonical,
                    "is_cat": False,
                    "reason": "归一化后无匹配且未列入别名表/已知无对应清单",
                })

        if stanford_label is not None:
            matched_stanford_labels.add(stanford_label)
        elif canonical in NOT_MERGED_REASONS:
            note = NOT_MERGED_REASONS[canonical]
        elif canonical in AMBIGUOUS_ALIASES:
            note = ("命名可能对应多个 Stanford 品种（"
                    + " / ".join(AMBIGUOUS_ALIASES[canonical])
                    + "），需人工确认后才可判定重叠；本阶段不合并")
        elif canonical in EXPECTED_NO_MATCH:
            note = f"Stanford Dogs 中无对应品种：{EXPECTED_NO_MATCH[canonical]}"
        elif canonical in CAT_BREEDS:
            note = "猫品种；Stanford Dogs 仅含犬种，故无对应（属预期）"
        else:
            note = "归一化后无匹配且未列入别名表/已知无对应清单，需人工复核"

        rows.append({
            "canonical_label": canonical,
            "chinese_name": CHINESE_NAMES.get(canonical, canonical),
            "source_name": "Oxford-IIIT Pet",
            "source_original_label": canonical,
            "raw_count": oxford_counts.get(canonical, 0),
            "available_count": oxford_counts.get(canonical, 0),
            "license_and_citation": f"{OXFORD_LICENSE} | {OXFORD_CITATION}",
            "overlaps_existing_37": True,
            "is_new_breed": False,
            "stanford_match": (stanford[stanford_label]["stanford_label"]
                               if stanford_label is not None else ""),
            "stanford_images": (stanford[stanford_label]["images"]
                                if stanford_label is not None else 0),
            "match_basis": match_basis or "",
            "v2_included_from": "data/processed_clean",
            "note": ("Oxford 与 Stanford 重叠品种：按决策只使用 "
                     "data/processed_clean 数据，Stanford 图片仅入审计统计"
                     if stanford_label is not None else note),
        })

    # ---- 2. Stanford 新增品种（未匹配到任何 Oxford 类）----
    for label, info in sorted(stanford.items()):
        if label in matched_stanford_labels:
            continue
        canonical = normalize(info["stanford_label"])
        stanford_label = info["stanford_label"]
        excluded_reason = EXCLUDED_STANFORD_CLASSES.get(stanford_label)
        rows.append({
            "canonical_label": canonical,
            "chinese_name": CHINESE_NAMES.get(
                canonical, CHINESE_NAMES.get(stanford_label, stanford_label)),
            "source_name": "Stanford Dogs",
            "source_original_label": info["folder"],
            "raw_count": info["images"],
            "available_count": 0 if excluded_reason else info["images"],
            "license_and_citation": f"{STANFORD_LICENSE} | {STANFORD_CITATION}",
            "overlaps_existing_37": False,
            "is_new_breed": True,
            "stanford_match": stanford_label,
            "stanford_images": info["images"],
            "match_basis": "new_breed_from_stanford",
            "v2_included_from": ("excluded_ambiguous" if excluded_reason
                                 else "Stanford Dogs (new stratified split)"),
            "note": (excluded_reason
                     or NEW_BREED_NOTES.get(
                         stanford_label,
                         "新增品种；须通过质量/去重/防泄漏检查后才进入 V2")),
        })

    # ---- 3. 写出目录 ----
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "v2_class_catalog.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    matched_count = len(matched_stanford_labels)
    included_new = [r for r in rows
                    if r["is_new_breed"]
                    and r["v2_included_from"] != "excluded_ambiguous"]
    excluded_rows = [r for r in rows
                     if r["v2_included_from"] == "excluded_ambiguous"]
    not_merged = [{"canonical_label": canonical,
                   "reason": reason}
                  for canonical, reason in NOT_MERGED_REASONS.items()]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "oxford_classes": len(oxford),
        "oxford_cat_classes": len([c for c in oxford if c in CAT_BREEDS]),
        "oxford_dog_classes": len([c for c in oxford if c not in CAT_BREEDS]),
        "stanford_classes": len(stanford),
        "stanford_total_images": sum(i["images"] for i in stanford.values()),
        # ---- 关键区分：候选行数 vs 最终有效类别数 ----
        "catalog_rows": len(rows),
        "catalog_rows_breakdown": {
            "oxford": len(oxford),
            "stanford_candidates": len(rows) - len(oxford),
        },
        "excluded_candidate_classes": [
            {"canonical_label": r["canonical_label"],
             "source_original_label": r["source_original_label"],
             "raw_count": r["raw_count"],
             "reason": r["note"]}
            for r in excluded_rows],
        "excluded_candidate_count": len(excluded_rows),
        # 最终有效类别数 = 现有 37 + 已纳入的新增品种
        "valid_class_count": len(oxford) + len(included_new),
        "v2_projected_class_count": len(oxford) + len(included_new),
        "existing_37_classes": sum(1 for r in rows
                                   if r["overlaps_existing_37"]),
        # 真正能在 Stanford 中找到对应标签的 Oxford 犬种数
        "oxford_breeds_matched_to_stanford": matched_count,
        "overlap_classes": matched_count,
        "new_breed_classes": sum(1 for r in rows if r["is_new_breed"]),
        "new_breed_included_in_v2": len(included_new),
        "excluded_ambiguous_stanford": sorted(EXCLUDED_STANFORD_CLASSES),
        "border_collie": next(
            ({"canonical_label": r["canonical_label"],
              "source_original_label": r["source_original_label"],
              "raw_count": r["raw_count"]}
             for r in rows if r["canonical_label"] == "border_collie"), None),
        "american_staffordshire_terrier": next(
            ({"canonical_label": r["canonical_label"],
              "chinese_name": r["chinese_name"],
              "source_original_label": r["source_original_label"],
              "raw_count": r["raw_count"],
              "v2_included_from": r["v2_included_from"],
              "note": r["note"]}
             for r in rows
             if r["canonical_label"] == "american_staffordshire_terrier"),
            None),
        "ambiguous_matches": ambiguous,
        # 有相似 Stanford 类别但按口径保留独立、不合并的 Oxford 犬种
        "not_merged_oxford_breeds": not_merged,
        # 确实没有任何 Stanford 对应类别的 Oxford 类别（含 12 猫）
        "unmatched_oxford_breeds": unmatched,
        "note": ("`catalog_rows` 是类别目录的候选行数；"
                 "`valid_class_count` 才是最终有效类别数"
                 "（已剔除 `excluded_candidate_classes`）。"
                 "类别并集由标准名称去重后的真实结果决定，132/140 仅为规划参考。"
                 "`not_merged_oxford_breeds` 表示有相似类别但按口径不合并，"
                 "与 `unmatched_oxford_breeds`（确实无对应）不同。"),
    }
    json_path = args.out_dir / "v2_class_catalog.json"
    json_path.write_text(json.dumps({"summary": summary, "classes": rows},
                                    indent=2, ensure_ascii=False),
                         encoding="utf-8")

    print(f"[catalog] Oxford {len(oxford)} 类 / Stanford {len(stanford)} 类")
    print(f"[catalog] 类别目录候选行数: {summary['catalog_rows']} "
          f"(Oxford {len(oxford)} + Stanford 候选 "
          f"{summary['catalog_rows_breakdown']['stanford_candidates']})")
    print(f"[catalog] 排除候选: {summary['excluded_candidate_count']} "
          f"{[r['canonical_label'] for r in excluded_rows]}")
    print(f"[catalog] 最终有效类别数: {summary['valid_class_count']} "
          f"(现有 {len(oxford)} + 新增 {len(included_new)})")
    print(f"[catalog] 与 Stanford 确切对应: {matched_count} 类；"
          f"不合并: {[m['canonical_label'] for m in not_merged]}；"
          f"无对应: {[u['canonical_label'] for u in unmatched]}")
    print(f"[catalog] AmStaff: {summary['american_staffordshire_terrier']}")
    print(f"[catalog] Border Collie: {summary['border_collie']}")
    print(f"[catalog] wrote {csv_path}")
    print(f"[catalog] wrote {json_path}")
    return 0


def unmatched_names(unmatched: list[dict]) -> set[str]:
    return {entry["canonical_label"] for entry in unmatched}


if __name__ == "__main__":
    raise SystemExit(main())
