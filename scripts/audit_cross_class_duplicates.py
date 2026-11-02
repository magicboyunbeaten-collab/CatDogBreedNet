#!/usr/bin/env python
"""APBT / AmStaff 相关类别间的图片重复审计（只读，不删除、不判定标签）。

用法（在仓库根目录执行）::

    python scripts/audit_cross_class_duplicates.py

检查范围（5 个 pit-bull 相关 canonical label，全部 split）：

1. **同一 split 内跨类别** MD5 完全相同；
2. **同一 split 内跨类别** pHash 近重复（汉明距离 ≤ 5，与项目既有阈值一致）；
3. **跨 split** 的相同图 / 近重复图（含同类跨 split）。

这是 ``scripts/verify_v2_dataset.py`` 未覆盖的维度——该脚本只做"跨 split"
与全类别汇总，不做"同一 split 内不同类别之间"的比对。

输出：
* ``apbt_amstaff_cross_class_duplicate_pairs.csv`` — 可疑配对明细；
* ``duplicates_contact_sheet.png`` — 可疑配对联系表（缩放副本，不改原图）。

**不自动删除任何重复对，也不判定哪个标签正确。**
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_clean_split import (  # noqa: E402
    find_near_duplicate_pairs,
    image_phash,
)

DATA_DIR = _REPO_ROOT / "data" / "v2_processed"
OUT_DIR = _REPO_ROOT / "reports" / "v2_1_diagnostics"
THRESHOLD = 5
SPLITS = ("train", "val", "test")
CLASSES = ("american_pit_bull_terrier", "american_staffordshire_terrier",
           "staffordshire_bull_terrier", "american_bulldog", "bull_mastiff")
OUT_CSV = "apbt_amstaff_cross_class_duplicate_pairs.csv"
OUT_SHEET = "duplicates_contact_sheet.png"


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(data_dir: Path) -> dict[tuple[str, str], list[Path]]:
    index: dict[tuple[str, str], list[Path]] = {}
    for split in SPLITS:
        for label in CLASSES:
            directory = data_dir / split / label
            index[(split, label)] = (
                sorted(directory.glob("*.jpg")) if directory.is_dir() else [])
    return index


def make_sheet(pairs: list[dict], destination: Path, cell: int = 190,
               columns: int = 2, limit: int = 24) -> None:
    """每个可疑对占两格（左 A / 右 B），标注类别与距离。"""
    if not pairs:
        return
    pairs = pairs[:limit]
    rows = len(pairs)
    width = columns * 2 * cell
    height = 28 + rows * (cell + 30)
    sheet = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None
    draw.text((6, 8), "APBT/AmStaff 可疑重复对（左 A / 右 B）", fill=(0, 0, 0),
              font=font)
    for row, pair in enumerate(pairs):
        y = 28 + row * (cell + 30)
        for column, side in enumerate(("a", "b")):
            x = column * cell * 2
            try:
                with Image.open(pair[f"path_{side}"]) as image:
                    thumbnail = image.convert("RGB").copy()
                thumbnail.thumbnail((cell - 6, cell - 6))
                sheet.paste(thumbnail, (x + 3, y + 3))
            except Exception:  # noqa: BLE001
                draw.rectangle([x + 3, y + 3, x + cell - 3, y + cell - 3],
                               outline=(200, 0, 0))
            caption = (f"{pair[f'class_{side}'][:26]} "
                       f"[{pair[f'split_{side}']}]")
            draw.text((x + 3, y + cell + 1), caption, fill=(0, 0, 0), font=font)
            draw.text((x + 3, y + cell + 13),
                      f"md5={'same' if pair['md5_equal'] else 'diff'} "
                      f"pHash={pair['phash_distance']}",
                      fill=(90, 90, 90), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=85)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--threshold", type=int, default=THRESHOLD)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    for name in (OUT_CSV, OUT_SHEET):
        if (out_dir / name).exists():
            out_dir = out_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"[dup] outputs exist; writing to {out_dir}")
            break
    out_dir.mkdir(parents=True, exist_ok=True)

    index = collect(args.data_dir)
    total = sum(len(v) for v in index.values())
    print(f"[dup] 扫描 {len(CLASSES)} 类 × {len(SPLITS)} split = {total} 张")
    for (split, label), paths in index.items():
        if paths:
            print(f"  {split:<5} {label:<32} {len(paths):>3}")

    # ---- MD5 ----
    md5_map: dict[str, str] = {}
    for paths in index.values():
        for path in paths:
            md5_map[str(path)] = md5_file(path)
    md5_groups: dict[str, list[str]] = {}
    for path_str, digest in md5_map.items():
        md5_groups.setdefault(digest, []).append(path_str)

    # ---- pHash ----
    hashes: dict[str, np.ndarray] = {}
    for paths in index.values():
        for path in paths:
            bits = image_phash(path)
            if bits is not None:
                hashes[str(path)] = bits
    print(f"[dup] pHash 计算完成: {len(hashes)}/{total}")

    split_of = {}
    class_of = {}
    for (split, label), paths in index.items():
        for path in paths:
            split_of[str(path)] = split
            class_of[str(path)] = label

    pairs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(left: str, right: str, distance: int, pair_type: str) -> None:
        key = tuple(sorted((left, right)))
        if key in seen:
            return
        seen.add(key)
        pairs.append({
            "pair_type": pair_type,
            "split_a": split_of[left],
            "class_a": class_of[left],
            "path_a": left,
            "md5_a": md5_map[left],
            "split_b": split_of[right],
            "class_b": class_of[right],
            "path_b": right,
            "md5_b": md5_map[right],
            "md5_equal": md5_map[left] == md5_map[right],
            "phash_distance": distance,
        })

    # 1) 同 split 内跨类别 MD5 完全相同
    for digest, paths in md5_groups.items():
        if len(paths) < 2:
            continue
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                left, right = paths[i], paths[j]
                if (split_of[left] == split_of[right]
                        and class_of[left] != class_of[right]):
                    add_pair(left, right, 0, "same_split_cross_class_md5")

    # 2) 同 split 内跨类别 pHash 近重复
    for split in SPLITS:
        labels_here = [label for label in CLASSES if index[(split, label)]]
        for i, left_label in enumerate(labels_here):
            for right_label in labels_here[i + 1:]:
                left_list = [str(p) for p in index[(split, left_label)]]
                right_list = [str(p) for p in index[(split, right_label)]]
                if not left_list or not right_list:
                    continue
                found = find_near_duplicate_pairs(
                    left_list, right_list, hashes, args.threshold)
                for left, right, distance in found:
                    add_pair(left, right, distance,
                             "same_split_cross_class_phash")

    # 3) 跨 split（含同类）
    for i, left_split in enumerate(SPLITS):
        for right_split in SPLITS[i + 1:]:
            for left_label in CLASSES:
                for right_label in CLASSES:
                    left_list = [str(p) for p in index[(left_split, left_label)]]
                    right_list = [str(p) for p in index[(right_split,
                                                         right_label)]]
                    if not left_list or not right_list:
                        continue
                    found = find_near_duplicate_pairs(
                        left_list, right_list, hashes, args.threshold)
                    for left, right, distance in found:
                        pair_type = ("cross_split_same_class"
                                     if left_label == right_label
                                     else "cross_split_cross_class")
                        add_pair(left, right, distance, pair_type)

    # ---- 写出 ----
    fieldnames = ["pair_type", "split_a", "class_a", "path_a", "md5_a",
                  "split_b", "class_b", "path_b", "md5_b", "md5_equal",
                  "phash_distance"]
    csv_path = out_dir / OUT_CSV
    import csv as _csv
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = _csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for pair in pairs:
            writer.writerow({key: pair[key] for key in fieldnames})

    counts = Counter(pair["pair_type"] for pair in pairs)
    print()
    print(f"[dup] 可疑配对总数: {len(pairs)}")
    for pair_type, count in sorted(counts.items()):
        print(f"  {pair_type:<34} {count}")
    md5_cross = [p for p in pairs if p["md5_equal"]]
    print(f"[dup] 其中 MD5 完全相同的对: {len(md5_cross)}")

    sheet_path = out_dir / OUT_SHEET
    make_sheet(md5_cross + [p for p in pairs if not p["md5_equal"]], sheet_path)
    print(f"[dup] wrote {csv_path}")
    if sheet_path.exists():
        print(f"[dup] wrote {sheet_path}")
    else:
        print("[dup] 未生成联系表：本次没有发现任何可疑配对（联系表为空无意义）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
