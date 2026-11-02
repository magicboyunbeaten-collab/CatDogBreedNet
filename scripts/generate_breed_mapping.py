#!/usr/bin/env python
"""U5.5：从已审核类别目录生成 136 类中文显示映射（可复现、可审计）。

用法（在仓库根目录执行）::

    python scripts/generate_breed_mapping.py

输入
----
* ``artifacts/v2_1_136classes_seed42/class_names.json`` —— 决定**有效类别集合**
  与**输出顺序**（必须与 checkpoint 的 ``class_names`` 完全一致）；
* ``reports/v2_class_catalog.csv`` —— 提供每个类别的已审核 ``chinese_name``；
* 现有 ``frontend/src/utils/breedNames.js`` —— 提取旧 37 类中文名，**原样保留**。

输出
----
* 重写 ``frontend/src/utils/breedNames.js`` 的 ``BREED_NAMES_ZH`` 为 136 条；
* ``reports/u5_5_v2_1_integration/breed_mapping_audit.csv`` —— 逐类审计表。

内置断言（任一不满足即退出，不写半成品）
------------------------------------------
136 条 / 键唯一 / 中文名唯一 / 旧 37 条逐一未变 / 候选四类名称与面板一致 /
无缺失 label / 无臆造名称。

**只读权重与目录**；不写 ``artifacts/`` 与 ``data/``。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

V2_1_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
#: V1.1（37 类）—— 用于界定"哪些中文名必须原样保留"
V11_DIR = _REPO_ROOT / "artifacts"
CATALOG = _REPO_ROOT / "reports" / "v2_class_catalog.csv"
BREED_NAMES_JS = _REPO_ROOT / "frontend" / "src" / "utils" / "breedNames.js"
DEFAULT_OUT = _REPO_ROOT / "reports" / "u5_5_v2_1_integration"

#: 候选面板使用的中文名（必须与 backend/app/services/candidate_group.py 一致）
CANDIDATE_PANEL_ZH = {
    "american_pit_bull_terrier": "美国比特斗牛梗",
    "american_staffordshire_terrier": "美国斯塔福郡梗",
    "staffordshire_bull_terrier": "斯塔福郡斗牛梗",
    "american_bulldog": "美国斗牛犬",
}

#: **已审核目录的缺陷修补**：``reports/v2_class_catalog.csv`` 中这两个类别的
#: ``chinese_name`` 实际是英文（分别是 ``basenji`` 与 ``Sealyham_terrier``），
#: 渲染时会退化成英文下划线标签。这里用通行中文犬种译名补齐，并在
#: ``breed_mapping_audit.csv`` 与实施报告中**逐项列出**，不做静默猜测。
#: 中文译名取自犬种通用中文名（非臆造）：Basenji = 巴辛吉犬；
#: Sealyham Terrier = 西里汉梗。
CATALOG_NAME_OVERRIDES: dict[str, tuple[str, str]] = {
    "basenji": ("巴辛吉犬", "catalog 中为英文 'basenji'，补通行中文译名"),
    "sealyham_terrier": (
        "西里汉梗", "catalog 中为英文 'Sealyham_terrier'，补通行中文译名"),
}

HEADER = '''/**
 * 136 类中文显示名（V2.1 / 136 类正式模型）。
 *
 * 键**完全等于** `artifacts/v2_1_136classes_seed42/class_names.json` 中的
 * canonical label，顺序与该文件一致（即模型输出顺序），大小写与下划线保持
 * 原样，不做任何合并或重命名。未知标签回退英文原名，因此缺映射不会渲染成空。
 *
 * 本文件仅用于显示：模型权重、后端 API、数据库与实验报告一律保留原始
 * 英文 canonical label。
 *
 * 名称来源：`reports/v2_class_catalog.csv` 的 `chinese_name`（已审核目录）。
 * 原有 37 类的中文名与 V1.1 时期**完全一致**，未做任何改写。
 * 由 `scripts/generate_breed_mapping.py` 生成，请勿手工编辑。
 */

const BREED_NAMES_ZH = {
'''

FOOTER = '''}

/**
 * 相近犬种候选组的附加中文名（V2.1 候选模型能力，U5.2 方案 B1 四类）。
 *
 * 与 BREED_NAMES_ZH 中的同名条目保持一致；单独保留一份，供候选面板在
 * 不依赖完整映射的情况下也能正确显示。
 */
export const CANDIDATE_BREED_NAMES_ZH = {
  american_pit_bull_terrier: '美国比特斗牛梗',
  american_staffordshire_terrier: '美国斯塔福郡梗',
  staffordshire_bull_terrier: '斯塔福郡斗牛梗',
  american_bulldog: '美国斗牛犬',
}

/** 候选组的 canonical label（与后端 CANDIDATE_GROUP 保持一致）。 */
export const CANDIDATE_GROUP = [
  'american_pit_bull_terrier',
  'american_staffordshire_terrier',
  'staffordshire_bull_terrier',
  'american_bulldog',
]

/** Chinese display name for a breed label; falls back to the raw label. */
export function getBreedDisplayName(breed) {
  if (!breed) return ''
  return BREED_NAMES_ZH[breed] || CANDIDATE_BREED_NAMES_ZH[breed] || breed
}

/** A copy of the full mapping (136 entries for the V2.1 class space). */
export function getBreedMapping() {
  return { ...BREED_NAMES_ZH }
}

export const BREED_MAPPING_SIZE = Object.keys(BREED_NAMES_ZH).length
'''


def read_old_mapping(path: Path) -> dict[str, str]:
    """从现有 breedNames.js 提取**旧 37 类**映射（键 → 中文名）。

    只保留 V1.1 ``artifacts/class_names.json`` 中的 37 个标签，这样脚本可反复
    运行：即使文件已被生成为 136 条，也能准确识别"哪些是必须原样保留的旧名"。
    """
    source = path.read_text(encoding="utf-8")
    match = re.search(r"const BREED_NAMES_ZH = \{(.*?)\n\}", source, re.S)
    if not match:
        raise SystemExit("[mapping] 无法从现有 breedNames.js 解析 BREED_NAMES_ZH")
    pairs = re.findall(r"^\s{2}([A-Za-z_][\w]*)\s*:\s*'([^']*)'",
                       match.group(1), re.M)
    if not pairs:
        raise SystemExit("[mapping] 现有映射为空，拒绝继续")

    v11_labels = json.loads(
        (V11_DIR / "class_names.json").read_text(encoding="utf-8"))
    parsed = dict(pairs)
    old = {label: parsed[label] for label in v11_labels if label in parsed}
    if len(old) != len(v11_labels):
        absent = [l for l in v11_labels if l not in parsed]
        raise SystemExit(
            f"[mapping] 现有映射缺少 {len(absent)} 个 V1.1 旧类别：{absent[:5]}")
    return old


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true",
                        help="只校验并打印统计，不写文件")
    args = parser.parse_args(argv)

    class_names = json.loads(
        (V2_1_DIR / "class_names.json").read_text(encoding="utf-8"))
    catalog = {}
    with CATALOG.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            label = row["canonical_label"]
            name = (row.get("chinese_name") or "").strip()
            if label and name:
                catalog[label] = name

    old = read_old_mapping(BREED_NAMES_JS)
    print(f"[mapping] V2.1 类别数 {len(class_names)}；"
          f"catalog 有中文名 {len(catalog)}；旧映射 {len(old)}")

    # ---- 逐类解析中文名：旧映射优先（保证含义不变），其余取 catalog ----
    resolved: list[tuple[str, str, str]] = []   # (label, name, source)
    missing: list[str] = []
    for label in class_names:
        if label in old:
            resolved.append((label, old[label], "existing_37"))
        elif label in CATALOG_NAME_OVERRIDES:
            resolved.append((label, CATALOG_NAME_OVERRIDES[label][0],
                             "curated_override"))
        elif label in catalog:
            source = ("candidate_panel" if label in CANDIDATE_PANEL_ZH
                      else "catalog")
            resolved.append((label, catalog[label], source))
        else:
            missing.append(label)

    # ---- 断言 ----
    errors: list[str] = []
    if len(class_names) != 136:
        errors.append(f"类别数不是 136（实际 {len(class_names)}）")
    if len(set(class_names)) != len(class_names):
        errors.append("canonical label 有重复")
    if missing:
        errors.append(f"缺中文名的类别：{missing}")
    names = [name for _, name, _ in resolved]
    if len(set(names)) != len(names):
        dup = {n for n in names if names.count(n) > 1}
        errors.append(f"中文名重复：{sorted(dup)}")
    # 旧 37 类逐一未变
    for label, name in old.items():
        if label not in class_names:
            continue
        actual = dict((r[0], r[1]) for r in resolved)[label]
        if actual != name:
            errors.append(f"旧类别 {label} 名称被改变：{name} → {actual}")
    # 旧 37 类全部仍可解析
    for label in old:
        if label not in class_names:
            errors.append(f"旧类别 {label} 不在 136 类集合中")
    # 候选四类与面板一致
    for label, name in CANDIDATE_PANEL_ZH.items():
        if label not in class_names:
            errors.append(f"候选类别 {label} 不在 136 类集合中")
        elif dict((r[0], r[1]) for r in resolved)[label] != name:
            errors.append(f"候选类别 {label} 名称与面板不一致")
    # 每个中文名都必须真的含中文字符（防止英文标签冒充中文名）
    cjk = re.compile(r"[\u4e00-\u9fff]")
    non_chinese = [(label, name) for label, name, _ in resolved
                   if not cjk.search(name)]
    if non_chinese:
        errors.append(f"以下类别的显示名不含中文字符：{non_chinese}")

    if errors:
        print("[mapping] 校验失败，未写入任何文件：", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(f"[mapping] 校验通过：136 条、键唯一、中文名唯一、"
          f"旧 {len(old)} 条未变、候选 4 条一致")

    # ---- 生成 JS ----
    lines = []
    for label, name, source in resolved:
        lines.append(f"  {label}: '{name}',")
    source_js = HEADER + "\n".join(lines) + "\n" + FOOTER

    if args.dry_run:
        print("[mapping] --dry-run：跳过写入")
        return 0

    BREED_NAMES_JS.write_text(source_js, encoding="utf-8")
    print(f"[mapping] wrote {BREED_NAMES_JS}")

    # ---- 审计表 ----
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "breed_mapping_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "canonical_label", "chinese_name",
                         "name_source", "in_v2_1_class_names",
                         "in_catalog", "catalog_name", "old_37_preserved",
                         "matches_candidate_panel", "verification", "note"])
        for index, (label, name, source) in enumerate(resolved):
            note = CATALOG_NAME_OVERRIDES[label][1] if label in \
                CATALOG_NAME_OVERRIDES else ""
            writer.writerow([
                index, label, name, source, "yes",
                "yes" if label in catalog else "no",
                catalog.get(label, ""),
                "yes" if (label in old and old[label] == name) else "n/a",
                ("yes" if CANDIDATE_PANEL_ZH[label] == name else "NO")
                if label in CANDIDATE_PANEL_ZH else "n/a",
                "ok", note,
            ])
    print(f"[mapping] wrote {audit_path}（{len(resolved)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
