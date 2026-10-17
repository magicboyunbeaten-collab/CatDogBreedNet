#!/usr/bin/env python
"""A5 难例分析（MODEL_UPGRADE_PLAN.md 的 A5 阶段）。

用法（在仓库根目录执行）::

    python scripts/analyze_hard_examples.py [--per-pair 20] [--top-pairs 8]

对基线模型在官方 test 集上的错误做结构化抽样，产出可人工复核的 case 列表：

  1. 用 ``artifacts/best_model.pth`` 对官方 test 集推理一次（只读，不重训）；
  2. 从 ``reports/confusion_matrix.csv`` 取错误最多的若干混淆对；
  3. 每对确定性抽样（seed=42）至多 ``--per-pair`` 个误分类样本；
  4. 对每个样本检查它与 train/val 的 pHash 近重复——若与**另一标签**的
     train 图片近重复，是标注噪声/泄漏的间接证据；
  5. 把抽样图片**复制**到 ``.cache/A5_review/<pair>/``（仅复制，不移动或
     修改原始数据）供人工目检，并写出 case 列表与统计。

产物：
  * ``reports/A5_hard_examples.json``  —— 机器可读明细
  * ``reports/A5_hard_examples.md``    —— 人读报告（含人工复核指引）

本脚本不对任何样本下“标注错误”的最终结论——那是人工复核后才能确定的；
它只提供可复核的证据与清单（CODEBUDDY.md：未验证的结论必须标注）。
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

from ml.config import (  # noqa: E402
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    SEED,
)
from ml.dataset import build_dataloaders  # noqa: E402
from ml.model import BEST_WEIGHTS_PATH, load_checkpoint, resolve_device  # noqa: E402

try:
    from scipy.fftpack import dct as _dct

    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _dct = None
    _HAS_SCIPY = False

PHASH_THRESHOLD = 5


def image_phash(path: Path, hash_size: int = 8,
                highfreq_factor: int = 4) -> np.ndarray | None:
    """Classic pHash bit array; ``None`` when the image cannot be decoded."""
    if not _HAS_SCIPY:
        return None
    img_size = hash_size * highfreq_factor
    try:
        with Image.open(path) as im:
            grey = im.convert("L").resize((img_size, img_size), Image.LANCZOS)
            pixels = np.asarray(grey, dtype=float)
    except Exception:
        return None
    coeffs = _dct(_dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")
    return coeffs[:hash_size, :hash_size] > np.median(
        coeffs[:hash_size, :hash_size])


@torch.no_grad()
def collect_test_predictions(model, loader, device, class_names) -> list[dict]:
    """One pass over the test set; keep path, true/pred label and confidence."""
    model.eval()
    dataset = loader.dataset
    records: list[dict] = []
    cursor = 0
    for images, labels in loader:
        logits = model(images.to(device))
        probabilities = torch.softmax(logits, dim=1)
        confidence, predicted = probabilities.max(dim=1)
        for offset in range(images.size(0)):
            path, _ = dataset.samples[cursor + offset]
            records.append({
                "path": str(path),
                "true": class_names[int(labels[offset])],
                "pred": class_names[int(predicted[offset])],
                "confidence": round(float(confidence[offset]), 6),
            })
        cursor += images.size(0)
    return records


def read_confusion_pairs(path: Path, top_pairs: int) -> list[dict]:
    """Off-diagonal confusion counts, strongest first."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        matrix = {row[0]: [int(v) for v in row[1:]] for row in reader}
    pairs = []
    for true_name, values in matrix.items():
        for column, count in enumerate(values):
            predicted = header[column + 1]
            if count > 0 and predicted != true_name:
                pairs.append({"true": true_name, "pred": predicted,
                              "count": count})
    pairs.sort(key=lambda p: p["count"], reverse=True)
    return pairs[:top_pairs]


def build_train_val_hashes(processed_dir: Path) -> tuple[dict, int]:
    """pHash every train/val image (the images the model actually saw)."""
    hashes: dict[str, np.ndarray] = {}
    failures = 0
    for split in ("train", "val"):
        split_dir = processed_dir / split
        for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            for image_path in sorted(class_dir.iterdir()):
                if not image_path.is_file():
                    continue
                digest = image_phash(image_path)
                if digest is None:
                    failures += 1
                    continue
                hashes[str(image_path)] = (digest, class_dir.name)
    return hashes, failures


def near_duplicates(target: np.ndarray, hashes: dict,
                    threshold: int) -> list[dict]:
    """Train/val images within ``threshold`` Hamming distance of ``target``."""
    matches = []
    for path, (digest, class_name) in hashes.items():
        distance = int(np.count_nonzero(target != digest))
        if distance <= threshold:
            matches.append({"path": path, "class": class_name,
                            "distance": distance})
    matches.sort(key=lambda m: m["distance"])
    return matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sample and structure hard examples from the baseline.")
    parser.add_argument("--weights", type=Path, default=BEST_WEIGHTS_PATH)
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--per-pair", type=int, default=20)
    parser.add_argument("--top-pairs", type=int, default=8)
    parser.add_argument("--device", default="auto",
                        choices=["auto", "cpu", "cuda"])
    args = parser.parse_args(argv)

    started = time.time()
    device = resolve_device(args.device)
    print(f"[A5] device={device} weights={args.weights}", flush=True)

    model, class_names = load_checkpoint(args.weights, device=device)
    loaders, dataset_class_names = build_dataloaders(
        processed_dir=args.data_dir, batch_size=32, num_workers=0)
    test_loader = loaders["test"]
    print(f"[A5] test images={len(test_loader.dataset)} "
          f"classes={len(dataset_class_names)}", flush=True)

    print("[A5] running baseline inference on the official test set ...",
          flush=True)
    records = collect_test_predictions(
        model, test_loader, device, dataset_class_names)
    errors = [r for r in records if r["true"] != r["pred"]]
    print(f"[A5] total={len(records)} errors={len(errors)} "
          f"({len(errors) / len(records):.2%})", flush=True)

    pairs = read_confusion_pairs(
        args.reports_dir / "confusion_matrix.csv", args.top_pairs)
    print(f"[A5] analysing top {len(pairs)} confusion pairs", flush=True)

    print("[A5] hashing train/val images for near-duplicate checks ...",
          flush=True)
    train_val_hashes, hash_failures = build_train_val_hashes(args.data_dir)
    print(f"[A5] hashed {len(train_val_hashes)} train/val images "
          f"(failures={hash_failures})", flush=True)

    review_root = _REPO_ROOT / ".cache" / "A5_review"
    if review_root.exists():
        shutil.rmtree(review_root)
    review_root.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    pair_reports = []
    for pair in pairs:
        candidates = [r for r in errors
                      if r["true"] == pair["true"] and r["pred"] == pair["pred"]]
        candidates.sort(key=lambda r: r["path"])
        sampled = (rng.sample(candidates, min(args.per_pair, len(candidates)))
                   if len(candidates) > args.per_pair else list(candidates))

        pair_dir = review_root / f"{pair['true']}_to_{pair['pred']}"
        pair_dir.mkdir(parents=True, exist_ok=True)

        cases = []
        for record in sampled:
            digest = image_phash(Path(record["path"]))
            duplicates = (near_duplicates(digest, train_val_hashes,
                                          PHASH_THRESHOLD)
                          if digest is not None else [])
            same_label = [d for d in duplicates
                          if d["class"] == record["true"]]
            other_label = [d for d in duplicates
                           if d["class"] != record["true"]]
            destination = pair_dir / Path(record["path"]).name
            try:
                shutil.copy2(record["path"], destination)
            except Exception:  # noqa: BLE001 - 复制失败不影响 case 记录
                destination = None
            cases.append({
                **record,
                "near_duplicates_in_train_val": duplicates,
                "near_duplicates_same_label": len(same_label),
                "near_duplicates_other_label": len(other_label),
                "review_copy": str(destination) if destination else None,
            })

        mean_confidence = (
            sum(c["confidence"] for c in candidates) / len(candidates)
            if candidates else None)
        pair_reports.append({
            "true": pair["true"],
            "pred": pair["pred"],
            "total_errors_in_pair": len(candidates),
            "sampled": len(sampled),
            "mean_confidence_of_errors": (
                round(mean_confidence, 4) if mean_confidence is not None
                else None),
            "cases": cases,
        })
        print(f"[A5] {pair['true']} -> {pair['pred']}: "
              f"{len(candidates)} errors, sampled {len(sampled)}", flush=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weights": str(args.weights),
        "phash_threshold": PHASH_THRESHOLD,
        "seed": SEED,
        "test_total": len(records),
        "test_errors": len(errors),
        "pairs_analysed": len(pair_reports),
        "train_val_images_hashed": len(train_val_hashes),
        "review_folder": str(review_root),
        "pairs": pair_reports,
        "runtime_seconds": round(time.time() - started, 2),
    }
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.reports_dir / "A5_hard_examples.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    md_path = args.reports_dir / "A5_hard_examples.md"
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"[A5] wrote {json_path} and {md_path} "
          f"in {report['runtime_seconds']}s", flush=True)
    return 0


def build_markdown(report: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# A5 难例分析：混淆对抽样与人工复核清单")
    add("")
    add(f"- 生成时间：{report['generated_at']}")
    add(f"- 权重：`{report['weights']}`（基线，未重训）")
    add(f"- 测试集：{report['test_total']} 张，误分类 "
        f"{report['test_errors']} 张"
        f"（{report['test_errors'] / report['test_total']:.2%}）")
    add(f"- pHash 近重复阈值：≤ {report['phash_threshold']}；"
        f"抽样种子：{report['seed']}")
    add(f"- 抽样图片已复制到：`{report['review_folder']}\\<真实品种>_to_<误判品种>\\`")
    add("- **本报告不下“标注错误”的最终结论**："
        "是否标签噪声必须人工目检后判定；"
        "此处只提供可复核的证据。")
    add("")
    add("## 混淆对抽样清单")
    add("")
    add("| 真实品种 | 误判为 | 该对错误总数 | 抽样数 | 错误平均置信度 |")
    add("|---|---|---|---|---|")
    for pair in report["pairs"]:
        confidence = pair["mean_confidence_of_errors"]
        add(f"| {pair['true']} | {pair['pred']} | "
            f"{pair['total_errors_in_pair']} | {pair['sampled']} | "
            f"{confidence if confidence is not None else 'N/A'} |")
    add("")
    add("## 逐对明细（抽样样本）")
    add("")
    for pair in report["pairs"]:
        add(f"### {pair['true']} → {pair['pred']}"
            f"（{pair['total_errors_in_pair']} 个错误，"
            f"抽样 {pair['sampled']} 个）")
        add("")
        add("| 样本文件 | 预测置信度 | train/val 中同标签近重复 | "
            "train/val 中异标签近重复 |")
        add("|---|---|---|---|")
        for case in pair["cases"]:
            name = Path(case["path"]).name
            add(f"| `{name}` | {case['confidence']:.4f} | "
                f"{case['near_duplicates_same_label']} | "
                f"{case['near_duplicates_other_label']} |")
        add("")
        flagged = [c for c in pair["cases"]
                   if c["near_duplicates_other_label"] > 0]
        if flagged:
            add(f"> 注意：本对有 {len(flagged)} 个抽样样本在 train/val 中存在"
                f"**异标签**近重复图片——这是标注噪声或数据泄漏的间接证据，"
                f"应优先人工复核这些样本。")
            add("")
    add("## 人工复核方法建议")
    add("")
    add("1. 打开上表中`review_copy`对应的图片（已按混淆对分文件夹复制）；")
    add("2. 判断真实品种标签是否正确：若图片实际属于误判品种，"
        "则为 Oxford 官方标注错误；")
    add("3. 若标签正确但外形确实相近，则记为“真实相似”，"
        "说明需要更强的细粒度特征或补充数据；")
    add("4. 复核结论回填到本表，作为 A4（补充数据）与 V2 数据清洗的输入。")
    add("")
    add("**约束**：发现官方标注问题也只记录 case，"
        "**不修改**官方 test 标注（否则基线不可比）。")
    add("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
