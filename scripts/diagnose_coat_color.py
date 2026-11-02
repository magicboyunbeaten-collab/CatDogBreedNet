#!/usr/bin/env python
"""边牧 / 柯利牧羊犬的毛色分布与分组准确率专项诊断（只读，不训练）。

用法（在仓库根目录执行）::

    python scripts/diagnose_coat_color.py

覆盖 ``collie`` 与 ``border_collie`` 的 **train / val / test 全部图片**（297 张）。

毛色识别原则（**保守、不猜测**）：

* 取图像中心区域（短边 60%）以降低背景干扰，转 HSV 后统计黑 / 白 /
  黄褐(tan) / 灰蓝 / 其他五类像素占比；
* 用带阈值的规则判定，并用"最弱条件超出阈值的相对幅度"作为置信度；
* **仅当置信度达标且与次优规则差距足够时才给出毛色**，否则
  ``coat='uncertain'`` 且 ``needs_manual_review=True``；
* 这是**像素统计启发式，不是经校验的分类器**，报告中一律标注为指示性结论。

本脚本只读数据与 checkpoint，只写 ``reports/v2_1_coat_pitbull_diagnostics/``。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from sklearn.metrics import accuracy_score

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_DATA_DIR = _REPO_ROOT / "data" / "v2_processed"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_coat_pitbull_diagnostics"

CLASSES = ("collie", "border_collie")
SPLITS = ("train", "val", "test")

COAT_LABELS = ("black_white", "tricolor", "sable", "merle", "red_white",
               "other", "uncertain")
COAT_ZH = {
    "black_white": "黑白色",
    "tricolor": "三色",
    "sable": "貂色",
    "merle": "陨石色",
    "red_white": "红白/黄白",
    "other": "其他毛色",
    "uncertain": "待人工复核",
}

#: 毛色判定所需的最小置信度（0.3 表示最弱条件至少超出阈值 15%）。
MIN_CONFIDENCE = 0.30
#: 最佳规则与次优规则的最小置信度差。
MIN_MARGIN = 0.15
#: 中心裁剪比例（相对短边）。
CENTER_FRACTION = 0.60
#: 背景环带宽度比例。
RING_FRACTION = 0.15


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def color_fractions(image: Image.Image) -> dict:
    """中心区域 HSV 像素占比。"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    side = max(8, int(min(width, height) * CENTER_FRACTION))
    left = (width - side) // 2
    top = (height - side) // 2
    crop = rgb.crop((left, top, left + side, top + side)).resize((128, 128))
    array = np.asarray(crop, dtype=np.float32) / 255.0
    import colorsys  # noqa: F401  (kept for clarity; vectorised below)

    max_c = array.max(axis=2)
    min_c = array.min(axis=2)
    delta = max_c - min_c
    value = max_c
    saturation = np.where(max_c > 0, delta / np.maximum(max_c, 1e-6), 0.0)
    red, green, blue = array[..., 0], array[..., 1], array[..., 2]
    hue = np.zeros_like(max_c)
    safe = delta > 1e-6
    idx = safe & (max_c == red)
    hue[idx] = (60 * ((green - blue) / np.maximum(delta, 1e-6)))[idx] % 360
    idx = safe & (max_c == green)
    hue[idx] = (60 * (2 + (blue - red) / np.maximum(delta, 1e-6)))[idx]
    idx = safe & (max_c == blue)
    hue[idx] = (60 * (4 + (red - green) / np.maximum(delta, 1e-6)))[idx]

    total = float(value.size)
    black = float(np.count_nonzero(value < 0.25)) / total
    white = float(np.count_nonzero((value > 0.80) & (saturation < 0.20))) / total
    tan = float(np.count_nonzero((hue >= 10) & (hue <= 45)
                                 & (saturation > 0.30)
                                 & (value >= 0.25))) / total
    grey = float(np.count_nonzero((saturation < 0.20)
                                  & (value >= 0.30) & (value <= 0.70))) / total
    other = max(0.0, 1.0 - black - white - tan - grey)
    return {"black": black, "white": white, "tan": tan, "grey": grey,
            "other": other}


def _slack(value: float, threshold: float) -> float:
    """条件满足时返回相对超出幅度（可为负，表示不满足）。"""
    if threshold <= 0:
        return 1.0
    return (value - threshold) / threshold


def _confidence(slacks: list[float]) -> float:
    """规则置信度：最弱条件的相对超出幅度，归一到 [0,1]。"""
    weakest = min(slacks)
    if weakest < 0:
        return 0.0
    return float(min(1.0, weakest / 0.5))


def evaluate_rules(fractions: dict) -> list[tuple[str, float]]:
    """返回每条规则的 (毛色, 置信度)，按置信度降序。"""
    black = fractions["black"]
    white = fractions["white"]
    tan = fractions["tan"]
    grey = fractions["grey"]
    other = fractions["other"]

    rules: list[tuple[str, float]] = []

    # 三色：黑 + 白 + 黄褐三种同时存在
    if tan >= 0.08:
        rules.append(("tricolor", _confidence([
            _slack(black, 0.15), _slack(white, 0.10), _slack(tan, 0.08)])))
    # 黑白：黑 + 白，且几乎没有黄褐
    if tan < 0.08:
        rules.append(("black_white", _confidence([
            _slack(black, 0.20), _slack(white, 0.15)])))
    # 貂色：黄褐占主导，黑色少
    if black < 0.15:
        rules.append(("sable", _confidence([_slack(tan, 0.35)])))
    # 陨石色：大面积灰蓝 + 黑色
    if tan < 0.10:
        rules.append(("merle", _confidence([
            _slack(grey, 0.25), _slack(black, 0.08)])))
    # 红白/黄白：黄褐 + 白，黑色少
    if black < 0.10:
        rules.append(("red_white", _confidence([
            _slack(tan, 0.15), _slack(white, 0.12)])))
    # 其他：某一类占比极高
    dominant = max(black, white, tan, grey, other)
    rules.append(("other", _confidence([_slack(dominant, 0.55)])))

    return sorted([(name, score) for name, score in rules if score > 0],
                  key=lambda kv: -kv[1])


def classify_coat(path: Path) -> dict:
    """返回毛色判定与置信度；不可靠时 coat='uncertain'。"""
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB").copy()
    except Exception as exc:  # noqa: BLE001
        return {"coat": "uncertain", "confidence": 0.0, "margin": 0.0,
                "needs_manual_review": True,
                "fractions": {}, "reason": f"decode_error: {exc}"}

    fractions = color_fractions(rgb)
    ranked = evaluate_rules(fractions)
    if not ranked:
        return {"coat": "uncertain", "confidence": 0.0, "margin": 0.0,
                "needs_manual_review": True, "fractions": fractions,
                "reason": "no_rule_matched"}

    best_name, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_score

    if best_score < MIN_CONFIDENCE or margin < MIN_MARGIN:
        return {"coat": "uncertain", "confidence": round(best_score, 4),
                "margin": round(margin, 4), "needs_manual_review": True,
                "fractions": fractions,
                "reason": (f"low_confidence({best_score:.2f})"
                           if best_score < MIN_CONFIDENCE
                           else f"ambiguous(margin={margin:.2f})")}

    return {"coat": best_name, "confidence": round(best_score, 4),
            "margin": round(margin, 4), "needs_manual_review": False,
            "fractions": fractions, "reason": "ok"}


def image_stats(path: Path) -> dict:
    """尺寸 / 亮度 / 饱和度 / 背景环带 / 字节数。"""
    stats = {"width": 0, "height": 0, "aspect_ratio": 0.0,
             "v_mean": 0.0, "s_mean": 0.0, "bg_v_mean": 0.0,
             "bg_s_mean": 0.0, "bg_h_mean": 0.0, "bytes": 0}
    try:
        stats["bytes"] = path.stat().st_size
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            stats["width"] = width
            stats["height"] = height
            stats["aspect_ratio"] = round(width / height, 4) if height else 0.0
            small = np.asarray(rgb.resize((128, 128)), dtype=np.float32) / 255.0
            stats["v_mean"] = round(float(small.max(axis=2).mean()), 4)
            max_c = small.max(axis=2)
            min_c = small.min(axis=2)
            with np.errstate(divide="ignore", invalid="ignore"):
                saturation = np.where(max_c > 0, (max_c - min_c)
                                      / np.maximum(max_c, 1e-6), 0.0)
            stats["s_mean"] = round(float(saturation.mean()), 4)
            # 背景代理：外圈 15% 宽度环带
            band = max(4, int(min(width, height) * RING_FRACTION))
            ring_pixels = []
            array = np.asarray(rgb.resize((160, 160)), dtype=np.float32) / 255.0
            edge = max(2, int(160 * RING_FRACTION))
            mask = np.ones(array.shape[:2], dtype=bool)
            mask[edge:-edge, edge:-edge] = False
            ring_pixels = array[mask]
            if ring_pixels.size:
                ring_v = ring_pixels.max(axis=1)
                ring_max = ring_pixels.max(axis=1)
                ring_min = ring_pixels.min(axis=1)
                ring_s = np.where(ring_max > 0,
                                  (ring_max - ring_min)
                                  / np.maximum(ring_max, 1e-6), 0.0)
                stats["bg_v_mean"] = round(float(ring_v.mean()), 4)
                stats["bg_s_mean"] = round(float(ring_s.mean()), 4)
                stats["bg_h_mean"] = round(
                    float(np.nan_to_num(np.arctan2(
                        ring_pixels[:, 0] - ring_pixels[:, 1],
                        ring_pixels[:, 2] - ring_pixels[:, 1])).mean()), 4)
            del band
    except Exception:  # noqa: BLE001
        pass
    return stats


def source_evidence(label: str, filename: str) -> str:
    import re
    match = re.match(r"^(n\d{8})_", Path(filename).stem)
    if match:
        return f"Stanford Dogs (ImageNet wnid {match.group(1)})"
    if Path(filename).stem.startswith(label):
        return "Oxford-IIIT Pet"
    return "unknown"


def predict_paths(model, paths: list[Path], class_names: list[str],
                  device, batch_size: int = 32) -> list[dict]:
    """对给定图片路径列表推理一次，返回逐图 top-5。"""
    transform = build_transforms(train=False)
    results: list[dict] = []
    buffer: list[torch.Tensor] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(paths), batch_size):
            chunk = paths[start:start + batch_size]
            tensors = []
            for path in chunk:
                with Image.open(path) as image:
                    tensors.append(transform(image.convert("RGB")))
            batch = torch.stack(tensors).to(device)
            logits = model(batch)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            for offset, probability in enumerate(probs):
                order = np.argsort(-probability)[:5]
                results.append({
                    "pred_label": class_names[int(order[0])],
                    "top1_prob": float(probability[order[0]]),
                    "top2_label": class_names[int(order[1])],
                    "top2_prob": float(probability[order[1]]),
                    "top5": "|".join(
                        f"{class_names[int(i)]}:{float(probability[int(i)]):.6f}"
                        for i in order),
                })
            buffer.clear()
    if len(results) != len(paths):
        raise ValueError(f"inference mismatch: {len(results)} vs {len(paths)}")
    return results


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def make_sheet(items: list[dict], destination: Path, columns: int = 6,
               cell: int = 170, title: str = "") -> bool:
    if not items:
        return False
    rows_count = (len(items) + columns - 1) // columns
    header = 30 if title else 0
    sheet = Image.new("RGB", (columns * cell, header + rows_count * (cell + 26)),
                      (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None
    if title:
        draw.text((6, 8), title, fill=(0, 0, 0), font=font)
    for index, item in enumerate(items):
        row, col = divmod(index, columns)
        x, y = col * cell, header + row * (cell + 26)
        try:
            with Image.open(item["image_path"]) as image:
                thumb = image.convert("RGB").copy()
            thumb.thumbnail((cell - 6, cell - 6))
            sheet.paste(thumb, (x + 3, y + 3))
        except Exception:  # noqa: BLE001
            draw.rectangle([x + 3, y + 3, x + cell - 3, y + cell - 3],
                           outline=(200, 0, 0))
        draw.text((x + 3, y + cell + 2), (item.get("caption") or "")[:30],
                  fill=(0, 0, 0), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=85)
    return True


def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": 0.0, "q1": 0.0, "q3": 0.0, "iqr": 0.0}
    array = np.asarray(values, dtype=float)
    q1, median, q3 = np.percentile(array, [25, 50, 75])
    return {"n": len(values), "median": round(float(median), 4),
            "q1": round(float(q1), 4), "q3": round(float(q3), 4),
            "iqr": round(float(q3 - q1), 4)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    if out_dir.exists() and any(out_dir.glob("coat_*.csv")):
        out_dir = out_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[coat] 已有 coat_*.csv，改写到 {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    model, class_names = load_checkpoint(
        args.model_dir / "best_model.pth", device=device)
    saved = json.loads((args.model_dir / "class_names.json").read_text(
        encoding="utf-8"))
    if list(saved) != list(class_names):
        raise ValueError("class_names.json 与 checkpoint 顺序不一致")
    print(f"[coat] device={device} classes={len(class_names)}")

    # ---- 枚举 297 张 ----
    entries = []
    for label in CLASSES:
        for split in SPLITS:
            directory = args.data_dir / split / label
            paths = sorted(directory.glob("*.jpg")) if directory.is_dir() else []
            print(f"  {label:<16} {split:<5} {len(paths):>3}")
            entries.extend({"label": label, "split": split, "path": path}
                           for path in paths)
    print(f"[coat] 合计 {len(entries)} 张")

    # ---- 推理 ----
    predictions = predict_paths(model, [e["path"] for e in entries],
                                class_names, device)
    rows = []
    for entry, prediction in zip(entries, predictions):
        coat = classify_coat(entry["path"])
        stats = image_stats(entry["path"])
        fractions = coat["fractions"] or {}
        rows.append({
            "sample_id": f"{entry['label']}/{entry['path'].name}",
            "split": entry["split"],
            "true_label": entry["label"],
            "pred_label": prediction["pred_label"],
            "correct": int(prediction["pred_label"] == entry["label"]),
            "top1_prob": round(prediction["top1_prob"], 6),
            "top2_label": prediction["top2_label"],
            "top2_prob": round(prediction["top2_prob"], 6),
            "top5": prediction["top5"],
            "coat": coat["coat"],
            "coat_confidence": coat["confidence"],
            "coat_margin": coat["margin"],
            "coat_needs_review": int(coat["needs_manual_review"]),
            "coat_reason": coat["reason"],
            "f_black": round(fractions.get("black", 0.0), 4),
            "f_white": round(fractions.get("white", 0.0), 4),
            "f_tan": round(fractions.get("tan", 0.0), 4),
            "f_grey": round(fractions.get("grey", 0.0), 4),
            "f_other": round(fractions.get("other", 0.0), 4),
            "width": stats["width"], "height": stats["height"],
            "aspect_ratio": stats["aspect_ratio"],
            "v_mean": stats["v_mean"], "s_mean": stats["s_mean"],
            "bg_v_mean": stats["bg_v_mean"], "bg_s_mean": stats["bg_s_mean"],
            "bg_h_mean": stats["bg_h_mean"], "bytes": stats["bytes"],
            "image_path": str(entry["path"]),
            "file_name": entry["path"].name,
            "source_evidence": source_evidence(entry["label"],
                                               entry["path"].name),
        })

    write_csv(out_dir / "coat_predictions_all_splits.csv", rows, list(rows[0]))

    # ---- 与既有 test 预测交叉核对 ----
    legacy = _REPO_ROOT / "reports" / "v2_1_diagnostics" / "all_predictions_136.csv"
    cross_check = {"checked": 0, "mismatches": [], "legacy_present": legacy.exists()}
    if legacy.exists():
        legacy_map = {}
        with legacy.open(encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                legacy_map[item["sample_id"]] = item["pred_label"]
        for row in rows:
            if row["split"] != "test":
                continue
            prior = legacy_map.get(row["sample_id"])
            if prior is None:
                continue
            cross_check["checked"] += 1
            if prior != row["pred_label"]:
                cross_check["mismatches"].append(
                    {"sample_id": row["sample_id"], "legacy": prior,
                     "now": row["pred_label"]})
        print(f"[coat] test 交叉核对 {cross_check['checked']} 行，"
              f"不一致 {len(cross_check['mismatches'])}")
        if cross_check["mismatches"]:
            print("[coat] ** 与既有 test 预测不一致，停止 **", file=sys.stderr)
            return 1

    # ---- 毛色分布 ----
    distribution = []
    for label in CLASSES:
        for split in SPLITS + ("all",):
            subset = [r for r in rows if r["true_label"] == label
                      and (split == "all" or r["split"] == split)]
            if not subset:
                continue
            counter = Counter(r["coat"] for r in subset)
            for coat in COAT_LABELS:
                count = counter.get(coat, 0)
                distribution.append({
                    "class": label, "split": split, "coat": coat,
                    "coat_zh": COAT_ZH[coat], "count": count,
                    "denominator": len(subset),
                    "ratio": round(count / len(subset), 4),
                })
    write_csv(out_dir / "coat_color_distribution.csv", distribution,
              ["class", "split", "coat", "coat_zh", "count", "denominator",
               "ratio"])

    # ---- 按毛色分组的准确率 ----
    accuracy_rows = []
    for label in CLASSES:
        other = "border_collie" if label == "collie" else "collie"
        for coat in COAT_LABELS:
            subset = [r for r in rows if r["true_label"] == label
                      and r["coat"] == coat]
            if not subset:
                accuracy_rows.append({
                    "class": label, "coat": coat, "coat_zh": COAT_ZH[coat],
                    "n": 0, "correct": 0, "accuracy": 0.0,
                    "to_other_class": 0, "other_class_rate": 0.0,
                    "top_wrong_target": "", "note": "无样本（分母 0）"})
                continue
            correct = sum(r["correct"] for r in subset)
            to_other = sum(1 for r in subset if r["pred_label"] == other)
            wrong_targets = Counter(r["pred_label"] for r in subset
                                    if r["pred_label"] != label)
            accuracy_rows.append({
                "class": label, "coat": coat, "coat_zh": COAT_ZH[coat],
                "n": len(subset), "correct": correct,
                "accuracy": round(correct / len(subset), 4),
                "to_other_class": to_other,
                "other_class_rate": round(to_other / len(subset), 4),
                "top_wrong_target": (wrong_targets.most_common(1)[0][0]
                                     if wrong_targets else ""),
                "note": "",
            })
    write_csv(out_dir / "coat_color_accuracy.csv", accuracy_rows,
              ["class", "coat", "coat_zh", "n", "correct", "accuracy",
               "to_other_class", "other_class_rate", "top_wrong_target", "note"])

    # ---- 8 张 collie -> border_collie 专项 ----
    cases = [r for r in rows
             if r["true_label"] == "collie"
             and r["pred_label"] == "border_collie"]
    collie_all = [r for r in rows if r["true_label"] == "collie"]
    collie_bw = [r for r in collie_all if r["coat"] == "black_white"]
    collie_bw_correct = sum(r["correct"] for r in collie_bw)
    case_rows = []
    for item in sorted(cases, key=lambda r: -r["top1_prob"]):
        case_rows.append({
            "sample_id": item["sample_id"],
            "split": item["split"],
            "true_label": item["true_label"],
            "pred_label": item["pred_label"],
            "top1_prob": item["top1_prob"],
            "top2_label": item["top2_label"],
            "top2_prob": item["top2_prob"],
            "coat": item["coat"], "coat_zh": COAT_ZH[item["coat"]],
            "coat_confidence": item["coat_confidence"],
            "coat_needs_review": item["coat_needs_review"],
            "f_black": item["f_black"], "f_white": item["f_white"],
            "f_tan": item["f_tan"], "f_grey": item["f_grey"],
            "aspect_ratio": item["aspect_ratio"],
            "bg_v_mean": item["bg_v_mean"], "bg_s_mean": item["bg_s_mean"],
            "image_path": item["image_path"],
            "denominator_note": (
                f"本类共 {len(collie_all)} 张；其中自动判定为黑白 "
                f"{len(collie_bw)} 张，黑白样本正确 {collie_bw_correct} 张"
                f"（{collie_bw_correct}/{len(collie_bw)}）"),
        })
    write_csv(out_dir / "collie_to_border_collie_cases.csv", case_rows,
              list(case_rows[0]) if case_rows else
              ["sample_id", "split", "true_label", "pred_label"])

    # ---- 混杂因素 ----
    features = ["width", "height", "aspect_ratio", "v_mean", "s_mean",
                "bg_v_mean", "bg_s_mean", "bytes"]
    confounder_rows = []
    per_class_feature: dict[tuple[str, str], dict] = {}
    for label in CLASSES:
        for feature in features:
            values = [float(r[feature]) for r in rows
                      if r["true_label"] == label and r[feature]]
            summary = describe(values)
            per_class_feature[(label, feature)] = summary
            confounder_rows.append({"class": label, "feature": feature, **summary})
    # 两类间效应量：|中位数差| / 合并 IQR
    for feature in features:
        left = per_class_feature[("collie", feature)]
        right = per_class_feature[("border_collie", feature)]
        pooled = max(1e-6, (left["iqr"] + right["iqr"]) / 2)
        effect = abs(left["median"] - right["median"]) / pooled
        confounder_rows.append({
            "class": "effect_size_collie_vs_border",
            "feature": feature, "n": left["n"] + right["n"],
            "median": round(effect, 4), "q1": "", "q3": "", "iqr": "",
        })
    write_csv(out_dir / "coat_confounders.csv", confounder_rows,
              ["class", "feature", "n", "median", "q1", "q3", "iqr"])

    # ---- 复核队列 ----
    review_rows = []
    for row in rows:
        reasons = []
        priority = ""
        if row["coat_needs_review"]:
            reasons.append(f"毛色待复核({row['coat_reason']})")
            priority = priority or "3"
        if row["true_label"] == "collie" and row["pred_label"] == "border_collie":
            reasons.append("collie->border_collie 高置信互误")
            priority = "1"
        elif row["true_label"] == "border_collie" and row["pred_label"] == "collie":
            reasons.append("border_collie->collie 互误")
            priority = "1"
        elif not row["correct"]:
            reasons.append(f"模型误判为 {row['pred_label']}")
            priority = priority or "2"
        if not reasons:
            continue
        review_rows.append({
            "priority": priority,
            "reasons": "; ".join(reasons),
            "sample_id": row["sample_id"],
            "split": row["split"],
            "true_label": row["true_label"],
            "pred_label": row["pred_label"],
            "top1_prob": row["top1_prob"],
            "top2_label": row["top2_label"],
            "top2_prob": row["top2_prob"],
            "top5": row["top5"],
            "coat": row["coat"],
            "coat_zh": COAT_ZH[row["coat"]],
            "coat_confidence": row["coat_confidence"],
            "f_black": row["f_black"], "f_white": row["f_white"],
            "f_tan": row["f_tan"], "f_grey": row["f_grey"],
            "image_path": row["image_path"],
            "source_evidence": row["source_evidence"],
            "review_status": "",
            "review_notes": "",
        })
    review_rows.sort(key=lambda r: (r["priority"], -float(r["top1_prob"])))
    write_csv(out_dir / "coat_color_review_queue.csv", review_rows,
              ["priority", "reasons", "sample_id", "split", "true_label",
               "pred_label", "top1_prob", "top2_label", "top2_prob", "top5",
               "coat", "coat_zh", "coat_confidence", "f_black", "f_white",
               "f_tan", "f_grey", "image_path", "source_evidence",
               "review_status", "review_notes"])

    # ---- 联系表 ----
    sheets = []
    for label in CLASSES:
        for coat in COAT_LABELS:
            subset = [r for r in rows if r["true_label"] == label
                      and r["coat"] == coat]
            if not subset:
                continue
            subset.sort(key=lambda r: (r["correct"], -float(r["top1_prob"])))
            items = [{
                "image_path": r["image_path"],
                "caption": f"{'OK' if r['correct'] else 'ERR:' + r['pred_label'][:12]}",
            } for r in subset[:24]]
            path = out_dir / f"contact_sheet_{label}_{coat}.png"
            if make_sheet(items, path,
                          title=f"{label} / {COAT_ZH[coat]} "
                                f"(n={len(subset)}, 最多显示 24 张)"):
                sheets.append(path.name)
    if cases:
        items = [{
            "image_path": r["image_path"],
            "caption": f"{r['top1_prob']:.2f} {COAT_ZH[r['coat']]}",
        } for r in sorted(cases, key=lambda r: -r["top1_prob"])]
        path = out_dir / "contact_sheet_collie_to_border_8cases.png"
        if make_sheet(items, path, columns=4,
                      title="collie -> border_collie 的 8 张（数字为 top-1 概率）"):
            sheets.append(path.name)

    # ---- 汇总 JSON ----
    test_rows = [r for r in rows if r["split"] == "test"]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": sha256_file(args.model_dir / "best_model.pth"),
        "counts": {label: {split: len([r for r in rows
                                       if r["true_label"] == label
                                       and r["split"] == split])
                           for split in SPLITS} for label in CLASSES},
        "classification_coverage": {
            "total": len(rows),
            "classified": sum(1 for r in rows if not r["coat_needs_review"]),
            "uncertain": sum(1 for r in rows if r["coat_needs_review"]),
            "uncertain_ratio": round(
                sum(1 for r in rows if r["coat_needs_review"]) / len(rows), 4),
        },
        "test_accuracy": {
            label: {
                "n": len([r for r in test_rows if r["true_label"] == label]),
                "correct": sum(1 for r in test_rows
                               if r["true_label"] == label and r["correct"]),
            } for label in CLASSES},
        "collie_to_border_collie": {
            "cases": len(cases),
            "collie_total": len(collie_all),
            "collie_black_white_total": len(collie_bw),
            "collie_black_white_correct": collie_bw_correct,
            "cases_coat_distribution": dict(Counter(r["coat"] for r in cases)),
        },
        "cross_check_with_legacy_test": cross_check,
        "contact_sheets": sheets,
    }
    (out_dir / "coat_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"[coat] 毛色分类覆盖: 已分类 "
          f"{summary['classification_coverage']['classified']}/"
          f"{len(rows)}，待复核 "
          f"{summary['classification_coverage']['uncertain']} "
          f"({summary['classification_coverage']['uncertain_ratio']:.1%})")
    print(f"[coat] collie test: "
          f"{summary['test_accuracy']['collie']['correct']}/"
          f"{summary['test_accuracy']['collie']['n']}；border_collie test: "
          f"{summary['test_accuracy']['border_collie']['correct']}/"
          f"{summary['test_accuracy']['border_collie']['n']}")
    print(f"[coat] collie->border_collie: {len(cases)} 张；"
          f"collie 全体 {len(collie_all)} 张，其中黑白 {len(collie_bw)} 张，"
          f"黑白正确 {collie_bw_correct}")
    print(f"[coat] 复核队列 {len(review_rows)} 条；联系表 {len(sheets)} 张")
    print(f"[coat] wrote -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
