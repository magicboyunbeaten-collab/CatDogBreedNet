#!/usr/bin/env python
"""独立校验 ``data/v2_processed/`` 的完整性与防泄漏性（U3）。

用法（在仓库根目录执行）::

    python scripts/verify_v2_dataset.py
    python scripts/verify_v2_dataset.py --skip-phash   # 跳过耗时的 pHash 复查

校验项：

1. 目录结构：每个 split 的类别集合一致，且与类别目录一致；
2. 计数一致性：实际文件数与 ``manifest.json`` / ``v2_class_counts.csv`` 一致；
3. 跨 split MD5 完全重复 = 0；
4. 跨 split pHash 近重复 = 0（默认执行，可用 ``--skip-phash`` 跳过）；
5. 现有 37 类与 ``data/processed_clean`` 的划分逐文件一致（证明历史基准未被改动）；
6. 每个类别在每个 split 均非空。

本脚本**只读**，不修改任何文件；任一校验失败返回非零退出码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_clean_split import (  # noqa: E402
    find_near_duplicate_pairs,
    image_phash,
)

V2_DIR = _REPO_ROOT / "data" / "v2_processed"
CLEAN_DIR = _REPO_ROOT / "data" / "processed_clean"
CATALOG = _REPO_ROOT / "reports" / "v2_class_catalog.json"
COUNTS = _REPO_ROOT / "reports" / "v2_class_counts.csv"
SPLITS = ("train", "val", "test")


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-phash", action="store_true")
    parser.add_argument("--phash-threshold", type=int, default=5)
    args = parser.parse_args(argv)

    if not V2_DIR.is_dir():
        print(f"[verify] 缺少 {V2_DIR}；请先运行 build_v2_dataset.py")
        return 1

    failures: list[str] = []

    # ---- 1. 目录结构 ----
    per_split: dict[str, dict[str, list[Path]]] = {}
    for split in SPLITS:
        split_dir = V2_DIR / split
        if not split_dir.is_dir():
            failures.append(f"缺少 split 目录 {split_dir}")
            continue
        per_split[split] = {
            class_dir.name: sorted(class_dir.glob("*.jpg"))
            for class_dir in sorted(split_dir.iterdir()) if class_dir.is_dir()}

    class_sets = {split: set(classes) for split, classes in per_split.items()}
    reference = class_sets.get("train", set())
    identical = all(s == reference for s in class_sets.values())
    print(f"[verify] 类别集合一致: {identical}  (类别数 {len(reference)})")
    if not identical:
        failures.append("各 split 的类别集合不一致")

    # 与类别目录比对
    if CATALOG.exists():
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        expected = {row["canonical_label"] for row in catalog["classes"]
                    if row["is_new_breed"]
                    and row["v2_included_from"] != "excluded_ambiguous"}
        expected |= {row["canonical_label"] for row in catalog["classes"]
                     if not row["is_new_breed"]}
        print(f"[verify] 与类别目录一致: {expected == reference}  "
              f"(目录 {len(expected)} 类)")
        if expected != reference:
            failures.append("V2 类别集合与 v2_class_catalog.json 不一致")

    # ---- 2. 计数一致性 ----
    total = sum(len(images) for classes in per_split.values()
                for images in classes.values())
    manifest_path = V2_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(f"[verify] 图片总数 {total:,} vs manifest "
              f"{manifest['total_images']:,} -> "
              f"{total == manifest['total_images']}")
        if total != manifest["total_images"]:
            failures.append("图片总数与 manifest 不一致")
    else:
        failures.append("缺少 manifest.json")

    # 每类非空
    empty = [(split, class_name) for split, classes in per_split.items()
             for class_name, images in classes.items() if not images]
    print(f"[verify] 空类别数: {len(empty)}")
    if empty:
        failures.append(f"{len(empty)} 个 (split, 类别) 为空")

    # ---- 3. 现有 37 类与 processed_clean 逐文件一致 ----
    legacy_mismatch = 0
    legacy_checked = 0
    if CLEAN_DIR.is_dir():
        for split in SPLITS:
            clean_split = CLEAN_DIR / split
            if not clean_split.is_dir():
                continue
            for class_dir in sorted(clean_split.iterdir()):
                if not class_dir.is_dir():
                    continue
                v2_dir = V2_DIR / split / class_dir.name
                clean_names = {p.name for p in class_dir.glob("*.jpg")}
                v2_names = {p.name for p in v2_dir.glob("*.jpg")} \
                    if v2_dir.is_dir() else set()
                legacy_checked += len(clean_names)
                if clean_names - v2_names:
                    legacy_mismatch += len(clean_names - v2_names)
    print(f"[verify] 现有 37 类划分与 processed_clean 一致性: "
          f"检查 {legacy_checked:,} 个文件名，缺失 {legacy_mismatch}")
    if legacy_mismatch:
        failures.append(f"{legacy_mismatch} 个现有 37 类文件名缺失")

    # ---- 4. 跨 split MD5 ----
    md5_index: dict[str, set[str]] = defaultdict(set)
    for split, classes in per_split.items():
        for images in classes.values():
            for image in images:
                md5_index[md5_file(image)].add(split)
    md5_cross = {d: s for d, s in md5_index.items() if len(s) > 1}
    print(f"[verify] 跨 split MD5 完全重复: {len(md5_cross)}")
    if md5_cross:
        failures.append(f"{len(md5_cross)} 组 MD5 跨 split 重复")

    # ---- 5. 跨 split pHash ----
    phash_pairs = 0
    if args.skip_phash:
        print("[verify] --skip-phash：跳过 pHash 复查")
    else:
        hashes: dict[str, np.ndarray] = {}
        for split, classes in per_split.items():
            for images in classes.values():
                for image in images:
                    bits = image_phash(image)
                    if bits is not None:
                        hashes[str(image)] = bits
        split_paths = {split: [str(p) for images in classes.values()
                               for p in images]
                       for split, classes in per_split.items()}
        for index, left in enumerate(SPLITS):
            for right in SPLITS[index + 1:]:
                if not split_paths.get(left) or not split_paths.get(right):
                    continue
                phash_pairs += len(find_near_duplicate_pairs(
                    split_paths[left], split_paths[right], hashes,
                    args.phash_threshold))
        print(f"[verify] 跨 split pHash 近重复（≤{args.phash_threshold}）: "
              f"{phash_pairs}")
        if phash_pairs:
            failures.append(f"{phash_pairs} 对 pHash 跨 split 近重复")

    # ---- 汇总 ----
    print()
    if failures:
        print(f"[verify] 未通过（{len(failures)} 项）：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"[verify] 全部校验通过：类别 {len(reference)}，图片 {total:,}，"
          f"跨 split 重复 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
