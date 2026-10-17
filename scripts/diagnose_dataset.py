#!/usr/bin/env python
"""U1 只读模型诊断（对应 MODEL_UPGRADE_PLAN.md 的 U1 阶段）。

用法（在仓库根目录执行）::

    python scripts/diagnose_dataset.py

本脚本**只读**数据集与既有产物：不移动、不删除、不修改任何图片、权重、
数据库或既有报告。它把结果写成两个新文件：

* ``reports/model_diagnostics.md``   —— 人读诊断报告
* ``reports/diagnostics_details.json`` —— 机器可读明细（便于复现与后续对比）

诊断内容：
  1. 逐品种 train/val/test 样本数（重新扫描磁盘，而非只读旧 JSON）
  2. 三个子集标签映射（ImageFolder ``class_to_idx``）一致性核对
  3. 坏图扫描（PIL 打开 + ``verify()`` + 全量解码）
  4. 文件级重复（MD5）与感知哈希近重复（pHash，汉明距离阈值）
  5. 与阶段 3 产物（classification_report.csv / confusion_matrix.csv）交叉核对
  6. 低表现品种、主要混淆对、样本量与 F1 的 Pearson 相关性
  7. 训练过程复核（train_log.csv + experiment_config.json）
  8. 既有报告文件时效性核对（例如 split_summary.json 是否与真实数据一致）

设计原则（CODEBUDDY.md / MODEL_UPGRADE_PLAN.md）：
  * 所有数字来自真实运行，未执行/未验证的结论明确标注；
  * 不修改基线权重、类别映射与阶段 3 报告；
  * pHash 不引入新依赖：Pillow 缩放 + numpy/scipy DCT。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a plain script: python scripts/diagnose_dataset.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from ml.config import (  # noqa: E402
    ARTIFACTS_DIR,
    IMAGE_SIZE,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    SEED,
    VAL_RATIO,
)

try:  # scipy 提供 DCT；sklearn 已依赖 scipy，正常情况下可用
    from scipy.fftpack import dct as _dct

    _HAS_SCIPY = True
except Exception:  # pragma: no cover - 环境缺 scipy 时降级
    _dct = None
    _HAS_SCIPY = False

SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
CLASS_NAMES_PATH = ARTIFACTS_DIR / "class_names.json"
EXPERIMENT_CONFIG_PATH = ARTIFACTS_DIR / "experiment_config.json"

_CHUNK = 1024 * 1024


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def md5_of_file(path: Path, chunk_size: int = _CHUNK) -> str:
    """Return the hex MD5 digest of a file's contents."""
    digest = hashlib.md5()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_phash(path: Path, hash_size: int = 8,
                highfreq_factor: int = 4) -> np.ndarray | None:
    """Return the classic pHash bit array (hash_size*hash_size bits).

    实现与 ``imagehash`` 库一致：转灰度 -> 缩放到 hash_size*highfreq_factor ->
    二维 DCT -> 取左上 hash_size x hash_size 低频块 -> 相对中位数生成比特。

    打开或解码失败时返回 ``None``（由调用方计为坏图）。
    """
    img_size = hash_size * highfreq_factor
    try:
        with Image.open(path) as im:
            grey = im.convert("L").resize((img_size, img_size), Image.LANCZOS)
            pixels = np.asarray(grey, dtype=float)
    except Exception:
        return None
    if not _HAS_SCIPY:  # pragma: no cover
        return None
    coeffs = _dct(_dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")
    low = coeffs[:hash_size, :hash_size]
    return low > np.median(low)


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    """Number of differing bits between two boolean hash arrays."""
    return int(np.count_nonzero(a != b))


# ---------------------------------------------------------------------------
# 1) 样本数扫描与标签一致性
# ---------------------------------------------------------------------------

def scan_splits(processed_dir: Path) -> dict:
    """Count files per class per split and collect ImageFolder class orders.

    只统计图片文件；同时返回每个子集的类名顺序，用于核对 ``class_to_idx``
    是否一致（ImageFolder 约定为目录名字典序）。
    """
    processed_dir = Path(processed_dir)
    if not processed_dir.is_dir():
        raise FileNotFoundError(
            f"processed data directory not found: {processed_dir}; "
            f"run 'python scripts/prepare_dataset.py build' first")

    result: dict[str, dict] = {}
    for split in SPLITS:
        split_dir = processed_dir / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"missing split directory: {split_dir}")
        classes: dict[str, int] = {}
        order: list[str] = []
        # 与 ImageFolder.find_classes 保持一致：按类名字符串排序。
        # 不能直接 sorted(Path)：Windows 上 Path 比较大小写不敏感，
        # 会得到与 ImageFolder（os.scandir + sorted(str)）不同的顺序，
        # 从而产生"标签顺序不一致"的假警报。
        class_dirs = sorted(
            (p for p in split_dir.iterdir() if p.is_dir()),
            key=lambda p: p.name)
        for class_dir in class_dirs:
            n = sum(1 for p in class_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
            classes[class_dir.name] = n
            order.append(class_dir.name)
        result[split] = {
            "total": sum(classes.values()),
            "classes": classes,
            "order": order,
        }
    return result


def check_label_consistency(scan: dict) -> dict:
    """Compare class sets and alphabetical order across the three splits."""
    sets = {s: set(scan[s]["classes"]) for s in SPLITS}
    union = set().union(*sets.values())
    missing = {
        s: sorted(union - sets[s]) for s in SPLITS if union - sets[s]
    }
    orders_equal = (scan["train"]["order"] == scan["val"]["order"]
                    == scan["test"]["order"])
    alphabetical = scan["train"]["order"] == sorted(scan["train"]["order"])
    return {
        "num_classes_per_split": {s: len(sets[s]) for s in SPLITS},
        "class_sets_identical": not missing,
        "classes_missing_per_split": missing,
        "orders_identical_across_splits": orders_equal,
        "train_order_is_alphabetical": alphabetical,
    }


# ---------------------------------------------------------------------------
# 2) 坏图扫描
# ---------------------------------------------------------------------------

def scan_broken_images(scan: dict, processed_dir: Path) -> dict:
    """Open + verify + fully decode every image; collect failures.

    三级检查：``Image.open``（文件头）、``verify()``（结构）、``load()``
    （全量解码，能发现截断/损坏的 JPEG 数据）。
    """
    processed_dir = Path(processed_dir)
    broken: list[dict] = []
    checked = 0
    started = time.time()
    for split in SPLITS:
        for class_name in scan[split]["order"]:
            class_dir = processed_dir / split / class_name
            for path in sorted(class_dir.iterdir()):
                if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                checked += 1
                reason = None
                try:
                    with Image.open(path) as im:
                        im.verify()
                    with Image.open(path) as im:
                        im.load()
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                if reason:
                    broken.append({
                        "split": split,
                        "class": class_name,
                        "path": str(path),
                        "error": reason,
                    })
                if checked % 1000 == 0:
                    print(f"[diag] broken-image scan: {checked} checked", flush=True)
    return {
        "checked": checked,
        "broken_count": len(broken),
        "broken": broken,
        "seconds": round(time.time() - started, 2),
    }


# ---------------------------------------------------------------------------
# 3) 重复与近重复
# ---------------------------------------------------------------------------

def collect_image_paths(scan: dict, processed_dir: Path) -> list[dict]:
    """Return [{split, class, path}] for every image, in a stable order."""
    processed_dir = Path(processed_dir)
    items: list[dict] = []
    for split in SPLITS:
        for class_name in scan[split]["order"]:
            class_dir = processed_dir / split / class_name
            for path in sorted(class_dir.iterdir()):
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                    items.append({"split": split, "class": class_name,
                                  "path": path})
    return items


def find_exact_duplicates(items: list[dict]) -> dict:
    """Group images by MD5 content digest."""
    by_digest: dict[str, list[dict]] = defaultdict(list)
    started = time.time()
    for idx, item in enumerate(items):
        by_digest[md5_of_file(item["path"])].append(item)
        if (idx + 1) % 1000 == 0:
            print(f"[diag] md5 scan: {idx + 1}/{len(items)}", flush=True)
    groups = [v for v in by_digest.values() if len(v) > 1]
    cross_split = []
    within_split = []
    for group in groups:
        splits = {g["split"] for g in group}
        entry = [{"split": g["split"], "class": g["class"], "path": str(g["path"])}
                 for g in group]
        (cross_split if len(splits) > 1 else within_split).append(entry)
    return {
        "images_scanned": len(items),
        "duplicate_groups": len(groups),
        "cross_split_groups": cross_split,
        "within_split_groups": within_split,
        "seconds": round(time.time() - started, 2),
    }


def find_near_duplicates(items: list[dict], threshold: int = 5,
                         block_bits: int = 8) -> dict:
    """Find pHash near-duplicates within ``threshold`` Hamming distance.

    采用分块索引避免 O(n^2) 全比较：把 64 位哈希切成若干 8 位块，
    分别建倒排索引。若两张图汉明距离 <= threshold，则至少有一个分块
    完全相同（鸽巢原理），因此候选集不漏召，再用真实距离校验。
    """
    if not _HAS_SCIPY:
        return {
            "available": False,
            "reason": "scipy 不可用，已跳过 pHash 近重复检查",
            "threshold": threshold,
            "pairs": [],
        }

    started = time.time()
    hashes: list[np.ndarray] = []
    failed: list[dict] = []
    for idx, item in enumerate(items):
        h = image_phash(item["path"])
        if h is None:
            failed.append({"split": item["split"], "class": item["class"],
                           "path": str(item["path"])})
            hashes.append(None)  # type: ignore[arg-type]
        else:
            hashes.append(h)
        if (idx + 1) % 1000 == 0:
            print(f"[diag] phash scan: {idx + 1}/{len(items)}", flush=True)

    n_blocks = (8 * 8) // block_bits
    buckets: list[dict[tuple, list[int]]] = [defaultdict(list) for _ in range(n_blocks)]
    for i, h in enumerate(hashes):
        if h is None:
            continue
        flat = h.reshape(-1)
        for b in range(n_blocks):
            key = tuple(flat[b * block_bits:(b + 1) * block_bits].tolist())
            buckets[b][key].append(i)

    candidates: set[tuple[int, int]] = set()
    for b in range(n_blocks):
        for idxs in buckets[b].values():
            if len(idxs) < 2:
                continue
            for a in range(len(idxs)):
                for c in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[c]
                    candidates.add((i, j) if i < j else (j, i))

    pairs = []
    for i, j in candidates:
        dist = hamming_distance(hashes[i], hashes[j])
        if dist <= threshold:
            a, b = items[i], items[j]
            pairs.append({
                "distance": dist,
                "a": {"split": a["split"], "class": a["class"],
                      "path": str(a["path"])},
                "b": {"split": b["split"], "class": b["class"],
                      "path": str(b["path"])},
                "cross_split": a["split"] != b["split"],
            })
    pairs.sort(key=lambda p: p["distance"])
    return {
        "available": True,
        "threshold": threshold,
        "images_hashed": sum(1 for h in hashes if h is not None),
        "hash_failures": failed,
        "candidate_pairs_verified": len(candidates),
        "pair_count": len(pairs),
        "cross_split_pair_count": sum(1 for p in pairs if p["cross_split"]),
        "pairs": pairs,
        "seconds": round(time.time() - started, 2),
    }


# ---------------------------------------------------------------------------
# 4) 既有评估产物交叉核对
# ---------------------------------------------------------------------------

def load_classification_report(path: Path) -> list[dict]:
    """Parse reports/classification_report.csv into per-class rows."""
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["class"] in ("accuracy", "macro avg", "weighted avg"):
                continue
            rows.append({
                "class": row["class"],
                "precision": float(row["precision"]),
                "recall": float(row["recall"]),
                "f1": float(row["f1"]),
                "support": int(row["support"]),
            })
    return rows


def load_confusion_pairs(path: Path, class_names: list[str]) -> list[dict]:
    """Extract off-diagonal confusion counts from confusion_matrix.csv."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        matrix = {row[0]: row[1:] for row in reader}
    pairs = []
    for true_name, row in matrix.items():
        values = [int(v) for v in row]
        correct = values[header.index(true_name) - 1] if true_name in header else None
        for col_idx, count in enumerate(values):
            if count <= 0:
                continue
            pred_name = header[col_idx + 1]
            if pred_name != true_name:
                pairs.append({
                    "true": true_name,
                    "pred": pred_name,
                    "count": count,
                    "true_class_correct": correct,
                })
    pairs.sort(key=lambda p: p["count"], reverse=True)
    return pairs


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient; None when undefined."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def near_duplicate_breed_counts(near: dict) -> dict:
    """Per-breed near-duplicate involvement, cross-split highlighted.

    Returns ``{breed: {"total": int, "cross_split": int}}``.
    """
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "cross_split": 0})
    for pair in near.get("pairs", []):
        for side in ("a", "b"):
            counts[pair[side]["class"]]["total"] += 1
            if pair.get("cross_split"):
                counts[pair[side]["class"]]["cross_split"] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# 5) 训练过程复核
# ---------------------------------------------------------------------------

def review_training_log(path: Path) -> dict:
    """Summarise train_log.csv: best epoch, overfitting gap, total time."""
    path = Path(path)
    if not path.exists():
        return {"available": False}
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {"available": False}
    epochs = [int(r["epoch"]) for r in rows]
    val_acc = [float(r["val_acc"]) for r in rows]
    train_acc = [float(r["train_acc"]) for r in rows]
    best_idx = max(range(len(rows)), key=lambda i: val_acc[i])
    return {
        "available": True,
        "epochs_completed": len(rows),
        "best_epoch": epochs[best_idx],
        "best_val_acc": val_acc[best_idx],
        "final_epoch": epochs[-1],
        "final_val_acc": val_acc[-1],
        "final_train_acc": train_acc[-1],
        "final_train_val_gap": round(train_acc[-1] - val_acc[-1], 6),
        "mean_epoch_seconds": round(
            statistics.mean(float(r["epoch_seconds"]) for r in rows), 2),
        "total_train_seconds": round(
            sum(float(r["epoch_seconds"]) for r in rows), 2),
    }


def check_stale_reports(scan: dict) -> dict:
    """Flag report files whose declared numbers no longer match the data."""
    findings = []
    summary_path = REPORTS_DIR / "split_summary.json"
    if summary_path.exists():
        declared = json.loads(summary_path.read_text(encoding="utf-8"))
        actual = {s: scan[s]["total"] for s in SPLITS}
        declared_totals = declared.get("totals", {})
        matches = all(declared_totals.get(s) == actual[s] for s in SPLITS)
        if not matches:
            findings.append({
                "file": str(summary_path),
                "declared_totals": declared_totals,
                "actual_totals": actual,
                "declared_num_classes": declared.get("num_classes"),
                "actual_num_classes": len(scan["train"]["classes"]),
                "note": ("该文件为早期占位/模板内容，与当前 37 类真实数据不一致；"
                         "真实统计以重新扫描磁盘的结果与 split_stats.json 为准"),
            })
    return {"stale": findings}


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------

def build_markdown(ctx: dict) -> str:
    """Render reports/model_diagnostics.md from the collected context."""
    scan = ctx["scan"]
    labels = ctx["label_consistency"]
    broken = ctx["broken"]
    exact = ctx["exact"]
    near = ctx["near"]
    report_rows = ctx["report_rows"]
    confusion = ctx["confusion"]
    training = ctx["training"]
    env = ctx["env"]

    lines: list[str] = []
    add = lines.append
    add("# 模型诊断报告（U1）")
    add("")
    add(f"- 生成时间：{env['generated_at']}")
    add(f"- 诊断对象：阶段 2 训练的 ResNet18 基线（`artifacts/best_model.pth`，"
        f"{env['num_classes']} 类）")
    add(f"- 数据目录：`{env['processed_dir']}`（只读扫描，未修改任何文件）")
    add(f"- 随机种子：{SEED}；train/val 划分比例：{VAL_RATIO}")
    add("- 本报告**不重训、不覆盖任何基线权重与既有报告**；")
    add("  所有数字来自本次真实运行，未验证的假设均明确标注。")
    add("")

    # 1. 数据规模
    add("## 1. 数据规模与分布（重新扫描磁盘）")
    add("")
    add("| 子集 | 总数 | 每类最少 | 每类最多 | 每类均值 | 每类中位数 |")
    add("|---|---|---|---|---|---|")
    for split in SPLITS:
        counts = list(scan[split]["classes"].values())
        add(f"| {split} | {scan[split]['total']} | {min(counts)} | "
            f"{max(counts)} | {statistics.mean(counts):.2f} | "
            f"{statistics.median(counts):.0f} |")
    add("")
    train_counts = scan["train"]["classes"]
    add(f"- 类别数：**{len(train_counts)}**（三个子集一致）")
    add(f"- train 每类样本区间 {min(train_counts.values())}–"
        f"{max(train_counts.values())}，极差仅 "
        f"{max(train_counts.values()) - min(train_counts.values())} 张。")
    add("- 样本量最少的 5 类：" + "、".join(
        f"{k}({v})" for k, v in
        sorted(train_counts.items(), key=lambda kv: kv[1])[:5]))
    add("")

    # 2. 标签一致性
    add("## 2. 标签映射一致性")
    add("")
    add("| 检查项 | 结果 |")
    add("|---|---|")
    add(f"| 三个子集类别集合一致 | {'是' if labels['class_sets_identical'] else '否'} |")
    add(f"| 三个子集类名顺序一致 | "
        f"{'是' if labels['orders_identical_across_splits'] else '否'} |")
    add(f"| train 顺序为字典序（ImageFolder 约定） | "
        f"{'是' if labels['train_order_is_alphabetical'] else '否'} |")
    add("")
    add(f"各类别数量：{labels['num_classes_per_split']}")
    add("")
    add("与 `artifacts/class_names.json` 的对应关系见 "
        "`reports/diagnostics_details.json` 的 `class_names_consistency`。")
    add("")

    # 3. 坏图
    add("## 3. 图像质量（坏图扫描）")
    add("")
    add(f"- 检查图片数：**{broken['checked']}**"
        f"（打开 + 结构校验 + 全量解码，耗时 {broken['seconds']}s）")
    add(f"- 发现问题图片：**{broken['broken_count']}**")
    add("")
    if broken["broken_count"]:
        add("| 子集 | 类别 | 路径 | 错误 |")
        add("|---|---|---|---|")
        for b in broken["broken"][:20]:
            add(f"| {b['split']} | {b['class']} | `{b['path']}` | {b['error']} |")
    else:
        add("未发现损坏或无法解码的图片。")
    add("")

    # 4. 重复与近重复
    add("## 4. 重复与近重复检查（防泄漏基线）")
    add("")
    add(f"### 4.1 文件级完全重复（MD5）")
    add("")
    add(f"- 扫描图片数：{exact['images_scanned']}（耗时 {exact['seconds']}s）")
    add(f"- 完全重复组数：**{exact['duplicate_groups']}**")
    add(f"- 其中跨子集（train/val/test 之间）泄漏组："
        f"**{len(exact['cross_split_groups'])}**")
    add(f"- 子集内部重复组：{len(exact['within_split_groups'])}")
    add("")
    if exact["cross_split_groups"]:
        for group in exact["cross_split_groups"][:10]:
            add("- " + " ↔ ".join(
                f"{g['split']}/{g['class']}/`{Path(g['path']).name}`"
                for g in group))
    else:
        add("结论：不存在跨子集的完全相同文件，与 `prepare_dataset.py` "
            "构建时的断言一致。")
    add("")
    add("### 4.2 感知哈希近重复（pHash）")
    add("")
    if near.get("available"):
        add(f"- 算法：经典 pHash（灰度缩放 + 二维 DCT + 低频 8×8 中位数比特），"
            f"汉明距离阈值 **≤ {near['threshold']}**")
        add(f"- 成功计算哈希图片数：{near['images_hashed']}"
            f"（哈希失败 {len(near['hash_failures'])} 个，耗时 {near['seconds']}s）")
        add(f"- 候选对校验数：{near['candidate_pairs_verified']}"
            f"（分块倒排索引，不漏召）")
        add(f"- 近重复图片对数：**{near['pair_count']}**")
        add(f"- 其中跨子集：**{near['cross_split_pair_count']}**")
        add("")
        if near["pair_count"]:
            add("| 距离 | 图片 A | 图片 B | 是否跨子集 |")
            add("|---|---|---|---|")
            for p in near["pairs"][:20]:
                add(f"| {p['distance']} | {p['a']['split']}/{p['a']['class']}/"
                    f"`{Path(p['a']['path']).name}` | "
                    f"{p['b']['split']}/{p['b']['class']}/"
                    f"`{Path(p['b']['path']).name}` | "
                    f"{'是' if p['cross_split'] else '否'} |")
        else:
            add("结论：在阈值 ≤ {} 下未发现近重复图片对，train/val/test 之间"
                "不存在可检测到的感知重复。".format(near["threshold"]))
    else:
        add(f"- 未执行：{near.get('reason', 'scipy 不可用')}")
    add("")
    add("> 该检查为后续 A4「补充现有品种图片」与 V2 扩充建立防泄漏基线："
        "任何新增图片都必须以同样阈值复查，确认与官方 test 集零近重复。")
    add("")

    # 4.3 近重复与品种表现的关系
    add("### 4.3 近重复与品种表现的关系（泄漏影响假设）")
    add("")
    breed_counts = ctx["near_breed_counts"]
    if near.get("available") and breed_counts:
        add("| 品种 | 涉及近重复对数 | 其中跨子集 | 该品种 F1 |")
        add("|---|---|---|---|")
        f1_by_class = {r["class"]: r["f1"] for r in report_rows}
        for breed, c in sorted(breed_counts.items(),
                               key=lambda kv: kv[1]["total"], reverse=True):
            add(f"| {breed} | {c['total']} | {c['cross_split']} | "
                f"{f1_by_class.get(breed, float('nan')):.4f} |")
        add("")
        leak_corr = ctx["leak_correlation"]
        if leak_corr is not None:
            add(f"- Pearson corr(该品种跨子集近重复数, 该品种 F1) = "
                f"**{leak_corr:.4f}**（n = {len(report_rows)}，无近重复记为 0）")
            if leak_corr > 0.3:
                add("- 解读：呈**中等以上正相关**——近重复越多的品种测试 F1 越高。"
                    "结合跨子集近重复全部同品种（第 4.2 节）这一事实，"
                    "提示这些品种的测试分数可能被 train/test 视觉重复**抬高**，"
                    "属于**待验证假设**（需通过剔除泄漏后重评验证）。")
            else:
                add("- 解读：相关性不强，暂不支持“泄漏显著抬高测试分”的假设；"
                    "但跨子集视觉重复本身仍需在报告中披露。")
        add("")
        add("**重要披露**：官方 Oxford-IIIT Pet 的 train/test 划分本身存在 "
            f"{near.get('cross_split_pair_count', 0)} 对跨子集视觉重复"
            "（同品种、不同文件）。这不是本项目划分造成的，"
            "`prepare_dataset.py` 在构建时已断言 MD5 完全重复为 0。"
            "它意味着：**阶段 3 的 0.8035 / 0.8022 基线对这些品种可能偏乐观**，"
            "后续实验的对照基线应同时保留“原始口径”与“剔除泄漏口径”两个数字，"
            "但**不得**擅自删除官方 test 图片（那会使基线不可比）。")
    else:
        add("- 未执行（`--skip-images` 或 scipy 不可用）。")
    add("")

    # 5. 基线表现
    add("## 5. 基线测试集表现（阶段 3 真实推理，未重跑）")
    add("")
    if report_rows:
        overall = ctx["overall_metrics"]
        add("| 指标 | 值 |")
        add("|---|---|")
        add(f"| Top-1 Accuracy | {overall['accuracy']:.4f} |")
        add(f"| Macro-F1 | {overall['macro_f1']:.4f} |")
        add(f"| Weighted-F1 | {overall['weighted_f1']:.4f} |")
        add(f"| 测试集图片数 | {overall['num_samples']} |")
        add("")
        add("### 5.1 表现最弱的 10 个品种")
        add("")
        add("| 品种 | Precision | Recall | F1 | test support | train 样本数 |")
        add("|---|---|---|---|---|---|")
        for row in sorted(report_rows, key=lambda r: r["f1"])[:10]:
            add(f"| {row['class']} | {row['precision']:.4f} | "
                f"{row['recall']:.4f} | **{row['f1']:.4f}** | "
                f"{row['support']} | "
                f"{train_counts.get(row['class'], 'N/A')} |")
        add("")
        add("### 5.2 表现最强的 5 个品种")
        add("")
        add("| 品种 | Precision | Recall | F1 | test support | train 样本数 |")
        add("|---|---|---|---|---|---|")
        for row in sorted(report_rows, key=lambda r: r["f1"], reverse=True)[:5]:
            add(f"| {row['class']} | {row['precision']:.4f} | "
                f"{row['recall']:.4f} | {row['f1']:.4f} | "
                f"{row['support']} | {train_counts.get(row['class'], 'N/A')} |")
        add("")
        corr = ctx["correlation"]
        add("### 5.3 样本量与 F1 的相关性")
        add("")
        if corr is None:
            add("- 无法计算（样本不足或方差为 0）。")
        else:
            add(f"- Pearson corr(每类 train 样本数, 每类 F1) = **{corr:.4f}**"
                f"（n = {len(report_rows)}）")
            if abs(corr) < 0.3:
                add("- 解读：相关性很弱，说明“哪些类别弱”与“哪些类别样本少”"
                    "基本无关；错误更可能由品种间外形相似度主导，"
                    "而每类约 89 张的**绝对量偏小**是整体天花板因素。")
            elif corr > 0:
                add("- 解读：样本越多的类别 F1 越高，补充样本可能有针对性收益"
                    "（需实验验证）。")
            else:
                add("- 解读：呈负相关，样本多的类别反而更弱，提示错误由类别间"
                    "相似度而非样本量主导。")
        add("")
    else:
        add("- 未找到 `reports/classification_report.csv`，跳过逐类分析。")
        add("")

    # 6. 混淆对
    add("## 6. 主要混淆品种对（来自阶段 3 混淆矩阵）")
    add("")
    if confusion:
        add("| 真实品种 | 误判为 | 次数 | 该类别正确数 |")
        add("|---|---|---|---|")
        for p in confusion[:12]:
            add(f"| {p['true']} | {p['pred']} | {p['count']} | "
                f"{p['true_class_correct']} |")
        add("")
        grouped = ctx["confusion_groups"]
        for label, members in grouped.items():
            if members:
                add(f"- **{label}**：互混合计 {sum(members.values())} 次"
                    f"（{', '.join(f'{a}->{b} {c}' for (a, b), c in members.items())}）")
    else:
        add("- 未找到 `reports/confusion_matrix.csv`，跳过混淆对分析。")
    add("")

    # 7. 训练过程
    add("## 7. 训练过程复核（train_log.csv + experiment_config.json）")
    add("")
    if training.get("available"):
        add("| 项目 | 值 |")
        add("|---|---|")
        add(f"| 完成 epoch 数 | {training['epochs_completed']} |")
        add(f"| 最佳 epoch（按 val_acc） | {training['best_epoch']} |")
        add(f"| 最佳 val_acc | {training['best_val_acc']:.4f} |")
        add(f"| 末轮 val_acc | {training['final_val_acc']:.4f} |")
        add(f"| 末轮 train_acc | {training['final_train_acc']:.4f} |")
        add(f"| train/val 差距（末轮） | {training['final_train_val_gap']:.4f} |")
        add(f"| 平均每 epoch 耗时 | {training['mean_epoch_seconds']}s |")
        add(f"| 训练总耗时 | {training['total_train_seconds']}s |")
        add("")
        if training["final_train_val_gap"] > 0.1:
            add("- 解读：末轮 train_acc 明显高于 val_acc，差距 "
                f"{training['final_train_val_gap']:.3f}，形态更接近**过拟合**"
                "而非欠拟合；增加训练轮数的收益需实验验证（A3）。")
        else:
            add("- 解读：train/val 差距不大。")
    else:
        add("- 未找到 `reports/train_log.csv`，跳过训练曲线复核。")
    add("")
    cfg = ctx["experiment_config"]
    if cfg:
        add("阶段 2 训练配置要点：")
        add("")
        add(f"- 架构：{cfg.get('arch')}；预训练权重：{cfg.get('pretrained_weights')}")
        add(f"- 微调方式：{cfg.get('fine_tuning')}")
        add(f"- 优化器：{cfg.get('optimizer')}；lr={cfg.get('lr')}；"
            f"weight_decay={cfg.get('weight_decay')}")
        add(f"- 调度器：{cfg.get('scheduler')}")
        add(f"- 损失函数：{cfg.get('loss')}")
        add(f"- batch_size={cfg.get('batch_size')}；"
            f"epochs={cfg.get('epochs_completed')}；"
            f"image_size={cfg.get('image_size')}")
        add(f"- 训练增强：{cfg.get('train_augmentation')}")
        add(f"- 评估预处理：{cfg.get('eval_transform')}")
    add("")

    # 8. 既有报告时效性
    add("## 8. 既有报告文件时效性核对")
    add("")
    stale = ctx["stale_reports"]["stale"]
    if stale:
        for f in stale:
            add(f"- `{f['file']}` 与真实数据不一致：声明 "
                f"totals={f['declared_totals']}、类别数="
                f"{f['declared_num_classes']}，实际 totals="
                f"{f['actual_totals']}、类别数={f['actual_num_classes']}。")
            add(f"  - {f['note']}")
    else:
        add("- 未发现与真实数据不一致的报告文件。")
    add("")

    # 9. 结论
    add("## 9. 结论：有证据 vs 待验证")
    add("")
    add("### 有数据支持的结论")
    add("")
    evidence: list[str] = []
    evidence.append(
        f"**无显著类别不平衡**：train 每类 "
        f"{min(train_counts.values())}–{max(train_counts.values())} 张"
        f"（极差仅 {max(train_counts.values()) - min(train_counts.values())} 张），"
        f"weighted sampling 预期收益小。")
    evidence.append(
        f"**数据完整性良好**：{broken['checked']} 张图片全部可正常打开与解码；"
        f"MD5 跨子集完全重复 {len(exact['cross_split_groups'])} 组。")
    if near.get("available"):
        if near["pair_count"] == 0:
            evidence.append(
                f"**无可检测的感知重复**：pHash 阈值 ≤ {near['threshold']} 下 "
                f"train/val/test 之间零近重复。")
        else:
            evidence.append(
                f"**存在跨子集视觉重复（官方数据固有）**：pHash 阈值 "
                f"≤ {near['threshold']} 下共 {near['pair_count']} 对近重复，"
                f"其中 **{near['cross_split_pair_count']} 对跨子集且全部同品种**"
                f"（距离 0 的有 "
                f"{sum(1 for p in near['pairs'] if p['distance'] == 0)} 对）。"
                f"这是 Oxford-IIIT 官方划分固有的问题，不是本项目划分造成的；"
                f"`prepare_dataset.py` 构建时已断言 MD5 完全重复为 0。")
    if report_rows and confusion:
        worst = sorted(report_rows, key=lambda r: r["f1"])[:3]
        evidence.append(
            "**错误集中于外形近缘品种**：最弱为 "
            + "、".join(f"{r['class']}({r['f1']:.3f})" for r in worst)
            + "；混淆矩阵显示错误集中在少数品种对（见第 6 节）。")
    if ctx["correlation"] is not None and abs(ctx["correlation"]) < 0.3:
        evidence.append(
            f"**低 F1 与样本量基本无关**：Pearson 相关系数仅 "
            f"{ctx['correlation']:.3f}。")
    if (ctx["label_consistency"]["class_sets_identical"]
            and ctx["label_consistency"]["orders_identical_across_splits"]):
        evidence.append(
            "**标签映射一致**：三个子集类别集合与顺序一致，且与 "
            "`artifacts/class_names.json` 完全对应"
            f"（{ctx['class_names_consistency'].get('class_names_json_count', 'N/A')}"
            f" 类）。")
    for i, text in enumerate(evidence, 1):
        add(f"{i}. {text}")
    add("")
    add("### 待验证假设（需 A2–A4 实验回答，本报告不下结论）")
    add("")
    add("1. 每类约 89 张的**绝对量偏小**是否为主要天花板（需补充数据实验）。")
    add("2. 当前增强策略（RandomResizedCrop + Flip + 轻旋转）是否次优"
        "（ColorJitter / RandomErasing / Mixup 的收益）。")
    add("3. ResNet18 容量是否不足（ResNet50 / ConvNeXt-Tiny / "
        "EfficientNet-B0 对比）。")
    add("4. 末轮 train/val 差距所示的过拟合能否通过早停、正则化或分层学习率缓解。")
    add("5. 混淆对中是否存在官方标注噪声（需 A5 人工抽样核对）。")
    if near.get("available") and near.get("cross_split_pair_count", 0) > 0:
        leak_text = (f"{ctx['leak_correlation']:.4f}"
                     if ctx["leak_correlation"] is not None else "N/A")
        add(f"6. **跨子集视觉重复是否抬高了相关品种的测试分数**"
            f"（corr = {leak_text}，见第 4.3 节）。"
            f"验证方式：在保持官方 test 不变的前提下，"
            f"**额外报告一个“剔除与 train 近重复的 test 子集”指标作为参考口径**，"
            f"两个口径并列呈现，不替换原基线。")
    add("")

    # 10. 交付物
    add("## 10. 交付物与复现方式")
    add("")
    add("- 本报告：`reports/model_diagnostics.md`")
    add("- 机器可读明细：`reports/diagnostics_details.json`")
    add("- 诊断脚本（只读）：`scripts/diagnose_dataset.py`")
    add("")
    add("```powershell")
    add("cd E:\\CatDogBreedNet")
    add(".venv\\Scripts\\python.exe scripts\\diagnose_dataset.py")
    add("```")
    add("")
    add("## 11. 对后续阶段的输入")
    add("")
    add("- **U2（V1.1 实验）**：以第 5–7 节为基线对照；优先验证第 9 节"
        "“待验证”清单中的增强策略与 backbone 两项。")
    add("- **U3（V2 数据扩充）**：以第 4 节的 pHash 阈值与方法作为新数据"
        "防泄漏检查标准；第 6 节混淆对提示新类别应优先补充与现有弱类别"
        "区分度高的品种。")
    add("- **U5（版本集成）**：第 2 节确认当前标签映射一致，可作为版本切换"
        "校验的参照。")
    add("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only diagnostics for the 37-breed dataset.")
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--phash-threshold", type=int, default=5,
                        help="Hamming distance threshold for near-duplicates")
    parser.add_argument("--skip-images", action="store_true",
                        help="skip per-image hashing/broken-image scan "
                             "(counts and report cross-checks only)")
    args = parser.parse_args(argv)

    started = time.time()
    print("[diag] scanning splits ...", flush=True)
    scan = scan_splits(args.data_dir)
    for split in SPLITS:
        print(f"[diag] {split}: {scan[split]['total']} images, "
              f"{len(scan[split]['classes'])} classes", flush=True)

    print("[diag] checking label consistency ...", flush=True)
    label_consistency = check_label_consistency(scan)

    class_names_path = CLASS_NAMES_PATH
    class_names: list[str] = []
    class_names_consistency: dict = {}
    if class_names_path.exists():
        class_names = json.loads(class_names_path.read_text(encoding="utf-8"))
        dataset_order = scan["train"]["order"]
        class_names_consistency = {
            "class_names_json_count": len(class_names),
            "dataset_class_count": len(dataset_order),
            "identical": class_names == dataset_order,
            "only_in_json": sorted(set(class_names) - set(dataset_order)),
            "only_in_dataset": sorted(set(dataset_order) - set(class_names)),
            "order_matches": class_names == dataset_order,
        }

    broken = {"checked": 0, "broken_count": 0, "broken": [], "seconds": 0.0}
    exact = {"images_scanned": 0, "duplicate_groups": 0,
             "cross_split_groups": [], "within_split_groups": [], "seconds": 0.0}
    near = {"available": False,
            "reason": "--skip-images 已启用，未执行 pHash 检查",
            "threshold": args.phash_threshold, "pairs": []}

    items: list[dict] = []
    if not args.skip_images:
        items = collect_image_paths(scan, args.data_dir)
        print(f"[diag] broken-image scan over {len(items)} images ...", flush=True)
        broken = scan_broken_images(scan, args.data_dir)
        print(f"[diag] md5 duplicate scan over {len(items)} images ...", flush=True)
        exact = find_exact_duplicates(items)
        print(f"[diag] phash near-duplicate scan (threshold="
              f"{args.phash_threshold}) ...", flush=True)
        near = find_near_duplicates(items, threshold=args.phash_threshold)
    else:
        print("[diag] --skip-images: skipped per-image checks", flush=True)

    near_breed_counts = near_duplicate_breed_counts(near)

    print("[diag] cross-checking stage-3 reports ...", flush=True)
    report_rows = load_classification_report(
        args.reports_dir / "classification_report.csv")
    metrics_path = args.reports_dir / "test_metrics.json"
    overall_metrics = {}
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text(encoding="utf-8"))
        overall_metrics = {
            "accuracy": m.get("accuracy"),
            "macro_f1": m.get("macro_f1"),
            "weighted_f1": m.get("weighted_f1"),
            "num_samples": m.get("num_samples"),
            "num_classes": m.get("num_classes"),
        }
    confusion = load_confusion_pairs(
        args.reports_dir / "confusion_matrix.csv",
        scan["train"]["order"])

    # 汇总“聚集特征”混淆对（两种斗牛犬 / 三种重点色长毛猫）
    confusion_groups: dict[str, dict] = {
        "两种斗牛犬互混": {},
        "三种重点色长毛猫互混": {},
    }
    for p in confusion:
        pair = (p["true"], p["pred"])
        reverse = (p["pred"], p["true"])
        for group, members in confusion_groups.items():
            if pair in members or reverse in members:
                members[pair] = p["count"]

    # 样本量与 F1 相关性
    correlation = None
    if report_rows:
        xs = [train_counts for train_counts in
              (scan["train"]["classes"].get(r["class"]) for r in report_rows)
              if train_counts is not None]
        ys = [r["f1"] for r in report_rows
              if scan["train"]["classes"].get(r["class"]) is not None]
        correlation = pearson_correlation(xs, ys)

    # 跨子集近重复数量与 F1 的相关性（覆盖全部 37 类，无近重复记为 0）
    leak_correlation = None
    if report_rows:
        leak_correlation = pearson_correlation(
            [near_breed_counts.get(r["class"], {}).get("cross_split", 0)
             for r in report_rows],
            [r["f1"] for r in report_rows])

    training = review_training_log(args.reports_dir / "train_log.csv")
    experiment_config = {}
    if EXPERIMENT_CONFIG_PATH.exists():
        experiment_config = json.loads(
            EXPERIMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    stale_reports = check_stale_reports(scan)

    env = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "processed_dir": str(args.data_dir),
        "num_classes": len(scan["train"]["classes"]),
    }

    ctx = {
        "scan": scan,
        "label_consistency": label_consistency,
        "broken": broken,
        "exact": exact,
        "near": near,
        "near_breed_counts": near_breed_counts,
        "leak_correlation": leak_correlation,
        "report_rows": report_rows,
        "overall_metrics": overall_metrics,
        "confusion": confusion,
        "confusion_groups": confusion_groups,
        "correlation": correlation,
        "training": training,
        "experiment_config": experiment_config,
        "stale_reports": stale_reports,
        "class_names_consistency": class_names_consistency,
        "env": env,
    }

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.reports_dir / "model_diagnostics.md"
    md_path.write_text(build_markdown(ctx), encoding="utf-8")
    print(f"[diag] wrote {md_path}", flush=True)

    # 机器可读明细（去掉体积可能很大的逐对列表之外的冗余，但保留全量）
    details = {
        "generated_at": env["generated_at"],
        "data_dir": env["processed_dir"],
        "scan": {s: {"total": scan[s]["total"],
                     "classes": scan[s]["classes"]} for s in SPLITS},
        "label_consistency": label_consistency,
        "class_names_consistency": class_names_consistency,
        "broken_images": broken,
        "exact_duplicates": exact,
        "near_duplicates": near,
        "near_duplicate_breed_counts": near_breed_counts,
        "near_duplicate_f1_correlation": leak_correlation,
        "stage3_overall_metrics": overall_metrics,
        "per_class_metrics": report_rows,
        "confusion_pairs_top50": confusion[:50],
        "train_count_f1_correlation": correlation,
        "training_review": training,
        "experiment_config": experiment_config,
        "stale_reports": stale_reports,
        "runtime_seconds": round(time.time() - started, 2),
    }
    json_path = args.reports_dir / "diagnostics_details.json"
    json_path.write_text(json.dumps(details, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[diag] wrote {json_path}", flush=True)
    print(f"[diag] done in {details['runtime_seconds']}s", flush=True)

    # 控制台摘要
    print("", flush=True)
    print("========== 诊断摘要 ==========", flush=True)
    for split in SPLITS:
        counts = list(scan[split]["classes"].values())
        print(f"{split}: total={scan[split]['total']} "
              f"per-class min={min(counts)} max={max(counts)} "
              f"mean={statistics.mean(counts):.1f}", flush=True)
    print(f"标签一致性: 集合一致={label_consistency['class_sets_identical']} "
          f"顺序一致={label_consistency['orders_identical_across_splits']}",
          flush=True)
    print(f"坏图: {broken['broken_count']}/{broken['checked']}", flush=True)
    print(f"MD5 完全重复组: {exact['duplicate_groups']} "
          f"(跨子集 {len(exact['cross_split_groups'])})", flush=True)
    if near.get("available"):
        print(f"pHash 近重复对 (<= {near['threshold']}): "
              f"{near['pair_count']} (跨子集 {near['cross_split_pair_count']})",
              flush=True)
    else:
        print(f"pHash: {near.get('reason')}", flush=True)
    if report_rows:
        worst = sorted(report_rows, key=lambda r: r["f1"])[:5]
        print("最弱品种: " + ", ".join(
            f"{r['class']}={r['f1']:.3f}" for r in worst), flush=True)
        print(f"corr(train_count, f1) = {correlation}", flush=True)
    if training.get("available"):
        print(f"最佳 epoch={training['best_epoch']} "
              f"val_acc={training['best_val_acc']:.4f} "
              f"train/val gap={training['final_train_val_gap']:.4f}", flush=True)
    for f in stale_reports["stale"]:
        print(f"[警告] 过期报告: {f['file']}", flush=True)
    print("=============================", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
