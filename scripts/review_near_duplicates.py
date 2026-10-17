#!/usr/bin/env python
"""阶段一：近重复图片人工审查（MODEL_UPGRADE_PLAN 的泄漏风险检查）。

用法（在仓库根目录执行）::

    python scripts/review_near_duplicates.py
    python scripts/review_near_duplicates.py --threshold 5

输入：``reports/diagnostics_details.json`` 中 ``near_duplicates.pairs``
（由 U1 诊断 `scripts/diagnose_dataset.py` 产生，pHash 阈值 5）。

输出（全部写入 ``reports/leakage_review/`` 与 ``reports/``）：

- ``reports/leakage_review/contact_sheet_<n>_<true>_vs_<pred>.png``
  每对图片的并排联系表（含路径、集合、品种、距离、像素相关度标注）；
- ``reports/leakage_review_contact_sheet.md`` —— 人读审查表；
- ``reports/leakage_review_contact_sheet.json`` —— 机器可读明细；
- ``reports/leakage_review_contact_sheet.csv`` —— 便于表格工具筛选。

**本脚本只提供证据，不下"泄漏已被证实"的结论。**
它对每对给出初步分级（基于 pHash 距离与像素相关度），但最终判定
必须由人工目检完成——pHash 距离小既可能来自同一照片的不同压缩/裁切，
也可能来自构图相似的**不同**照片（误报）。

本脚本**只读**图片：不修改、不移动、不删除任何数据文件。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.config import REPORTS_DIR  # noqa: E402

DEFAULT_THRESHOLD = 5
DETAILS_JSON = REPORTS_DIR / "diagnostics_details.json"
OUT_DIR = REPORTS_DIR / "leakage_review"

# 像素相关度判定阈值（0-255 灰度、缩放到 64x64 后比较）
PIXEL_HIGH_CORR = 0.90   # >= 视为"像素层面高度相似"
PIXEL_LOW_MAE = 12.0     # <= 视为"平均像素差很小"


def image_phash(path: Path, hash_size: int = 8,
                highfreq_factor: int = 4) -> np.ndarray | None:
    """Classic pHash bit array; ``None`` when scipy or the image is unavailable."""
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


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def image_stats(path: Path) -> dict:
    """MD5、尺寸、灰度 64x64 数组与均值颜色（用于人工审查的辅助证据）。"""
    import hashlib

    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        size = rgb.size
        small = np.asarray(rgb.resize((64, 64), Image.LANCZOS), dtype=float)
        grey = np.asarray(rgb.convert("L").resize((64, 64), Image.LANCZOS),
                          dtype=float)
        mean_rgb = [round(float(v), 2) for v in
                    np.asarray(rgb, dtype=float).reshape(-1, 3).mean(axis=0)]
    return {
        "md5": digest.hexdigest(),
        "width": int(size[0]),
        "height": int(size[1]),
        "mean_rgb": mean_rgb,
        "grey64": grey,
        "rgb64": small,
    }


def pixel_evidence(a: dict, b: dict) -> dict:
    """两张图的像素层面相似度证据（独立于 pHash）。"""
    ga, gb = a["grey64"].ravel(), b["grey64"].ravel()
    mae = float(np.abs(ga - gb).mean())
    if ga.std() == 0 or gb.std() == 0:
        corr = None
    else:
        corr = float(np.corrcoef(ga, gb)[0, 1])
    colour_mae = float(np.abs(
        a["rgb64"].reshape(-1, 3) - b["rgb64"].reshape(-1, 3)).mean())
    return {
        "grey_mae": round(mae, 3),
        "grey_corr": None if corr is None else round(corr, 5),
        "rgb_mae": round(colour_mae, 3),
    }


def preliminary_grade(distance: int, pixel: dict) -> tuple[str, str]:
    """返回 (初步分级, 依据)。这只是给人工审查的起点，不是结论。"""
    corr = pixel["grey_corr"]
    if distance == 0:
        return ("极可能为同一照片的变体（pHash 完全相同）",
                "pHash 距离为 0，两张图的感知哈希逐位相同")
    if corr is not None and corr >= PIXEL_HIGH_CORR and \
            pixel["grey_mae"] <= PIXEL_LOW_MAE:
        return (f"很可能为同一照片的变体（pHash 距离 {distance}）",
                f"像素相关度 {corr:.3f} ≥ {PIXEL_HIGH_CORR} 且平均灰度差 "
                f"{pixel['grey_mae']:.2f} ≤ {PIXEL_LOW_MAE}")
    if corr is not None and corr < 0.80:
        return (f"疑似 pHash 误报（pHash 距离 {distance}，像素差异大）",
                f"像素相关度仅 {corr:.3f}，更可能是构图相似的不同照片，"
                f"需人工确认")
    return (f"需人工确认（pHash 距离 {distance}）",
            f"像素相关度 {corr if corr is not None else 'N/A'}，"
            f"证据不充分，必须人工目检")


VERDICT_LABELS = {
    "same_photo_variant": "同一照片变体（构成泄漏）",
    "phash_false_positive": "pHash 误报（不构成泄漏）",
    "uncertain": "待人工复核",
}


def load_verdicts(path: Path | None) -> dict:
    """Load optional manual/visual verdicts keyed by pair index."""
    if path is None:
        return {}
    if not path.exists():
        print(f"[review] 警告：--verdicts 文件不存在：{path}", flush=True)
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): v for k, v in data.get("verdicts", {}).items()}


def make_contact_sheet(pair_index: int, pair: dict, out_dir: Path) -> Path | None:
    """把一对图片并排拼成一张联系表 PNG，带文字标注。"""
    paths = [Path(pair["a"]["path"]), Path(pair["b"]["path"])]
    if not all(p.exists() for p in paths):
        return None
    thumb_height = 260
    panels = []
    for path, side in zip(paths, ("a", "b")):
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            scale = thumb_height / rgb.height
            thumb = rgb.resize((max(1, int(rgb.width * scale)), thumb_height),
                               Image.LANCZOS)
        canvas = Image.new("RGB", (thumb.width, thumb.height + 96), "white")
        canvas.paste(thumb, (0, 0))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("arial.ttf", 13)
        except Exception:
            font = ImageFont.load_default()
        label = (
            f"[{side.upper()}] split={pair[side]['split']}\n"
            f"class={pair[side]['class']}\n"
            f"{path.name}"
        )
        draw.multiline_text((6, thumb.height + 6), label, fill="black",
                            font=font, spacing=3)
        panels.append(canvas)

    width = sum(p.width for p in panels) + 24
    height = max(p.height for p in panels) + 74
    sheet = Image.new("RGB", (width, height), "#f2f2f2")
    draw = ImageDraw.Draw(sheet)
    try:
        title_font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        title_font = ImageFont.load_default()
    title = (f"Pair #{pair_index}  pHash distance={pair['distance']}  "
             f"cross_split={pair['cross_split']}")
    draw.text((10, 8), title, fill="black", font=title_font)
    x = 10
    for panel in panels:
        sheet.paste(panel, (x, 60))
        x += panel.width + 12
    name = (f"contact_sheet_{pair_index:02d}_"
            f"{pair['a']['class']}_vs_{pair['b']['class']}.png")
    destination = out_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return destination


def load_pairs(details_path: Path, threshold: int) -> list[dict]:
    if not details_path.exists():
        raise FileNotFoundError(
            f"missing {details_path}; run scripts/diagnose_dataset.py first")
    details = json.loads(details_path.read_text(encoding="utf-8"))
    near = details.get("near_duplicates", {})
    if not near.get("available"):
        raise RuntimeError(
            "diagnostics_details.json 中 near_duplicates.available=False"
            "（scipy 不可用），无法审查")
    if near.get("threshold") != threshold:
        print(f"[review] 警告：记录阈值 {near.get('threshold')} 与 "
              f"--threshold {threshold} 不一致，仍按记录数据审查", flush=True)
    return list(near.get("pairs", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review near-duplicate image pairs for leakage risk.")
    parser.add_argument("--details", type=Path, default=DETAILS_JSON)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--no-images", action="store_true",
                        help="skip generating contact-sheet PNGs")
    parser.add_argument("--verdicts", type=Path, default=None,
                        help="可选：人工/目视核验结果 JSON（index -> "
                             "{verdict, note}），会把判定渲染进报告")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    verdicts = load_verdicts(args.verdicts)
    if verdicts:
        print(f"[review] 已载入 {len(verdicts)} 条核验判定", flush=True)
    pairs = load_pairs(args.details, args.threshold)
    cross = [p for p in pairs if p.get("cross_split")]
    within = [p for p in pairs if not p.get("cross_split")]
    print(f"[review] 共 {len(pairs)} 对近重复（阈值 "
          f"{args.threshold}）：跨划分 {len(cross)} 对，"
          f"划分内部 {len(within)} 对", flush=True)

    records = []
    for index, pair in enumerate(pairs, 1):
        stats = {}
        ok = True
        for side in ("a", "b"):
            path = Path(pair[side]["path"])
            if not path.exists():
                print(f"[review] 缺少文件：{path}", flush=True)
                ok = False
                break
            stats[side] = image_stats(path)
        if not ok:
            continue

        # 独立复算 pHash 距离，校验 U1 记录值
        recomputed = None
        hash_a = image_phash(Path(pair["a"]["path"]))
        hash_b = image_phash(Path(pair["b"]["path"]))
        if hash_a is not None and hash_b is not None:
            recomputed = hamming_distance(hash_a, hash_b)
        distance_match = (recomputed is None
                          or recomputed == pair["distance"])

        pixel = pixel_evidence(stats["a"], stats["b"])
        grade, basis = preliminary_grade(pair["distance"], pixel)
        identical_md5 = stats["a"]["md5"] == stats["b"]["md5"]

        sheet = None
        if not args.no_images:
            sheet = make_contact_sheet(index, pair, args.out_dir)

        record = {
            "index": index,
            "cross_split": bool(pair["cross_split"]),
            "phash_distance_recorded": pair["distance"],
            "phash_distance_recomputed": recomputed,
            "distance_match": distance_match,
            "identical_md5": identical_md5,
            "preliminary_grade": grade,
            "basis": basis,
            "visual_verdict": (
                VERDICT_LABELS.get(verdicts.get(str(index), {}).get("verdict"),
                                   "未核验")
                if str(index) in verdicts else "未核验"),
            "visual_verdict_note": verdicts.get(str(index), {}).get("note", ""),
            "pixel_evidence": pixel,
            "contact_sheet": str(sheet) if sheet else None,
            "a": {
                "path": pair["a"]["path"], "split": pair["a"]["split"],
                "class": pair["a"]["class"], "md5": stats["a"]["md5"],
                "width": stats["a"]["width"], "height": stats["a"]["height"],
                "mean_rgb": stats["a"]["mean_rgb"],
            },
            "b": {
                "path": pair["b"]["path"], "split": pair["b"]["split"],
                "class": pair["b"]["class"], "md5": stats["b"]["md5"],
                "width": stats["b"]["width"], "height": stats["b"]["height"],
                "mean_rgb": stats["b"]["mean_rgb"],
            },
        }
        records.append(record)
        print(f"[review] #{index} d={pair['distance']} "
              f"{pair['a']['split']}/{pair['a']['class']} vs "
              f"{pair['b']['split']}/{pair['b']['class']} "
              f"corr={pixel['grey_corr']} -> {grade}", flush=True)

    # ---- 汇总 ----
    def _count(grade_prefix: str) -> int:
        return sum(1 for r in records
                   if r["preliminary_grade"].startswith(grade_prefix))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": args.threshold,
        "total_pairs": len(records),
        "cross_split_pairs": sum(1 for r in records if r["cross_split"]),
        "within_split_pairs": sum(1 for r in records if not r["cross_split"]),
        "identical_md5_pairs": sum(1 for r in records if r["identical_md5"]),
        "distance_mismatches": sum(1 for r in records
                                   if not r["distance_match"]),
        "grade_counts": {
            "极可能同一照片变体": _count("极可能"),
            "很可能同一照片变体": _count("很可能"),
            "疑似 pHash 误报": _count("疑似"),
            "需人工确认": _count("需人工"),
        },
        "visual_verification": {
            "verdicts_provided": bool(verdicts),
            "verified_pairs": sum(1 for r in records
                                  if r["visual_verdict"] != "未核验"),
            "cross_split_confirmed_same_photo": sum(
                1 for r in records if r["cross_split"] and r[
                    "visual_verdict"] == VERDICT_LABELS["same_photo_variant"]),
            "cross_split_false_positive": sum(
                1 for r in records if r["cross_split"] and r[
                    "visual_verdict"] == VERDICT_LABELS["phash_false_positive"]),
            "cross_split_unverified": sum(
                1 for r in records if r["cross_split"]
                and r["visual_verdict"] == "未核验"),
        },
        "note": ("初步分级仅基于 pHash 距离与像素相关度；"
                 "目视核验结论以 visual_verdict 字段为准。"
                 "两者都不替代用户本人的最终复核。"),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "leakage_review_contact_sheet.json").write_text(
        json.dumps({"summary": summary, "pairs": records}, indent=2,
                   ensure_ascii=False), encoding="utf-8")

    with (REPORTS_DIR / "leakage_review_contact_sheet.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["index", "cross_split", "phash_distance",
                         "recomputed", "identical_md5", "grey_corr",
                         "grey_mae", "grade", "visual_verdict",
                         "verdict_note", "a_split", "a_class", "a_path",
                         "b_split", "b_class", "b_path", "contact_sheet"])
        for r in records:
            writer.writerow([
                r["index"], r["cross_split"], r["phash_distance_recorded"],
                r["phash_distance_recomputed"], r["identical_md5"],
                r["pixel_evidence"]["grey_corr"],
                r["pixel_evidence"]["grey_mae"], r["preliminary_grade"],
                r["visual_verdict"], r["visual_verdict_note"],
                r["a"]["split"], r["a"]["class"], r["a"]["path"],
                r["b"]["split"], r["b"]["class"], r["b"]["path"],
                r["contact_sheet"],
            ])

    (REPORTS_DIR / "leakage_review_contact_sheet.md").write_text(
        build_markdown(summary, records), encoding="utf-8")
    print(f"[review] wrote reports/leakage_review_contact_sheet."
          f"{{md,json,csv}} 和 {len(records)} 张联系表到 {args.out_dir}",
          flush=True)
    print(f"[review] done in "
          f"{(datetime.now(timezone.utc) - started).total_seconds():.1f}s",
          flush=True)
    return 0


def build_markdown(summary: dict, records: list[dict]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# 近重复图片人工审查联系表（泄漏风险检查）")
    add("")
    add(f"- 生成时间：{summary['generated_at']}")
    add(f"- pHash 阈值：≤ {summary['threshold']}（与 U1 诊断同口径）")
    add(f"- 近重复对总数：**{summary['total_pairs']}**"
        f"（跨 train/val/test **{summary['cross_split_pairs']}** 对，"
        f"划分内部 {summary['within_split_pairs']} 对）")
    add(f"- MD5 完全相同的对数：{summary['identical_md5_pairs']}")
    add(f"- pHash 距离复算与记录不一致的对数：{summary['distance_mismatches']}")
    add("")
    add("## 初步分级统计")
    add("")
    add("| 分级 | 对数 |")
    add("|---|---|")
    for grade, count in summary["grade_counts"].items():
        add(f"| {grade} | {count} |")
    add("")
    add("> **重要**：以上分级仅由 pHash 距离与像素相关度自动得出。"
        "pHash 距离小既可能来自同一照片的不同压缩/裁切，"
        "也可能来自构图相似的**不同**照片（误报）。")
    add("")

    verification = summary.get("visual_verification", {})
    if verification.get("verdicts_provided"):
        add("## 目视核验结果")
        add("")
        add(f"- 已核验对数：**{verification['verified_pairs']}** / "
            f"{summary['total_pairs']}")
        add(f"- 跨划分对中，目视确认**为同一照片变体（构成泄漏）**："
            f"**{verification['cross_split_confirmed_same_photo']}** / "
            f"{summary['cross_split_pairs']}")
        add(f"- 跨划分对中，判定为 pHash 误报（不构成泄漏）："
            f"{verification['cross_split_false_positive']}")
        add(f"- 跨划分对中，尚未核验："
            f"{verification['cross_split_unverified']}")
        add("")
        add("> 核验方式：逐张打开 `reports/leakage_review/contact_sheet_*.png` "
            "左右并排比对个体、姿态、场景与背景；判定记录见 "
            "`reports/leakage_review/visual_verification.json`。"
            "**用户的最终复核结论可覆盖此结果。**")
        add("")
    add("## 审查方法")
    add("")
    add("1. 打开 `reports/leakage_review/contact_sheet_*.png`，左右并排比对；")
    add("2. 若为同一只宠物、同一拍摄批次的不同帧/裁切 → "
        "记为“同一照片变体”（构成跨集合泄漏）；")
    add("3. 若为不同个体、仅品种与构图相似 → 记为“pHash 误报”（不构成泄漏）；")
    add("4. 在 CSV 的 `grade` 列后追加 `人工判定` 与 `备注` 两列并回填；")
    add("5. 判定结果将决定 `scripts/build_clean_split.py` 的排除范围。")
    add("")
    add("## 逐对明细")
    add("")
    add("| # | 跨划分 | pHash 距离 | 复算 | MD5 相同 | 灰度相关度 | 灰度 MAE | 初步分级 |")
    add("|---|---|---|---|---|---|---|---|")
    for r in records:
        add(f"| {r['index']} | {'是' if r['cross_split'] else '否'} | "
            f"{r['phash_distance_recorded']} | "
            f"{r['phash_distance_recomputed']} | "
            f"{'是' if r['identical_md5'] else '否'} | "
            f"{r['pixel_evidence']['grey_corr']} | "
            f"{r['pixel_evidence']['grey_mae']} | "
            f"{r['preliminary_grade']} |")
    add("")
    add("## 跨划分逐对明细（含路径）")
    add("")
    for r in records:
        if not r["cross_split"]:
            continue
        add(f"### #{r['index']} pHash 距离 {r['phash_distance_recorded']}"
            f"（复算 {r['phash_distance_recomputed']}）")
        add("")
        add(f"- A：`{r['a']['split']}` / {r['a']['class']} / "
            f"`{r['a']['path']}`（{r['a']['width']}×{r['a']['height']}）")
        add(f"- B：`{r['b']['split']}` / {r['b']['class']} / "
            f"`{r['b']['path']}`（{r['b']['width']}×{r['b']['height']}）")
        add(f"- MD5 相同：{'是' if r['identical_md5'] else '否'}；"
            f"灰度相关度 {r['pixel_evidence']['grey_corr']}；"
            f"灰度 MAE {r['pixel_evidence']['grey_mae']}；"
            f"RGB MAE {r['pixel_evidence']['rgb_mae']}")
        add(f"- 初步分级：**{r['preliminary_grade']}**")
        add(f"- 依据：{r['basis']}")
        add(f"- 联系表：`{r['contact_sheet']}`")
        add(f"- 目视核验：**{r['visual_verdict']}**"
            + (f"（{r['visual_verdict_note']}）"
               if r["visual_verdict_note"] else ""))
        add("")
    add("## 划分内部的近重复（不构成跨集合泄漏，仅记录）")
    add("")
    add("| # | 集合 | 品种 | pHash 距离 | 灰度相关度 |")
    add("|---|---|---|---|---|")
    for r in records:
        if r["cross_split"]:
            continue
        add(f"| {r['index']} | {r['a']['split']}/{r['b']['split']} | "
            f"{r['a']['class']} | {r['phash_distance_recorded']} | "
            f"{r['pixel_evidence']['grey_corr']} |")
    add("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
