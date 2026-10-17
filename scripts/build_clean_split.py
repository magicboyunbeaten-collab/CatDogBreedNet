#!/usr/bin/env python
"""阶段一：构建独立的去重数据划分（MODEL_UPGRADE_PLAN 的泄漏风险检查）。

用法（在仓库根目录执行）::

    python scripts/build_clean_split.py
    python scripts/build_clean_split.py --threshold 5 --seed 42 --val-ratio 0.1

目标：在**不修改原始数据**的前提下，生成一份用于评估的"清洁"划分
``data/processed_clean/``，规则如下：

1. **官方 test 集原样保留**：所有官方 test 图片全部复制，不排除、不改名、
   不改标签（保证 test 指标与原始划分在测试集层面一致）；
2. **排除 train/val 中与 test 近重复的样本**：官方 trainval 图片若与任一
   官方 test 图片 pHash 距离 ≤ 阈值（或 MD5 相同），从训练池中剔除，
   并记录排除原因与匹配到的 test 图片；
3. **剩余 train/val 按近重复簇分组**：在剩余 trainval 内部用 pHash 阈值
   构建近重复簇（并查集），整簇分配到 train 或 val，确保相同/近重复图片
   **不跨 train/val**；簇归属用"簇内原划分多数决，平局归 train"；
4. **类别完备性保护**：若某类别在 val 中一个样本都不剩，则从该类别中
   选取一个"所在簇最小"的样本补入 val，并记录该决策；
5. **完整清单**：写入 ``reports/clean_split_manifest.json``，包含每张图的
   split / 品种 / 簇 ID / 排除原因、逐类数量、随机种子与阈值。

划分后自动校验：类别集合与顺序一致（ImageFolder 约定）、MD5 跨划分完全
重复为 0、pHash 跨划分近重复为 0（train/val ↔ test 以及 train ↔ val）。

**本脚本只写 ``data/processed_clean/``，绝不触碰 ``data/processed/``、
官方原始档案或任何模型权重。**
"""
from __future__ import annotations

import argparse
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

from ml.config import (  # noqa: E402
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    REPORTS_DIR,
    SEED,
    VAL_RATIO,
)

DEFAULT_THRESHOLD = 5


# ---------------------------------------------------------------------------
# 官方划分解析（与 scripts/prepare_dataset.py 完全一致的算法）
# ---------------------------------------------------------------------------

def parse_breed_mapping(raw_dir: Path) -> dict[str, str]:
    """image_id -> breed, parsed from annotations/list.txt."""
    list_txt = Path(raw_dir) / "annotations" / "list.txt"
    if not list_txt.exists():
        raise FileNotFoundError(f"missing {list_txt}")
    mapping: dict[str, str] = {}
    for line in list_txt.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        mapping[parts[0]] = parts[0].rsplit("_", 1)[0]
    if not mapping:
        raise ValueError(f"no entries parsed from {list_txt}")
    return mapping


def read_split_file(path: Path) -> list[str]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"missing split file {path}")
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split()[0])
    return ids


def original_train_val_split(trainval_ids: list[str], breed_of: dict[str, str],
                             seed: int, val_ratio: float) -> dict[str, str]:
    """复现 prepare_dataset.py 的按类分层 train/val 划分，返回 image_id -> split。"""
    by_class: dict[str, list[str]] = defaultdict(list)
    for image_id in trainval_ids:
        by_class[breed_of[image_id]].append(image_id)
    rng = random.Random(seed)
    assignment: dict[str, str] = {}
    for breed in sorted(by_class):
        ids = sorted(by_class[breed])
        rng.shuffle(ids)
        n_val = int(round(len(ids) * val_ratio))
        if len(ids) >= 10:
            n_val = max(1, n_val)
        for image_id in ids[:n_val]:
            assignment[image_id] = "val"
        for image_id in ids[n_val:]:
            assignment[image_id] = "train"
    return assignment


# ---------------------------------------------------------------------------
# 图像哈希与近重复检索（多索引分块，避免 O(n^2) 全比较）
# ---------------------------------------------------------------------------

def md5_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_phash(path: Path, hash_size: int = 8,
                highfreq_factor: int = 4) -> np.ndarray | None:
    """Classic pHash bit array; ``None`` if scipy is unavailable."""
    try:
        from scipy.fftpack import dct
    except Exception:
        return None
    img_size = hash_size * highfreq_factor
    try:
        with Image.open(path) as im:
            grey = im.convert("L").resize((img_size, img_size), Image.LANCZOS)
            pixels = np.asarray(grey, dtype=float)
    except Exception:
        return None
    coeffs = dct(dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")
    return coeffs[:hash_size, :hash_size] > np.median(
        coeffs[:hash_size, :hash_size])


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def _blocks(bits: np.ndarray, block_count: int) -> list[bytes]:
    """把比特数组**展平后**等分成 block_count 段，返回每段的字节表示。

    注意：``image_phash`` 返回的是 (8, 8) 的二维布尔数组，必须先 ``ravel``
    再切片；直接 ``bits[start:end]`` 会按行切片并在超出 8 行时得到空段。
    """
    flat = np.asarray(bits).ravel()
    width = flat.size
    bounds = [round(i * width / block_count) for i in range(block_count + 1)]
    keys = []
    for start, end in zip(bounds, bounds[1:]):
        if end > start:
            keys.append(np.packbits(flat[start:end]).tobytes())
    return keys


def find_near_duplicate_pairs(
        left: list[str], right: list[str], hashes: dict[str, np.ndarray],
        threshold: int) -> list[tuple[str, str, int]]:
    """返回 left/right 之间汉明距离 ≤ threshold 的所有图片对。

    返回的三元组保持 ``(left 中的图片, right 中的图片, 距离)`` 的归属关系
    （当 left 与 right 是同一集合时，同一无序对只会返回一次）。

    使用多索引分块：把 64 比特等分成 threshold+1 段。若两条哈希相差不超过
    threshold 位，根据鸽笼原理必有至少一段完全相同，因此它们一定落入同一段
    的同一个桶——先按段取候选集，再精确计算距离，保证不漏召且避免 O(n^2)。
    """
    sample = next(iter(hashes.values()))
    block_count = min(threshold + 1, max(1, int(np.asarray(sample).size)))
    indexes: list[dict[bytes, list[str]]] = [defaultdict(list)
                                             for _ in range(block_count)]
    for key in right:
        for index, block in enumerate(_blocks(hashes[key], block_count)):
            indexes[index][block].append(key)

    found: dict[frozenset, tuple[str, str, int]] = {}
    for key in left:
        bits = hashes[key]
        candidates: set[str] = set()
        for index, block in enumerate(_blocks(bits, block_count)):
            candidates.update(indexes[index][block])
        for other in candidates:
            if other == key:
                continue
            distance = hamming(bits, hashes[other])
            if distance <= threshold:
                identity = frozenset((key, other))
                if identity not in found or distance < found[identity][2]:
                    found[identity] = (key, other, distance)
    return sorted(found.values(), key=lambda p: (p[0], p[1]))


class UnionFind:
    """Tiny union-find used to group near-duplicate images into clusters."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:  # 路径压缩
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def clusters(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for item in self.parent:
            groups[self.find(item)].append(item)
        return {root: sorted(members) for root, members in groups.items()}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a de-duplicated evaluation split.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--out-dir", type=Path,
                        default=PROCESSED_DATA_DIR.parent / "processed_clean")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--val-ratio", type=float, default=VAL_RATIO)
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing output directory")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    out_dir = Path(args.out_dir)
    if out_dir.exists() and not args.force:
        print(f"[clean] {out_dir} 已存在；加 --force 可增量重建", flush=True)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    breed_of = parse_breed_mapping(args.raw_dir)
    images_dir = Path(args.raw_dir) / "images"
    ann_dir = Path(args.raw_dir) / "annotations"
    test_ids = read_split_file(ann_dir / "test.txt")
    trainval_ids = read_split_file(ann_dir / "trainval.txt")
    print(f"[clean] 官方 test={len(test_ids)} trainval={len(trainval_ids)} "
          f"threshold={args.threshold} seed={args.seed} "
          f"val_ratio={args.val_ratio}", flush=True)

    # ---- 1. 计算全部相关图片的 MD5 与 pHash ----
    print("[clean] 计算 MD5 与 pHash ...", flush=True)
    hashes: dict[str, np.ndarray] = {}
    md5s: dict[str, str] = {}
    failures: list[str] = []
    for image_id in test_ids + trainval_ids:
        path = images_dir / f"{image_id}.jpg"
        if not path.exists():
            raise FileNotFoundError(f"image not found: {path}")
        md5s[image_id] = md5_of_file(path)
        digest = image_phash(path)
        if digest is None:
            failures.append(image_id)
        else:
            hashes[image_id] = digest
    if failures:
        raise RuntimeError(
            f"{len(failures)} 张图片无法计算 pHash（scipy 不可用？），"
            f"例如 {failures[:5]}")
    print(f"[clean] 哈希完成：{len(hashes)} 张", flush=True)

    # ---- 2. 排除 train/val 中与 test 近重复的样本 ----
    print("[clean] 检查 train/val 与 test 的近重复 ...", flush=True)
    leak_pairs = find_near_duplicate_pairs(
        trainval_ids, test_ids, hashes, args.threshold)
    nearest_test: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for trainval_id, test_id, distance in leak_pairs:
        nearest_test[trainval_id].append((test_id, distance))

    test_md5: dict[str, list[str]] = defaultdict(list)
    for image_id in test_ids:
        test_md5[md5s[image_id]].append(image_id)

    exclusions: list[dict] = []
    kept_trainval: list[str] = []
    for image_id in trainval_ids:
        identical = test_md5.get(md5s[image_id])
        if identical:
            exclusions.append({
                "image_id": image_id, "class": breed_of[image_id],
                "reason": "identical_md5_with_test",
                "matched_test_ids": identical, "phash_distance": 0})
            continue
        matches = sorted(nearest_test.get(image_id, []), key=lambda m: m[1])
        if matches:
            exclusions.append({
                "image_id": image_id, "class": breed_of[image_id],
                "reason": "near_duplicate_with_test",
                "matched_test_ids": [m[0] for m in matches],
                "phash_distance": matches[0][1]})
            continue
        kept_trainval.append(image_id)
    print(f"[clean] 因与 test 近重复而排除 {len(exclusions)} 张；"
          f"剩余 trainval 池 {len(kept_trainval)} 张", flush=True)

    # ---- 3. 剩余 train/val 的近重复簇分组 ----
    print("[clean] 构建 train/val 近重复簇 ...", flush=True)
    internal_pairs = find_near_duplicate_pairs(
        kept_trainval, kept_trainval, hashes, args.threshold)
    union = UnionFind()
    for image_id in kept_trainval:
        union.find(image_id)
    for a, b, _distance in internal_pairs:
        union.union(a, b)
    clusters = union.clusters()
    cluster_of: dict[str, int] = {}
    for index, (_root, members) in enumerate(
            sorted(clusters.items(), key=lambda kv: kv[1][0]), 1):
        for member in members:
            cluster_of[member] = index
    print(f"[clean] 近重复对 {len(internal_pairs)} 个，簇 {len(clusters)} 个"
          f"（大小 >1 的簇 "
          f"{sum(1 for m in clusters.values() if len(m) > 1)} 个）", flush=True)

    # ---- 4. 簇整体分配到 train/val（原划分多数决，平局归 train） ----
    original = original_train_val_split(trainval_ids, breed_of,
                                        args.seed, args.val_ratio)
    cluster_members: dict[int, list[str]] = defaultdict(list)
    for image_id in kept_trainval:
        cluster_members[cluster_of[image_id]].append(image_id)

    assignment: dict[str, str] = {}
    cluster_decisions: list[dict] = []
    for cluster_index in sorted(cluster_members):
        members = sorted(cluster_members[cluster_index])
        votes: dict[str, int] = defaultdict(int)
        for member in members:
            votes[original[member]] += 1
        decision = "train" if votes["train"] >= votes["val"] else "val"
        for member in members:
            assignment[member] = decision
        if len(members) > 1:
            cluster_decisions.append({
                "cluster_id": cluster_index,
                "members": [{"image_id": m, "class": breed_of[m],
                             "original_split": original[m]} for m in members],
                "votes": dict(votes), "decision": decision,
                "rule": "簇内原划分多数决；平局归 train"})
    print("[clean] 簇归属完成（整簇分配，不跨集合）", flush=True)

    # ---- 5. 类别完备性保护：确保每类在 val 至少 1 个样本 ----
    val_by_class: dict[str, list[str]] = defaultdict(list)
    for image_id, split in assignment.items():
        if split == "val":
            val_by_class[breed_of[image_id]].append(image_id)
    all_classes = sorted(set(breed_of.values()))
    repairs: list[dict] = []
    for breed in all_classes:
        if val_by_class.get(breed):
            continue
        candidates = [i for i in assignment
                      if breed_of[i] == breed and assignment[i] == "train"]
        if not candidates:
            raise RuntimeError(
                f"类别 {breed} 在去重后没有任何可分配给 val 的样本")
        candidates.sort(key=lambda i: (len(cluster_members[cluster_of[i]]), i))
        chosen = candidates[0]
        assignment[chosen] = "val"
        val_by_class[breed].append(chosen)
        repairs.append({
            "class": breed, "image_id": chosen,
            "reason": "该类别在去重后 val 样本为 0，补入 1 个（选所在簇最小者）",
            "cluster_id": cluster_of[chosen]})
    if repairs:
        print(f"[clean] 为 {len(repairs)} 个类别补充了 val 样本", flush=True)

    # ---- 6. 写出 ImageFolder 布局（增量同步，避免整目录删除） ----
    print(f"[clean] 写入 {out_dir} ...", flush=True)
    splits = {
        "train": sorted(i for i, s in assignment.items() if s == "train"),
        "val": sorted(i for i, s in assignment.items() if s == "val"),
        "test": sorted(test_ids),
    }
    sync_stats = sync_directory(out_dir, splits, breed_of, images_dir)
    print(f"[clean] 同步完成：写入 {sync_stats['written']}，"
          f"移除多余 {sync_stats['removed_stale']}", flush=True)

    # ---- 7. 校验 ----
    print("[clean] 校验清洁划分 ...", flush=True)
    verification = verify_clean_split(out_dir, splits, breed_of, hashes,
                                      md5s, args.threshold, cluster_of)

    # ---- 8. 清单 ----
    per_class = {
        split: {breed: sum(1 for i in ids if breed_of[i] == breed)
                for breed in all_classes}
        for split, ids in splits.items()
    }
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": (
            "test = 官方 test.txt 原样全量复制（不排除、不改名、不改标签）；"
            "train/val = 官方 trainval.txt，先剔除与任一官方 test 图片 MD5 "
            "相同或 pHash 距离 <= threshold 的样本，再在剩余样本内按 pHash "
            "阈值构建近重复簇（并查集 + 多索引分块检索），整簇按'原划分多数决、"
            "平局归 train'分配到 train/val；最后保证每个类别在 val 至少 1 个样本"),
        "parameters": {
            "phash_threshold": args.threshold,
            "seed": args.seed,
            "val_ratio": args.val_ratio,
            "phash_algorithm": "灰度 32x32 + 二维 DCT + 低频 8x8 中位数比特",
        },
        "source": {
            "raw_dir": str(args.raw_dir),
            "dataset": "Oxford-IIIT Pet Dataset (official archives)",
            "official_test_ids": len(test_ids),
            "official_trainval_ids": len(trainval_ids),
        },
        "output_dir": str(out_dir),
        "totals": {split: len(ids) for split, ids in splits.items()},
        "num_classes": len(all_classes),
        "per_class_counts": per_class,
        "excluded_from_trainval": {
            "count": len(exclusions),
            "by_reason": {reason: sum(1 for e in exclusions
                                      if e["reason"] == reason)
                          for reason in sorted({e["reason"]
                                                for e in exclusions})},
            "by_class": {breed: sum(1 for e in exclusions
                                    if e["class"] == breed)
                         for breed in sorted({e["class"]
                                              for e in exclusions})},
            "details": exclusions,
        },
        "near_duplicate_clusters": {
            "pair_count": len(internal_pairs),
            "cluster_count": len(clusters),
            "multi_image_cluster_count": sum(
                1 for m in clusters.values() if len(m) > 1),
            "reassigned_clusters": cluster_decisions,
        },
        "val_repairs": repairs,
        "verification": verification,
        "original_split_comparison": {
            "processed": {"train": 3311, "val": 369, "test": 3669,
                          "source": "reports/split_stats.json（U1 重新扫描）"},
            "processed_clean": {split: len(ids) for split, ids in splits.items()},
            "note": ("test 数量不变；train/val 因排除泄漏样本而减少。"
                     "两套划分的训练数据与选模过程已不同，"
                     "指标不可作为同条件直接比较。"),
        },
    }
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.reports_dir / "clean_split_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.reports_dir / "clean_split_report.md").write_text(
        build_markdown(manifest), encoding="utf-8")

    print(f"[clean] totals: {manifest['totals']}, "
          f"classes: {manifest['num_classes']}", flush=True)
    print(f"[clean] verification: {verification}", flush=True)
    print(f"[clean] wrote {manifest_path} 和 clean_split_report.md",
          flush=True)
    print(f"[clean] done in "
          f"{(datetime.now(timezone.utc) - started).total_seconds():.1f}s",
          flush=True)
    return 0 if verification["ok"] else 2


def sync_directory(out_dir: Path, splits: dict[str, list[str]],
                   breed_of: dict[str, str],
                   images_dir: Path) -> dict:
    """把 ImageFolder 布局同步为目标划分。

    复制/覆盖所有应有文件，并**只删除**不再属于划分的多余文件，然后清理空
    目录。刻意避免 ``shutil.rmtree(out_dir)``：整目录删除会一次性删除上万
    个文件，既危险也不利于增量重建。
    """
    expected: dict[str, Path] = {}
    for split, ids in splits.items():
        for image_id in ids:
            destination = (out_dir / split / breed_of[image_id]
                           / f"{image_id}.jpg")
            expected[str(destination)] = images_dir / f"{image_id}.jpg"

    for destination, source in expected.items():
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    existing = {str(p) for p in out_dir.rglob("*.jpg")}
    removed = 0
    for path in sorted(existing - set(expected)):
        Path(path).unlink()
        removed += 1

    for directory in sorted((p for p in out_dir.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()

    return {"written": len(expected), "removed_stale": removed}


def verify_clean_split(out_dir: Path, splits: dict[str, list[str]],
                       breed_of: dict[str, str], hashes: dict[str, np.ndarray],
                       md5s: dict[str, str], threshold: int,
                       cluster_of: dict[str, int]) -> dict:
    """Post-build checks: class mapping, MD5 and pHash cross-split leakage."""
    breeds = sorted(set(breed_of.values()))
    result: dict = {
        "class_sets_identical": True, "class_order_alphabetical": True,
        "md5_cross_split_duplicates": 0, "phash_cross_split_pairs": 0,
        "cluster_straddles": 0, "ok": False}

    for split, ids in splits.items():
        present = sorted(p.name for p in (out_dir / split).iterdir()
                         if p.is_dir())
        if present != breeds:
            result["class_sets_identical"] = False
        if present != sorted(present):
            result["class_order_alphabetical"] = False

    seen_md5: dict[str, str] = {}
    for split, ids in splits.items():
        for image_id in ids:
            digest = md5s[image_id]
            if digest in seen_md5:
                result["md5_cross_split_duplicates"] += 1
            seen_md5[digest] = split

    cross_pairs = 0
    for split in ("train", "val"):
        cross_pairs += len(find_near_duplicate_pairs(
            splits[split], splits["test"], hashes, threshold))
    cross_pairs += len(find_near_duplicate_pairs(
        splits["train"], splits["val"], hashes, threshold))
    result["phash_cross_split_pairs"] = cross_pairs

    straddles = 0
    for cluster_index, members in _group_by_cluster(cluster_of).items():
        splits_seen = {_split_of(m, splits) for m in members}
        if len(splits_seen) > 1:
            straddles += 1
    result["cluster_straddles"] = straddles

    result["ok"] = (
        result["class_sets_identical"]
        and result["class_order_alphabetical"]
        and result["md5_cross_split_duplicates"] == 0
        and result["phash_cross_split_pairs"] == 0
        and result["cluster_straddles"] == 0)
    return result


def _group_by_cluster(cluster_of: dict[str, int]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = defaultdict(list)
    for image_id, cluster_index in cluster_of.items():
        groups[cluster_index].append(image_id)
    return groups


def _split_of(image_id: str, splits: dict[str, list[str]]) -> str:
    for split, ids in splits.items():
        if image_id in ids:
            return split
    return "excluded"


def build_markdown(manifest: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# 清洁（去重）数据划分报告")
    add("")
    add(f"- 生成时间：{manifest['generated_at']}")
    add(f"- 输出目录：`{manifest['output_dir']}`")
    add(f"- 参数：{manifest['parameters']}")
    add(f"- 算法：{manifest['algorithm']}")
    add("")
    add("## 样本数量对比")
    add("")
    add("| 划分 | 原始 `data/processed` | 清洁 `data/processed_clean` | 差值 |")
    add("|---|---|---|---|")
    original = manifest["original_split_comparison"]["processed"]
    clean = manifest["original_split_comparison"]["processed_clean"]
    for split in ("train", "val", "test"):
        add(f"| {split} | {original[split]} | {clean[split]} | "
            f"{clean[split] - original[split]:+d} |")
    add("")
    add(f"> {manifest['original_split_comparison']['note']}")
    add("")
    excluded = manifest["excluded_from_trainval"]
    add("## 从 train/val 中排除的样本")
    add("")
    add(f"- 合计排除 **{excluded['count']}** 张")
    add(f"- 按原因：{excluded['by_reason']}")
    add(f"- 按品种：{excluded['by_class']}")
    add("")
    add("## 近重复簇")
    add("")
    clusters = manifest["near_duplicate_clusters"]
    add(f"- 近重复对：{clusters['pair_count']}")
    add(f"- 簇数：{clusters['cluster_count']}"
        f"（含多张图片的簇 {clusters['multi_image_cluster_count']} 个）")
    add("- 因簇归属而调整的记录见 `clean_split_manifest.json` 的 "
        "`near_duplicate_clusters.reassigned_clusters`")
    add("")
    add("## 校验结果")
    add("")
    add("```json")
    add(json.dumps(manifest["verification"], indent=2, ensure_ascii=False))
    add("```")
    add("")
    if manifest["val_repairs"]:
        add("## val 样本补充记录")
        add("")
        for repair in manifest["val_repairs"]:
            add(f"- {repair['class']}: `{repair['image_id']}` —— "
                f"{repair['reason']}")
        add("")
    add("## 复现方式")
    add("")
    add("```powershell")
    add("cd E:\\CatDogBreedNet")
    add(".venv\\Scripts\\python.exe scripts\\build_clean_split.py")
    add("```")
    add("")
    add("**本脚本只写 `data/processed_clean/`，未修改 `data/processed/`、"
        "官方原始档案或任何模型权重。**")
    add("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
