#!/usr/bin/env python
"""构建可复现的 V2 数据集 ``data/v2_processed/``（U3 数据准备）。

用法（在仓库根目录执行）::

    python scripts/build_v2_dataset.py --check      # 只统计，不写文件
    python scripts/build_v2_dataset.py              # 构建（增量同步，可重复执行）
    python scripts/build_v2_dataset.py --force      # 重新计算（哈希缓存仍复用）

构建规则：

* **现有 37 类**：原样复制 ``data/processed_clean/{split}/{class}/*.jpg``，
  **完全保留其 train/val/test 划分**（其中 test 作为该部分的历史基准）。
  ``data/processed_clean/`` 只读，绝不修改。
* **新增品种（Stanford Dogs）**：经过质量、去重、防泄漏筛选后，
  按类别分层 + 近重复簇**整簇原子分配**做可复现划分。
* **防泄漏（关键）**：任何外部图片若与 ``data/processed_clean/test/`` 中
  任一图片的 pHash 距离 ≤ 阈值，则**排除该外部图片**；
  **绝不删除或覆盖原测试图片**。
* **幂等**：写入采用增量同步（覆盖应有文件 + 只删多余文件 + 清理空目录），
  不使用 ``shutil.rmtree`` 整目录删除。

产物：
* ``data/v2_processed/``（ImageFolder 布局，Git 忽略）
* ``data/v2_processed/manifest.json``
* ``reports/v2_class_counts.csv``
* ``reports/v2_exclusion_manifest.csv``
* ``reports/v2_data_quality_report.md``
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_clean_split import (  # noqa: E402
    find_near_duplicate_pairs,
    hamming,
    image_phash,
)

CATALOG_JSON = _REPO_ROOT / "reports" / "v2_class_catalog.json"
PROCESSED_CLEAN = _REPO_ROOT / "data" / "processed_clean"
STANFORD_IMAGES = (_REPO_ROOT / "data" / "external_raw" / "stanford_dogs"
                   / "Images")
DOWNLOAD_MANIFEST = (_REPO_ROOT / "data" / "external_raw" / "stanford_dogs"
                     / "download_manifest.json")
OUT_DIR = _REPO_ROOT / "data" / "v2_processed"
REPORTS_DIR = _REPO_ROOT / "reports"
HASH_CACHE = _REPO_ROOT / ".cache" / "v2_phash_cache.json"

SEED = 42
#: 新增品种的划分比例（train / val / test）
SPLIT_RATIOS = (("train", 0.8), ("val", 0.1), ("test", 0.1))
PHASH_THRESHOLD = 5
MIN_SIDE = 64          # 短边小于该值的图片视为无效分辨率

#: 现有 37 类固定按 processed_clean 的划分复制（不重算）
LEGACY_SPLITS = ("train", "val", "test")


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_hash_cache() -> dict:
    if HASH_CACHE.exists():
        try:
            return json.loads(HASH_CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_hash_cache(cache: dict) -> None:
    HASH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HASH_CACHE.write_text(json.dumps(cache), encoding="utf-8")


def phash_bits_to_str(bits: np.ndarray) -> str:
    return "".join("1" if v else "0" for v in np.asarray(bits).ravel())


def str_to_phash_bits(text: str) -> np.ndarray:
    return np.array([c == "1" for c in text], dtype=bool).reshape(8, 8)


def compute_phash_cached(path: Path, cache: dict) -> np.ndarray | None:
    key = str(path)
    if key in cache:
        return str_to_phash_bits(cache[key])
    bits = image_phash(path)
    if bits is not None:
        cache[key] = phash_bits_to_str(bits)
    return bits


def inspect_image(path: Path) -> dict:
    """检查可解码性与分辨率；返回质量结论。"""
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"decode_error: {type(exc).__name__}",
                "width": 0, "height": 0}
    if min(width, height) < MIN_SIDE:
        return {"ok": False, "reason": f"resolution_too_small: {width}x{height}",
                "width": width, "height": height}
    return {"ok": True, "reason": "", "width": width, "height": height}


def union_find_clusters(items: list[str],
                        pairs: list[tuple[str, str, int]]) -> dict[str, int]:
    """并查集：把近重复对合并成簇，返回 item -> cluster_id。"""
    parent = {item: item for item in items}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for left, right, _distance in pairs:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    roots = sorted({find(item) for item in items})
    root_to_id = {root: index for index, root in enumerate(roots)}
    return {item: root_to_id[find(item)] for item in items}


def assign_clusters_to_splits(cluster_members: dict[int, list[str]],
                              class_of: dict[str, str], ratios,
                              rng: random.Random) -> dict[str, str]:
    """把近重复簇**整簇**分配到 split，同时尽量让每个类别保持目标比例。

    必须在**全局**上分配而不是按类各自分配：Stanford Dogs 中存在**跨类别**的
    近重复（例如同一张照片同时出现在 ``English_foxhound`` 与 ``Walker_hound``），
    若按类独立分配，同一簇会被拆到不同 split，造成跨集合泄漏。

    贪心策略：先处理大簇；对每个簇，在它涉及的所有类别上计算各 split 的
    "缺口比例"，选择最缺的那个 split。
    """
    class_totals: dict[str, int] = defaultdict(int)
    for canonical in class_of.values():
        class_totals[canonical] += 1

    targets = {canonical: {name: ratio * total for name, ratio in ratios}
               for canonical, total in class_totals.items()}
    counts = {canonical: {name: 0 for name, _ in ratios}
              for canonical in class_totals}

    cluster_ids = sorted(cluster_members,
                         key=lambda cid: len(cluster_members[cid]), reverse=True)
    rng.shuffle(cluster_ids)
    cluster_ids.sort(key=lambda cid: len(cluster_members[cid]), reverse=True)

    assignment: dict[str, str] = {}
    for cluster_id in cluster_ids:
        members = cluster_members[cluster_id]
        involved = sorted({class_of[member] for member in members})

        def deficit(split_name: str) -> float:
            return max(
                (targets[canonical][split_name] - counts[canonical][split_name])
                / max(targets[canonical][split_name], 1.0)
                for canonical in involved)

        best_split = max((name for name, _ in ratios), key=deficit)
        for member in members:
            assignment[member] = best_split
        for canonical in involved:
            counts[canonical][best_split] += sum(
                1 for member in members if class_of[member] == canonical)
    return assignment


def sync_directory(out_dir: Path, expected: dict[str, Path]) -> dict:
    """增量同步：写入应有文件、删除多余文件、清理空目录（不做整目录删除）。"""
    for destination_str, source in expected.items():
        destination = Path(destination_str)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or md5_file(destination) != md5_file(source):
            shutil.copy2(source, destination)

    existing = {str(path) for path in out_dir.rglob("*.jpg")}
    removed = 0
    for stale in sorted(existing - set(expected)):
        Path(stale).unlink()
        removed += 1

    for directory in sorted((p for p in out_dir.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return {"written": len(expected), "removed_stale": removed}


# ---------------------------------------------------------------------------
# 现有 37 类（原样复制 processed_clean 的划分）
# ---------------------------------------------------------------------------

def collect_legacy() -> tuple[dict[str, Path], list[dict]]:
    """返回 {(split, class, filename): source_path} 与排除记录。"""
    expected: dict[str, Path] = {}
    exclusions: list[dict] = []
    if not PROCESSED_CLEAN.is_dir():
        raise FileNotFoundError(f"缺少 {PROCESSED_CLEAN}")

    for split in LEGACY_SPLITS:
        split_dir = PROCESSED_CLEAN / split
        if not split_dir.is_dir():
            continue
        for class_dir in sorted(split_dir.iterdir()):
            if not class_dir.is_dir():
                continue
            for image in sorted(class_dir.glob("*.jpg")):
                destination = OUT_DIR / split / class_dir.name / image.name
                expected[str(destination)] = image
    return expected, exclusions


# ---------------------------------------------------------------------------
# 新增品种（Stanford Dogs）
# ---------------------------------------------------------------------------

def collect_new_breeds(catalog: dict, hash_cache: dict) -> tuple[
        dict[str, Path], list[dict], dict]:
    """对新增品种执行质量/去重/防泄漏筛选与划分。"""
    all_new_rows = [row for row in catalog["classes"] if row["is_new_breed"]]
    # 命名歧义项不纳入 V2（避免同一品种重复计为多类），但记录进排除清单
    new_rows = [row for row in all_new_rows
                if row.get("v2_included_from") != "excluded_ambiguous"]
    skipped_ambiguous = [row for row in all_new_rows
                         if row.get("v2_included_from") == "excluded_ambiguous"]

    # ---- 1. 枚举 + 质量检查 ----
    candidates: dict[str, list[Path]] = {}
    exclusions: list[dict] = [
        {"class": row["canonical_label"],
         "file": row["source_original_label"],
         "reason": "excluded_ambiguous_naming",
         "detail": row.get("note", "")}
        for row in skipped_ambiguous
    ]
    quality_stats = {"checked": 0, "decode_failed": 0,
                     "resolution_rejected": 0}

    for row in new_rows:
        canonical = row["canonical_label"]
        folder = row["source_original_label"]
        class_dir = STANFORD_IMAGES / folder
        if not class_dir.is_dir():
            exclusions.append({
                "class": canonical, "file": "", "reason": "class_dir_missing",
                "detail": str(class_dir)})
            continue
        kept: list[Path] = []
        for image in sorted(class_dir.glob("*.jpg")):
            quality_stats["checked"] += 1
            verdict = inspect_image(image)
            if not verdict["ok"]:
                if verdict["reason"].startswith("decode"):
                    quality_stats["decode_failed"] += 1
                else:
                    quality_stats["resolution_rejected"] += 1
                exclusions.append({
                    "class": canonical, "file": str(image),
                    "reason": verdict["reason"].split(":")[0],
                    "detail": verdict["reason"]})
                continue
            kept.append(image)
        candidates[canonical] = kept

    # ---- 2. MD5 完全重复去重（同源内部）----
    seen_md5: dict[str, Path] = {}
    md5_duplicates = 0
    deduped: dict[str, list[Path]] = {}
    for canonical, images in candidates.items():
        kept: list[Path] = []
        for image in images:
            digest = md5_file(image)
            if digest in seen_md5:
                md5_duplicates += 1
                exclusions.append({
                    "class": canonical, "file": str(image),
                    "reason": "md5_exact_duplicate",
                    "detail": f"与 {seen_md5[digest]} 完全相同"})
                continue
            seen_md5[digest] = image
            kept.append(image)
        deduped[canonical] = kept

    # ---- 3. 与现有 test 集交叉去重（防泄漏，关键）----
    test_images: list[Path] = []
    test_split_dir = PROCESSED_CLEAN / "test"
    if test_split_dir.is_dir():
        test_images = sorted(test_split_dir.rglob("*.jpg"))

    print(f"[v2] 计算 pHash：新增 {sum(len(v) for v in deduped.values())} 张 + "
          f"现有 test {len(test_images)} 张 ...", flush=True)
    new_hashes: dict[str, np.ndarray] = {}
    for images in deduped.values():
        for image in images:
            bits = compute_phash_cached(image, hash_cache)
            if bits is not None:
                new_hashes[str(image)] = bits
    test_hashes: dict[str, np.ndarray] = {}
    for image in test_images:
        bits = compute_phash_cached(image, hash_cache)
        if bits is not None:
            test_hashes[str(image)] = bits
    save_hash_cache(hash_cache)

    leak_pairs: list[tuple[str, str, int]] = []
    if new_hashes and test_hashes:
        print("[v2] 与现有 test 集做近重复交叉比对 ...", flush=True)
        leak_pairs = find_near_duplicate_pairs(
            list(new_hashes), list(test_hashes),
            {**new_hashes, **test_hashes}, PHASH_THRESHOLD)

    leaked: dict[str, int] = {}
    for new_path, test_path, distance in leak_pairs:
        leaked.setdefault(new_path, distance)

    for canonical, images in deduped.items():
        kept = []
        for image in images:
            if str(image) in leaked:
                exclusions.append({
                    "class": canonical, "file": str(image),
                    "reason": "near_duplicate_with_existing_test",
                    "detail": f"pHash 距离 {leaked[str(image)]}，"
                              f"与现有 test 图近重复（已排除外部样本，"
                              f"原测试图保留）"})
                continue
            kept.append(image)
        deduped[canonical] = kept

    # ---- 4. 同源近重复聚簇（簇不跨 split）----
    all_new = [str(image) for images in deduped.values() for image in images]
    internal_pairs: list[tuple[str, str, int]] = []
    if len(all_new) > 1:
        print(f"[v2] 对 {len(all_new)} 张新增图片做近重复聚簇 ...", flush=True)
        internal_pairs = find_near_duplicate_pairs(
            all_new, all_new, {k: v for k, v in new_hashes.items()
                               if k in set(all_new)}, PHASH_THRESHOLD)
    clusters = union_find_clusters(all_new, internal_pairs)

    # ---- 5. 分层 + 全局簇原子划分 ----
    class_of: dict[str, str] = {}
    for canonical, images in deduped.items():
        for image in images:
            class_of[str(image)] = canonical

    cluster_members: dict[int, list[str]] = defaultdict(list)
    for image_str in class_of:
        cluster_members[clusters[image_str]].append(image_str)

    rng = random.Random(SEED)
    assignment = assign_clusters_to_splits(
        dict(cluster_members), class_of, SPLIT_RATIOS, rng)

    expected: dict[str, Path] = {}
    for image_str, split in assignment.items():
        canonical = class_of[image_str]
        destination = OUT_DIR / split / canonical / Path(image_str).name
        expected[str(destination)] = Path(image_str)

    stats = {
        "quality": quality_stats,
        "md5_duplicates": md5_duplicates,
        "leak_pairs_with_existing_test": len(leak_pairs),
        "leaked_images_excluded": len(leaked),
        "internal_near_duplicate_pairs": len(internal_pairs),
        "clusters": len(set(clusters.values())) if clusters else 0,
        "multi_image_clusters": sum(
            1 for members in
            _group_by_cluster(clusters).values() if len(members) > 1),
    }
    return expected, exclusions, stats


def _group_by_cluster(clusters: dict[str, int]) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for item, cluster_id in clusters.items():
        grouped[cluster_id].append(item)
    return dict(grouped)


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def verify(expected: dict[str, Path], hash_cache: dict) -> dict:
    """校验：类别集合一致、MD5 跨 split 为 0、pHash 跨 split 为 0。

    注意：一律读取**源文件**（``expected.values()``），因为 ``--check`` 模式
    下目标目录尚未写入；split/class 归属从目标路径（``expected`` 的键）推导。
    """
    by_split: dict[str, dict[str, list[Path]]] = defaultdict(
        lambda: defaultdict(list))
    for destination_str, source in expected.items():
        parts = Path(destination_str).parts
        split, class_name = parts[-3], parts[-2]
        by_split[split][class_name].append(source)

    class_sets = {split: set(classes) for split, classes in by_split.items()}
    reference = class_sets.get("train", set())
    classes_identical = all(s == reference for s in class_sets.values())

    # MD5 跨 split
    md5_index: dict[str, list[str]] = defaultdict(list)
    for split, classes in by_split.items():
        for images in classes.values():
            for image in images:
                md5_index[md5_file(image)].append(f"{split}/{image.name}")
    md5_cross = {digest: locations for digest, locations in md5_index.items()
                 if len({loc.split("/")[0] for loc in locations}) > 1}

    # pHash 跨 split
    split_list = {split: [str(p) for classes in classes.values()
                          for p in classes] for split, classes in by_split.items()}
    hashes: dict[str, np.ndarray] = {}
    for paths in split_list.values():
        for path in paths:
            bits = compute_phash_cached(Path(path), hash_cache)
            if bits is not None:
                hashes[path] = bits

    cross_split_pairs: list[tuple[str, str, int]] = []
    names = list(split_list)
    for i, left_split in enumerate(names):
        for right_split in names[i + 1:]:
            if not split_list[left_split] or not split_list[right_split]:
                continue
            cross_split_pairs += find_near_duplicate_pairs(
                split_list[left_split], split_list[right_split],
                hashes, PHASH_THRESHOLD)

    return {
        "class_sets_identical": classes_identical,
        "class_count": len(reference),
        "md5_cross_split_duplicates": len(md5_cross),
        "phash_cross_split_pairs": len(cross_split_pairs),
        "phash_cross_split_examples": [
            {"a": a, "b": b, "distance": d}
            for a, b, d in cross_split_pairs[:10]],
        "per_split_class_count": {s: len(c) for s, c in class_sets.items()},
    }


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def write_reports(catalog: dict, expected: dict[str, Path],
                  exclusions: list[dict], stats: dict, verification: dict,
                  manifest: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 每类每 split 计数
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for destination_str in expected:
        parts = Path(destination_str).parts
        counts[(parts[-3], parts[-2])] += 1

    classes = sorted({cls for (_split, cls) in counts})
    with (REPORTS_DIR / "v2_class_counts.csv").open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_label", "train", "val", "test", "total"])
        for class_name in classes:
            row = [counts.get((split, class_name), 0)
                   for split in ("train", "val", "test")]
            writer.writerow([class_name, *row, sum(row)])

    # 排除清单
    with (REPORTS_DIR / "v2_exclusion_manifest.csv").open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["class", "file", "reason", "detail"])
        writer.writeheader()
        writer.writerows(exclusions)

    # 质量报告
    lines: list[str] = []
    add = lines.append
    add("# V2 数据质量与防泄漏报告（U3）")
    add("")
    add(f"> 生成时间：{manifest['generated_at']}")
    add("> 数据目录：`data/v2_processed/`（Git 忽略）")
    add("> 本阶段**不训练模型**。")
    add("")

    summary = catalog["summary"]
    add("## 1. 数据集组成")
    add("")
    add("> **两个数字必须区分**：`catalog_rows` 是类别目录的**候选行数**，"
        "`valid_class_count` 是剔除被排除候选后的**最终有效类别数**。"
        "下表「最终有效类别数」取自实际 `manifest.json` 与数据目录。")
    add("")
    add("| 项目 | 数量 | 说明 |")
    add("|---|---|---|")
    add(f"| 类别目录候选行数 | **{summary['catalog_rows']}** | "
        f"Oxford {summary['catalog_rows_breakdown']['oxford']} + "
        f"Stanford 候选 "
        f"{summary['catalog_rows_breakdown']['stanford_candidates']} |")
    excluded = summary.get("excluded_candidate_classes", [])
    add(f"| 被排除的候选类别 | **{len(excluded)}** | "
        + ("、".join(f"`{item['canonical_label']}`" for item in excluded)
           or "无")
        + " |")
    add(f"| **最终有效类别数** | **{verification['class_count']}** | "
        f"现有 {summary['oxford_classes']} + 新增 "
        f"{summary['new_breed_included_in_v2']}；"
        f"由标准名称去重后的真实并集决定 |")
    add("")
    add("各来源明细：")
    add("")
    add("| 来源 | 有效类别数 | 说明 |")
    add("|---|---|---|")
    add(f"| Oxford-IIIT Pet（现有 37 类） | "
        f"{summary['oxford_classes']} | "
        f"原样复制 `data/processed_clean` 的 train/val/test，"
        f"其 test 作为历史基准 |")
    add(f"| Stanford Dogs（新增有效品种） | "
        f"{summary['new_breed_included_in_v2']} | "
        f"经质量/去重/防泄漏筛选后按 80/10/10 分层划分 |")
    add(f"| **合计** | **{verification['class_count']}** | |")
    add("")
    excluded = summary.get("excluded_candidate_classes", [])
    if excluded:
        add("被排除的候选类别及理由：")
        add("")
        for item in excluded:
            add(f"- `{item['canonical_label']}`"
                f"（`{item['source_original_label']}`，"
                f"原始 {item['raw_count']} 张）：{item['reason']}")
        add("")

    add("## 2. 各 split 规模")
    add("")
    add("| split | 类别数 | 图片数 |")
    add("|---|---|---|")
    for split in ("train", "val", "test"):
        images = sum(1 for path in expected if Path(path).parts[-3] == split)
        add(f"| {split} | {verification['per_split_class_count'].get(split, 0)} "
            f"| {images:,} |")
    add(f"| **合计** | **{verification['class_count']}** | "
        f"**{len(expected):,}** |")
    add("")

    add("## 3. 质量检查")
    add("")
    quality = stats["quality"]
    add(f"- 检查图片数：**{quality['checked']:,}**")
    add(f"- 解码失败：**{quality['decode_failed']}**")
    add(f"- 分辨率过低（短边 < {MIN_SIDE}px）："
        f"**{quality['resolution_rejected']}**")
    add(f"- MD5 完全重复（同源内部）：**{stats['md5_duplicates']}**")
    add("")

    add("## 4. 防泄漏检查（关键）")
    add("")
    add(f"阈值：pHash（灰度 DCT 8×8）汉明距离 ≤ **{PHASH_THRESHOLD}**")
    add("")
    add(f"- 新增数据与 `data/processed_clean/test/` 的近重复对："
        f"**{stats['leak_pairs_with_existing_test']}**")
    add(f"- **因此被排除的外部图片：{stats['leaked_images_excluded']} 张**"
        f"（原测试图片全部保留，未删除、未覆盖）")
    add(f"- 新增数据内部的近重复对："
        f"**{stats['internal_near_duplicate_pairs']}**")
    add(f"- 近重复簇数：{stats['clusters']}（其中多图簇 "
        f"{stats['multi_image_clusters']} 个），**整簇原子分配到同一 split**")
    add("")
    add("### 4.1 V2 划分内部跨集合检查")
    add("")
    add("| 检查项 | 结果 |")
    add("|---|---|")
    add(f"| 各 split 类别集合一致 | "
        f"**{verification['class_sets_identical']}** |")
    add(f"| MD5 跨 split 完全重复 | "
        f"**{verification['md5_cross_split_duplicates']}** |")
    add(f"| pHash 跨 split 近重复对（≤{PHASH_THRESHOLD}） | "
        f"**{verification['phash_cross_split_pairs']}** |")
    add("")
    if verification["phash_cross_split_pairs"]:
        add("残留跨 split 近重复示例：")
        for example in verification["phash_cross_split_examples"]:
            add(f"- 距离 {example['distance']}：`{example['a']}` ↔ "
                f"`{example['b']}`")
        add("")
        add("> 说明：现有 37 类沿用 `data/processed_clean` 的原划分，"
            "该划分已通过「pHash 跨划分近重复 = 0」校验；")
        add("> 若上表非 0，需逐对核查是否为新增品种内部簇边界问题。")
        add("")

    add("## 5. 排除清单摘要")
    add("")
    by_reason: dict[str, int] = defaultdict(int)
    for item in exclusions:
        by_reason[item["reason"]] += 1
    add("| 原因 | 数量 |")
    add("|---|---|")
    for reason, count in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        add(f"| `{reason}` | {count} |")
    add("")
    add(f"完整清单见 `reports/v2_exclusion_manifest.csv`（共 {len(exclusions)} 条）。")
    add("")

    add("## 6. 可复现性")
    add("")
    add(f"- 随机种子：**{manifest['seed']}**")
    add(f"- 划分脚本：`scripts/build_v2_dataset.py`")
    add(f"- 标签目录：`reports/v2_class_catalog.json`")
    add(f"- 校验脚本：`scripts/verify_v2_dataset.py`")
    add("")
    add("```powershell")
    add("cd E:\\CatDogBreedNet")
    add(".venv\\Scripts\\python.exe scripts\\fetch_stanford_dogs.py")
    add(".venv\\Scripts\\python.exe scripts\\build_v2_class_catalog.py")
    add(".venv\\Scripts\\python.exe scripts\\build_v2_dataset.py")
    add(".venv\\Scripts\\python.exe scripts\\verify_v2_dataset.py")
    add("```")
    add("")

    add("## 7. 已知限制与口径说明")
    add("")
    add("1. **许可**：Stanford Dogs 为 ImageNet 衍生数据集，官方页面未声明独立")
    add("   许可证，仅限本地非商业教育研究用途；**不得再分发**原始或处理后的图片。")
    add("   论文需按审核报告要求引用 Khosla et al. (FGVC@CVPR 2011) 与 "
        "Deng et al. (CVPR 2009)。")
    add("2. **新增品种仅犬类**：本阶段未找到可审核通过的家猫品种数据源")
    add("   （CatInBeard 需授权、COCO 无品种标签、其余两个 HF 数据集不适用），")
    add("   因此猫类别仍为现有 12 种。")
    add("3. **Oxford 犬种与 Stanford 的对应关系分为三类**（不可混为一谈）：")
    add(f"   - **已确切对应 {summary['oxford_breeds_matched_to_stanford']} 个**："
        "经归一化或人工核验别名与 Stanford 一一对应，"
        "其中包含 `scottish_terrier` ↔ `Scotch_terrier`"
        "（Scotch 是 Scottish 的旧同义名，属**已验证别名**，"
        "不再按命名歧义处理）。按既定决策**只使用 Oxford 数据**，"
        "Stanford 图片仅入审计统计、不合并训练。")
    not_merged = summary.get("not_merged_oxford_breeds", [])
    if not_merged:
        add(f"   - **有相似类别但按口径不合并 {len(not_merged)} 个**：")
        for item in not_merged:
            add(f"     - `{item['canonical_label']}`：{item['reason']}")
    unmatched = summary.get("unmatched_oxford_breeds", [])
    dog_unmatched = [item for item in unmatched if not item.get("is_cat")]
    cat_unmatched = [item for item in unmatched if item.get("is_cat")]
    add(f"   - **确实没有对应类别 {len(unmatched)} 个**："
        f"其中猫 {len(cat_unmatched)} 个（Stanford Dogs 仅含犬种，属预期），"
        f"犬 {len(dog_unmatched)} 个"
        + ("（"
           + "、".join(f"`{item['canonical_label']}`" for item in dog_unmatched)
           + "）" if dog_unmatched else "")
        + "。")
    add("4. **`cocker_spaniel` 保持排除**：Stanford 的来源标签无法可靠区分")
    add("   美式/英式可卡犬，**不做猜测性重标**；Oxford 的 "
        "`english_cocker_spaniel` 完整保留，两者不合并。")
    add("5. **重叠品种不合并**：" 
        f"{summary['oxford_breeds_matched_to_stanford']} 个重叠犬种"
        "只使用 `data/processed_clean` 数据，"
        "Stanford 对应图片仅进入审计统计，不参与训练。")
    add("6. 新增品种的划分是本项目自建（80/10/10），与 Stanford 官方划分不同；")
    add("   本阶段**未用测试集做任何调参**。")
    add("")

    (REPORTS_DIR / "v2_data_quality_report.md").write_text(
        "\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="只统计与校验，不写 data/v2_processed/")
    parser.add_argument("--force", action="store_true",
                        help="忽略已存在结果，重新计算")
    args = parser.parse_args(argv)

    if not CATALOG_JSON.exists():
        print(f"[v2] 缺少 {CATALOG_JSON}；请先运行 "
              f"scripts/build_v2_class_catalog.py")
        return 1
    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))

    hash_cache = load_hash_cache()
    print("[v2] 收集现有 37 类（原样复制 processed_clean 划分）...", flush=True)
    expected, exclusions = collect_legacy()
    legacy_count = len(expected)
    print(f"[v2]   现有 37 类：{legacy_count:,} 张", flush=True)

    print("[v2] 处理新增品种（质量 / 去重 / 防泄漏 / 划分）...", flush=True)
    new_expected, new_exclusions, stats = collect_new_breeds(catalog, hash_cache)
    expected.update(new_expected)
    exclusions.extend(new_exclusions)
    print(f"[v2]   新增品种：{len(new_expected):,} 张，"
          f"排除 {len(new_exclusions)} 张", flush=True)

    print("[v2] 校验划分 ...", flush=True)
    verification = verify(expected, hash_cache)
    save_hash_cache(hash_cache)

    source_checksums: dict[str, str] = {}
    if DOWNLOAD_MANIFEST.exists():
        download_info = json.loads(
            DOWNLOAD_MANIFEST.read_text(encoding="utf-8"))
        source_checksums = {name: entry.get("sha256")
                            for name, entry in download_info["files"].items()}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "split_ratios_new_breeds": dict(SPLIT_RATIOS),
        "phash_threshold": PHASH_THRESHOLD,
        "min_side": MIN_SIDE,
        "class_count": verification["class_count"],
        "total_images": len(expected),
        "legacy_images": legacy_count,
        "new_breed_images": len(new_expected),
        "exclusions": len(exclusions),
        "stats": stats,
        "verification": verification,
        "source_checksums": source_checksums,
        "note": ("现有 37 类原样沿用 data/processed_clean 的划分；"
                 "新增品种按 80/10/10 分层 + 近重复簇原子分配；"
                 "与 processed_clean/test 近重复的外部图片已排除。"),
    }

    if args.check:
        print(f"[v2] --check：类别 {verification['class_count']}，"
              f"图片 {len(expected):,}，不做写入", flush=True)
        print(json.dumps(verification, indent=2, ensure_ascii=False))
        return 0

    print("[v2] 增量同步写入 data/v2_processed/ ...", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sync_stats = sync_directory(OUT_DIR, expected)
    print(f"[v2]   写入 {sync_stats['written']:,}，"
          f"移除多余 {sync_stats['removed_stale']}", flush=True)

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    write_reports(catalog, expected, exclusions, stats, verification, manifest)

    print(f"[v2] 类别数：{verification['class_count']}", flush=True)
    print(f"[v2] 图片总数：{len(expected):,} "
          f"(现有 37 类 {legacy_count:,} + 新增 {len(new_expected):,})",
          flush=True)
    print(f"[v2] 跨 split 检查：MD5 重复 "
          f"{verification['md5_cross_split_duplicates']}，"
          f"pHash 近重复 {verification['phash_cross_split_pairs']}", flush=True)
    print("[v2] wrote data/v2_processed/manifest.json、"
          "reports/v2_class_counts.csv、reports/v2_exclusion_manifest.csv、"
          "reports/v2_data_quality_report.md", flush=True)
    return 0 if (verification["class_sets_identical"]
                 and verification["md5_cross_split_duplicates"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
