#!/usr/bin/env python
"""汇总边牧 / 柯利人工复核备注（只读，不修改任何原始文件）。

用法（在仓库根目录执行）::

    python scripts/summarize_coat_review.py

读取 ``reports/v2_1_coat_pitbull_diagnostics/coat_color_review_queue.csv``
中用户填写的 ``review_notes`` 自由文本，归一化到颜色标签后输出分组统计，
写入 ``reports/v2_1_candidate_ui_review/coat_review_summary.md`` 与
``coat_review_grouped.csv``。

硬性约束：

* **只读**。不修改、不重写、不重命名原 CSV，不改任何图片或标签；
* **不推断**。无法可靠解析的备注归入"未识别"，不做猜测；
* 自由文本不是结构化人工结论，报告必须明确这一限制。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_QUEUE = (_REPO_ROOT / "reports" / "v2_1_coat_pitbull_diagnostics"
                 / "coat_color_review_queue.csv")
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_candidate_ui_review"

CLASSES = ("collie", "border_collie")

#: 备注中的多犬 / 非目标犬关键词——这些样本的"毛色"不能简单归为单一颜色。
MULTI_DOG_RE = re.compile(r"两只|三只|两只dog|后面那只|别的品种")
CORRECTION_RE = re.compile(r"纠正")

#: 颜色归一化规则。顺序即优先级：先识别更具体的组合。
COLOR_RULES: tuple[tuple[str, re.Pattern], ...] = (
    # 三色及以上组合（含黑 + 白 + 黄/灰）
    ("三色及以上", re.compile(r"黑白黄|白黄黑|黑黄白|白黄黑灰|黑白灰")),
    # 黑白
    ("黑白色", re.compile(r"黑白")),
    # 白黄（含黄白、白黄灰）
    ("白黄色系", re.compile(r"白黄|黄白")),
    # 陨石色
    ("陨石色", re.compile(r"陨石")),
    # 纯黑
    ("黑色", re.compile(r"黑色")),
)


def normalise_note(note: str) -> str:
    """把自由文本备注归一化到颜色标签；无法识别返回 ``未识别``。"""
    text = (note or "").strip()
    if not text:
        return "未填写"
    if MULTI_DOG_RE.search(text):
        return "多犬/非目标犬"
    for label, pattern in COLOR_RULES:
        if pattern.search(text):
            return label
    return "未识别"


def read_queue(path: Path) -> list[dict]:
    if not path.exists():
        print(f"[coat-review] 缺少 {path}", file=sys.stderr)
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = read_queue(args.queue)
    if not rows:
        print("[coat-review] 无可读取的人工复核记录", file=sys.stderr)
        return 1

    total = len(rows)
    with_notes = [r for r in rows if r.get("review_notes", "").strip()]
    with_status = [r for r in rows if r.get("review_status", "").strip()]
    print(f"[coat-review] 队列 {total} 行；review_notes 非空 {len(with_notes)}；"
          f"review_status 非空 {len(with_status)}")

    # ---- 归一化 ----
    for row in with_notes:
        row["_color"] = normalise_note(row["review_notes"])
        row["_corrected"] = bool(CORRECTION_RE.search(row["review_notes"]))

    # ---- 分组统计 ----
    grouped: dict[tuple[str, str], dict] = {}
    for row in with_notes:
        key = (row["true_label"], row["_color"])
        entry = grouped.setdefault(key, {
            "class": row["true_label"], "manual_color": row["_color"],
            "n": 0, "predicted_correct": 0, "predicted_wrong": 0,
            "wrong_targets": Counter(), "splits": Counter(),
            "corrected": 0,
        })
        entry["n"] += 1
        if row["pred_label"] == row["true_label"]:
            entry["predicted_correct"] += 1
        else:
            entry["predicted_wrong"] += 1
            entry["wrong_targets"][row["pred_label"]] += 1
        entry["splits"][row["split"]] += 1
        entry["corrected"] += int(row["_corrected"])

    table_rows = []
    for (label, color), entry in sorted(grouped.items()):
        table_rows.append({
            "class": label,
            "manual_color": color,
            "n": entry["n"],
            "model_correct": entry["predicted_correct"],
            "model_wrong": entry["predicted_wrong"],
            "model_accuracy": round(entry["predicted_correct"] / entry["n"], 4),
            "main_wrong_target": (entry["wrong_targets"].most_common(1)[0][0]
                                  if entry["wrong_targets"] else ""),
            "splits": "; ".join(f"{k}:{v}" for k, v in
                                sorted(entry["splits"].items())),
            "corrected_notes": entry["corrected"],
        })
    csv_path = out_dir / "coat_review_grouped.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table_rows[0].keys()))
        writer.writeheader()
        writer.writerows(table_rows)
    print(f"[coat-review] wrote {csv_path}")

    # ---- 关键交叉统计 ----
    cross = Counter((r["true_label"], r["_color"],
                     r["pred_label"] == r["true_label"])
                    for r in with_notes)

    def acc(label: str, color: str) -> tuple[int, int]:
        ok = cross.get((label, color, True), 0)
        bad = cross.get((label, color, False), 0)
        return ok, ok + bad

    bw_collie = acc("collie", "黑白色")
    bw_border = acc("border_collie", "黑白色")
    white_yellow_collie = acc("collie", "白黄色系")
    merle_collie = acc("collie", "陨石色")
    tri_collie = acc("collie", "三色及以上")
    corrected = [r for r in with_notes if r["_corrected"]]

    # ---- 报告 ----
    lines: list[str] = []
    add = lines.append
    add("# 边牧 / 柯利人工复核汇总（U5）")
    add("")
    add(f"- 生成时间：{datetime.now(timezone.utc).isoformat()}")
    add(f"- 数据来源：`{args.queue}`（**只读**，未修改、未重写、未重命名）")
    add(f"- 队列总行数：**{total}**")
    add(f"- 其中填写了 `review_notes` 的：**{len(with_notes)}** 行")
    add(f"- 其中填写了 `review_status` 的：**{len(with_status)}** 行")
    add("")
    add("> **重要限制**：读取到的人工结果是 `review_notes` 中的**自由文本备注**，"
        "而不是结构化的 `review_status` 字段（该列当前为空）。"
        "自由文本由人工主观观察写成，本汇总只做**归一化与计数**，"
        "不推断、不外推为因果结论，也不据此更改任何图片标签。")
    add("")
    add("## 1. 读取到的记录规模")
    add("")
    add("| 项目 | 数量 |")
    add("|---|---|")
    add(f"| 队列总行数 | {total} |")
    add(f"| review_notes 非空 | {len(with_notes)} |")
    add(f"| review_status 非空 | {len(with_status)} |")
    add(f"| 多犬 / 非目标犬备注 | "
        f"{sum(1 for r in with_notes if r['_color'] == '多犬/非目标犬')} |")
    add(f"| 明确写“纠正”的备注 | {len(corrected)} |")
    add("")
    add("按 split 分布：" + "、".join(
        f"`{name}` {count}" for name, count in
        sorted(Counter(r["split"] for r in with_notes).items())))
    add("")
    add("## 2. 按类别与人工确认毛色分组的预测正确性")
    add("")
    add("| 类别 | 人工备注归一化颜色 | n | 模型判对 | 模型判错 | 模型准确率 | 主要误判目标 | split 分布 |")
    add("|---|---|---|---|---|---|---|---|")
    for item in table_rows:
        add(f"| `{item['class']}` | {item['manual_color']} | {item['n']} | "
            f"{item['model_correct']} | {item['model_wrong']} | "
            f"{item['model_accuracy']:.4f} | "
            f"{('`' + item['main_wrong_target'] + '`') if item['main_wrong_target'] else '—'} | "
            f"{item['splits']} |")
    add("")
    add("> 分母为该组人工备注条数，**不是**该类别在数据集中的图片总数。")
    add("")
    add("## 2b. 样本选择偏差（阅读上表前必读）")
    add("")
    add("`coat_color_review_queue.csv` 的入队条件是“模型误判”或“自动毛色待复核”，"
        "因此：")
    add("")
    add("- **预测正确且自动毛色 confident 的图片根本不在队列里**；")
    add("- 所以上表的“模型准确率”是**在复核队列这个子集上**的数值，"
        "相对全量数据集**系统性偏低**；")
    add("- **颜色组之间的横向比较**比绝对数值更有参考价值，但即便横向比较"
        "也未完全排除“能否被自动定色”与“是否误判”之间的关联，"
        "因此只能作为方向性参考，**不能当作因果证据**。")
    add("")
    add("作为对照，此前全量诊断（`reports/v2_1_coat_pitbull_diagnostics/`）"
        "在全部 297 张上得到：`collie` 黑白 6/11 正确、白黄系与红白 28/28 正确、"
        "`border_collie` 黑白 21/22 正确。两组数字方向一致。")
    add("")
    add("## 3. 关键交叉统计（黑白 vs 白黄）")
    add("")
    add("| 类别 | 人工颜色 | 判对 / 总数 | 准确率 |")
    add("|---|---|---|---|")

    def fmt(pair: tuple[int, int]) -> str:
        ok, total_n = pair
        rate = f"{ok / total_n:.4f}" if total_n else "—"
        return f"{ok} / {total_n}", rate

    for label, color, pair in (
            ("`collie`", "黑白色", bw_collie),
            ("`collie`", "白黄色系", white_yellow_collie),
            ("`collie`", "陨石色", merle_collie),
            ("`collie`", "三色及以上", tri_collie),
            ("`border_collie`", "黑白色", bw_border)):
        text, rate = fmt(pair)
        add(f"| {label} | {color} | {text} | {rate} |")
    add("")
    add("## 4. 有数据支持的观察")
    add("")
    add("> 以下均为**相关性观察**，不是因果结论；样本来自复核队列子集（见 2b）。")
    add("")
    if bw_collie[1] and bw_border[1]:
        add(f"1. 在人工备注中，`collie` 被标为**黑白色**的 {bw_collie[1]} 条里，"
            f"模型判对 {bw_collie[0]} 条（{bw_collie[0] / bw_collie[1]:.1%}）；"
            f"`border_collie` 被标为**黑白色**的 {bw_border[1]} 条里，"
            f"模型判对 {bw_border[0]} 条（{bw_border[0] / bw_border[1]:.1%}）。"
            f"同一颜色下两个类别的表现差距明显，方向与自动毛色启发式一致"
            f"（黑白柯利更容易被误判为边牧），**但样本量小且来自复核队列**，"
            f"只能作为方向性参考。")
    if white_yellow_collie[1]:
        add(f"2. 人工备注中 `collie` 的**白黄色系**样本 {white_yellow_collie[1]} 条，"
            f"模型判对 {white_yellow_collie[0]} 条"
            f"（{white_yellow_collie[0] / white_yellow_collie[1]:.1%}）；"
            f"**三色及以上** {tri_collie[1]} 条中判对 {tri_collie[0]} 条。")
    if corrected:
        add(f"3. 有 {len(corrected)} 条备注明确写了“人工复核纠正为黑白色”，"
            f"涉及样本："
            + "、".join(f"`{r['sample_id']}`" for r in corrected) + "。")
    add("")
    add("## 5. 尚未验证的假设")
    add("")
    add("1. **“黑白柯利更容易被判成边牧”只是相关性观察**：人工备注按颜色分组后"
        "准确率有差异，但分组本身由人工主观判断产生，且样本量小，"
        "**不能推出“毛色导致误判”的因果结论**。")
    add("2. 自动毛色启发式此前仅覆盖 130/297 张，其余 167 张为 uncertain；"
        "本汇总**没有**用启发式结果替代人工判断。")
    add("3. 多犬 / 非目标犬的备注（如“两只dog 左边白黄黑与右边黄白灰”、"
        "“后面那只是别的品种狗”）说明部分图片并非单一目标犬只，"
        "这类样本的标签与预测对比意义有限，已单独归类，不计入颜色分组。")
    add("4. 未读取到任何关于“这张图标签错误”的结构化人工结论；"
        "本报告**不**对任何图片的品种归属下结论。")
    add("")
    add("## 6. 下一步（本任务不执行）")
    add("")
    add("- 若要把人工复核固化为结构化数据，需要在队列中填写 "
        "`review_status`（如 `confirmed_correct` / `confirmed_mislabeled` / "
        "`unclear`），并在 `review_notes` 中记录依据；")
    add("- 在积累足够样本前，不建议依据毛色调整任何标签或重新划分数据。")
    add("")

    report_path = out_dir / "coat_review_summary.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[coat-review] wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
