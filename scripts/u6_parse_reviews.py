#!/usr/bin/env python
"""U6-B：只读解析人工复核备注与数据分布诊断（**不改标签、不动原 CSV**）。

用法（在仓库根目录执行）::

    python scripts/u6_parse_reviews.py

产出（``reports/u6_border_collie/``）：

* ``u6_manual_review_parsed.csv`` —— 183 行队列 + 归一化毛色 + 原文
* ``u6_coat_distribution_train_val.csv`` —— 人工确认毛色 vs 自动启发式（分开标注）
* ``u6_sample_counts.csv`` —— 136 类 × train/val 计数（突出目标两类）
* ``u6_confounders_train_val.csv`` —— 复用既有混杂因素，注明来源脚本
* ``u6_target_data_audit.md`` —— 证据分级（直接证据 / 迹象 / 未知）+ 1–2 个假设

**只读**：不修改 ``coat_color_review_queue.csv``，不生成任何重新标注结果。
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.summarize_coat_review import normalise_note  # noqa: E402

OUT = REPO / "reports" / "u6_border_collie"
COAT_DIR = REPO / "reports" / "v2_1_coat_pitbull_diagnostics"
QUEUE = COAT_DIR / "coat_color_review_queue.csv"
AUTO_COAT = COAT_DIR / "coat_color_distribution.csv"
CONFOUNDERS = COAT_DIR / "coat_confounders.csv"
DATA_DIR = REPO / "data" / "v2_processed"
TARGETS = ("collie", "border_collie")


def write_csv(path: Path, rows: list[dict],
              fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_queue() -> tuple[list[dict], Counter]:
    import csv as _csv
    with QUEUE.open(encoding="utf-8") as handle:
        rows = list(_csv.DictReader(handle))
    parsed = []
    for row in rows:
        note = (row.get("review_notes") or "").strip()
        colour = normalise_note(note)
        parsed.append({
            "priority": row.get("priority", ""),
            "split": row.get("split", ""),
            "true_label": row.get("true_label", ""),
            "pred_label": row.get("pred_label", ""),
            "top1_prob": row.get("top1_prob", ""),
            "auto_coat": row.get("coat", ""),
            "auto_coat_confidence": row.get("coat_confidence", ""),
            "manual_colour_normalised": colour,
            "manual_colour_is_uncertain": "yes" if colour in
                                          ("未填写", "未识别", "多犬/非目标犬")
                                          else "no",
            "review_status": (row.get("review_status") or "").strip(),
            "review_notes_raw": note,
            "image_path": row.get("image_path", ""),
        })
    return parsed, Counter(r["manual_colour_normalised"] for r in parsed)


def coat_distribution(parsed: list[dict]) -> list[dict]:
    """人工确认毛色分布（含分母与不确定数量）。"""
    buckets: dict[tuple[str, str], Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for row in parsed:
        key = (row["true_label"], row["split"])
        buckets[key][row["manual_colour_normalised"]] += 1
        totals[key] += 1
    rows = []
    for (label, split), counter in sorted(buckets.items()):
        denominator = totals[(label, split)]
        for colour, count in sorted(counter.items(),
                                    key=lambda kv: -kv[1]):
            rows.append({
                "source": "manual_review_notes",
                "class": label,
                "split": split,
                "colour": colour,
                "count": count,
                "denominator": denominator,
                "ratio": round(count / denominator, 4),
                "is_uncertain": "yes" if colour in
                                ("未填写", "未识别", "多犬/非目标犬") else "no",
            })
    return rows


def auto_distribution() -> list[dict]:
    """复用既有自动 HSV 结果，**明确标注为启发式、非真值**。"""
    if not AUTO_COAT.exists():
        return []
    rows = []
    with AUTO_COAT.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("class") not in TARGETS:
                continue
            rows.append({
                "source": "auto_hsv_heuristic(非真值)",
                "class": row["class"],
                "split": row["split"],
                "colour": row.get("coat_zh") or row.get("coat"),
                "count": row.get("count"),
                "denominator": row.get("denominator"),
                "ratio": row.get("ratio"),
                "is_uncertain": "yes" if (row.get("coat") == "uncertain")
                                else "no",
            })
    return rows


def sample_counts() -> list[dict]:
    rows = []
    for split in ("train", "val"):
        base = DATA_DIR / split
        for class_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            count = len(list(class_dir.glob("*.jpg")))
            rows.append({
                "class": class_dir.name,
                "split": split,
                "count": count,
                "is_target_pair": "yes" if class_dir.name in TARGETS else "no",
            })
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not QUEUE.exists():
        print(f"[u6b] missing {QUEUE}", file=sys.stderr)
        return 1

    parsed, colour_counter = parse_queue()
    write_csv(OUT / "u6_manual_review_parsed.csv", parsed)
    print(f"[u6b] 人工备注 {len(parsed)} 行；颜色分布: {dict(colour_counter)}")

    dist = coat_distribution(parsed) + auto_distribution()
    write_csv(OUT / "u6_coat_distribution_train_val.csv", dist)
    print(f"[u6b] 毛色分布行数 {len(dist)}")

    counts = sample_counts()
    write_csv(OUT / "u6_sample_counts.csv", counts)

    # 混杂因素：复制既有结果并加来源标注（不重跑全量测量）
    if CONFOUNDERS.exists():
        with CONFOUNDERS.open(encoding="utf-8") as handle:
            conf_rows = list(csv.DictReader(handle))
        for row in conf_rows:
            row["source"] = ("复用 reports/v2_1_coat_pitbull_diagnostics/"
                             "coat_confounders.csv（由 scripts/diagnose_coat_"
                             "color.py 生成，本轮未重跑）")
        write_csv(OUT / "u6_confounders_train_val.csv", conf_rows)
        print(f"[u6b] 混杂因素 {len(conf_rows)} 行（复用既有结果）")

    # ---- 关键统计 ----
    def acc(label: str, colour: str) -> tuple[int, int]:
        ok = sum(1 for r in parsed
                 if r["true_label"] == label
                 and r["manual_colour_normalised"] == colour
                 and r["true_label"] == r["pred_label"])
        bad = sum(1 for r in parsed
                  if r["true_label"] == label
                  and r["manual_colour_normalised"] == colour
                  and r["true_label"] != r["pred_label"])
        return ok, bad

    bw_collie = acc("collie", "黑白色")
    bw_border = acc("border_collie", "黑白色")
    wy_collie = acc("collie", "白黄色系")
    tri_collie = acc("collie", "三色及以上")
    merle_collie = acc("collie", "陨石色")
    unknown = sum(1 for r in parsed if r["manual_colour_is_uncertain"] == "yes")

    # 目标两类训练/验证样本数
    pair_counts = {(r["class"], r["split"]): r["count"] for r in counts
                   if r["is_target_pair"] == "yes"}

    lines: list[str] = []
    add = lines.append
    add("# U6-B：目标两类数据与人工备注诊断")
    add("")
    add("> **不改标签**：本文件只读解析既有产物，未修改 `coat_color_review_queue.csv`，")
    add("> 也未生成任何重新标注结果。")
    add("")
    add("## 1. 人工备注覆盖情况")
    add("")
    add(f"- 队列总行数：**{len(parsed)}**（按「模型误判或毛色待复核」入队，"
        "**存在选择偏差**）")
    add(f"- 可归一化到明确颜色：**{len(parsed) - unknown}**")
    add(f"- 无法确认（未填写 / 未识别 / 多犬非目标犬）：**{unknown}** → 一律标 "
        "`uncertain`，**不猜测**")
    add("")
    add("| 归一化颜色 | 行数 |")
    add("|---|---|")
    for colour, count in colour_counter.most_common():
        add(f"| {colour} | {count} |")
    add("")
    add("## 2. 直接证据（可复核计数）")
    add("")
    add("| 观察 | 计数 | 说明 |")
    add("|---|---|---|")
    if bw_collie[0] + bw_collie[1]:
        add(f"| `collie` 黑白色：模型判对 / 判错 | {bw_collie[0]:d} / "
            f"{bw_collie[1]:d}（共 {sum(bw_collie)}） | 判错率 "
            f"{bw_collie[1] / sum(bw_collie):.1%} |")
    if bw_border[0] + bw_border[1]:
        add(f"| `border_collie` 黑白色：判对 / 判错 | {bw_border[0]:d} / "
            f"{bw_border[1]:d}（共 {sum(bw_border)}） | 判错率 "
            f"{bw_border[1] / sum(bw_border):.1%} |")
    if wy_collie[0] + wy_collie[1]:
        add(f"| `collie` 白黄色系：判对 / 判错 | {wy_collie[0]:d} / "
            f"{wy_collie[1]:d} | — |")
    if tri_collie[0] + tri_collie[1]:
        add(f"| `collie` 三色及以上：判对 / 判错 | {tri_collie[0]:d} / "
            f"{tri_collie[1]:d} | — |")
    if merle_collie[0] + merle_collie[1]:
        add(f"| `collie` 陨石色：判对 / 判错 | {merle_collie[0]:d} / "
            f"{merle_collie[1]:d} | — |")
    add("")
    add("**样本量警示**：上述分母来自复核队列（已富集误判样本），"
        "**不是**全量准确率；且 `collie` 黑白色分母仅 "
        f"{sum(bw_collie)} 条，单条即可显著改变比例。")
    add("")
    add("## 3. 目标两类样本规模（全量，非队列）")
    add("")
    add("| 类别 | train | val |")
    add("|---|---|---|")
    for label in TARGETS:
        add(f"| `{label}` | {pair_counts.get((label, 'train'), 0)} | "
            f"{pair_counts.get((label, 'val'), 0)} |")
    add("")
    add("## 4. 迹象（相关但不构成因果）")
    add("")
    add("1. 自动 HSV 毛色启发式在全部 297 张目标类图片中 **56.2%（167/297）"
        "为 uncertain**，因此**不能**用自动毛色做严格分层；人工备注只覆盖"
        f"{len(parsed)} 行且富集误判样本。")
    add("2. 队列内 `collie` 黑白样本的判错方向主要流向 `border_collie`；"
        "而 `border_collie` 黑白样本判对率明显更高——方向与「黑白柯利易被判成"
        "边牧」的既有观察一致。")
    add("3. 既有混杂因素诊断（尺寸/宽高比/亮度/背景环带）**效应量均 < 0.25**，"
        "未发现系统性裁剪或背景差异（见 `u6_confounders_train_val.csv`）。")
    add("")
    add("## 5. 未知 / 无法判断")
    add("")
    add("1. 队列中被标为 `uncertain` 的样本究竟属于哪种毛色，**无法从现有自由文本确定**；")
    add("   要做毛色分层必须另行人工标注（需人工批准）。")
    add("2. 目标两类是否存在**系统性标签错误**（同犬不同标）——现有证据不足以判断，"
        "也未发现可直接举证的样本。")
    add("3. 毛色与误判之间是因果还是仅相关，**无法由观察性数据确定**。")
    add("")
    add("## 6. 最值得验证的假设（U6-C 的实验依据）")
    add("")
    add("| # | 假设 | 依据 | 对应实验 |")
    add("|---|---|---|---|")
    add("| H1 | 模型对毛色（尤其黑白对比强度）存在过拟合，"
        "温和的颜色扰动可降低该依赖 | 队列中黑白 `collie` 判错率最高；"
        "训练集两类毛色分布不同（`collie` 有貂色/红白，`border_collie` 无） | "
        "`exp01_pair_color_jitter` |")
    add("| H2 | 目标两类样本量偏少（114/121）导致其决策边界欠拟合，"
        "温和加权采样可改善 | 两类 support 在 136 类中偏小，且互相竞争 | "
        "`exp02_pair_sampler` |")
    add("")
    add("**是否值得围绕毛色做实验？** 是——但仅作为**一个**低风险变量，"
        "且必须接受\"可能无效\"的结论。若 exp01 与 exp02 均无改善，"
        "应转向数据增补与标签复核，而非继续堆叠增强。")
    add("")
    add("## 7. 未生成的项目")
    add("")
    add("`u6_relabel_proposal.csv` **未生成**：现有自由文本备注中没有任何一条"
        "明确指出\"该图标签错误\"，因此不提议重标（不凭外观改标签）。")
    add("")

    (OUT / "u6_target_data_audit.md").write_text("\n".join(lines),
                                                encoding="utf-8")
    print(f"[u6b] wrote u6_target_data_audit.md")
    print(f"[u6b] collie 黑白 {bw_collie} | border 黑白 {bw_border} | "
          f"uncertain {unknown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
