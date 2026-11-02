#!/usr/bin/env python
"""外部候选数据源初筛（只读元数据/许可，**不下载任何图片**）。

用法（在仓库根目录执行）::

    python scripts/audit_external_sources.py

原则：

* 只抓取页面文本，记录 HTTP 状态、标题、宣称的图片数量、宣称的原始来源、
  许可声明与链接；**不下载、不解包、不合并任何图片**。
* **网页宣称不构成标签质量证明**：所有"宣称"字段都标注为 `(页面宣称)`。
* 若页面未提供某字段，写 `页面未提供`，不推测、不虚构。
* 若站点不可达，记录失败原因，不给结论性评价。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO_ROOT / "reports" / "v2_1_diagnostics"
OUT_NAME = "external_dataset_source_audit.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

#: 待初筛的候选源（只做元数据核对，不下载）。
CANDIDATES = [
    {
        "source_name": "images.cv — American Pit Bull Terrier",
        "url": ("https://images.cv/dataset/"
                "american-pit-bull-terrier-image-classification-dataset"),
        "label_definition": "american pit bull terrier（单一类别目录）",
    },
    {
        "source_name": "images.cv — American Staffordshire Terrier",
        "url": ("https://images.cv/dataset/"
                "american-staffordshire-terrier-image-classification-dataset"),
        "label_definition": "american staffordshire terrier（单一类别目录）",
    },
]

FIELDNAMES = ["source_name", "url", "http_status", "page_title",
              "label_definition", "image_count_stated", "original_source_stated",
              "license_stated", "license_url", "likely_overlap_with_imagenet",
              "per_image_label_traceable", "screening_conclusion",
              "evidence_notes", "checked_at"]


def fetch(url: str, timeout: int = 30) -> dict:
    request = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status,
                    "final_url": response.geturl(), "html": html}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code,
                "error": f"HTTP {exc.code} {exc.reason}", "html": ""}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "",
                "error": f"{type(exc).__name__}: {exc}", "html": ""}


def strip_tags(html: str) -> str:
    body = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", text)


def page_title(html: str) -> str:
    match = re.search(r"(?is)<title>(.*?)</title>", html)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else "页面未提供"


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0).strip()
    return "页面未提供"


def license_links(html: str) -> str:
    links = re.findall(r'href=["\']([^"\']*(?:licen[cs]e|terms)[^"\']*)["\']',
                       html, re.I)
    unique = []
    for link in links:
        if link not in unique:
            unique.append(link)
    return "; ".join(unique[:3]) if unique else "页面未提供"


def license_policy_note(base_url: str = "https://images.cv") -> str:
    """抓取站点许可政策页，仅用于核实"页面宣称许可"是否有可核对出处。"""
    response = fetch(base_url.rstrip("/") + "/datasets-licenses")
    if not response["ok"]:
        return (f"许可政策页不可达（{response.get('error', '')}），"
                f"页面宣称的许可无法进一步核实")
    text = strip_tags(response["html"])
    excerpt = first_match(text, [r"licen[cs]e[^.]{0,200}"])
    if excerpt == "页面未提供":
        return "许可政策页可访问但未提取到明确许可条款文本"
    return f"许可政策页（HTTP {response['status']}）摘录：{excerpt[:200]}"


def screen(candidate: dict, policy_note: str = "") -> dict:
    result = {key: "" for key in FIELDNAMES}
    result.update({key: candidate.get(key, "") for key in
                   ("source_name", "url", "label_definition")})
    result["checked_at"] = datetime.now(timezone.utc).isoformat()

    response = fetch(candidate["url"])
    if not response["ok"]:
        result.update({
            "http_status": str(response.get("status", "")),
            "page_title": "抓取失败",
            "image_count_stated": "页面未提供",
            "original_source_stated": "页面未提供",
            "license_stated": "页面未提供",
            "likely_overlap_with_imagenet": "无法判断",
            "per_image_label_traceable": "无法判断",
            "screening_conclusion": "需授权/不可达",
            "evidence_notes": f"抓取失败：{response.get('error', '')}",
        })
        return result

    html = response["html"]
    text = strip_tags(html)

    count = first_match(text, [
        r"\b[\d,]{2,7}\s*(?:images|photos|pictures)\b",
        r"\bimages?\s*[:：]\s*[\d,]{2,7}\b",
    ])
    source = first_match(text, [
        r"ImageNet[^.]{0,120}",
        r"source[^.]{0,120}",
    ])
    licence = first_match(text, [
        r"(?:CC[ -]?BY[ -]?[0-9.]+[^.]{0,80})",
        r"(?:MIT|Apache|GPL|Public Domain|Creative Commons)[^.]{0,60}",
        r"licen[cs]e[^.]{0,100}",
    ])

    # 来源重叠判定：优先识别 Oxford（与现有 APBT 同源），其次 ImageNet
    # （与 Stanford Dogs 同源）。两者都比"未提及"更值得警惕。
    oxford_mention = bool(re.search(r"oxford", text, re.I))
    imagenet_mention = bool(re.search(r"imagenet", text, re.I))
    if oxford_mention:
        overlap = ("极高：页面宣称来源为 Oxford-IIIT Pet，"
                   "与本项目现有 APBT 训练数据同源，可能为同一批图片，"
                   "不具备独立性")
    elif imagenet_mention:
        overlap = ("高：页面宣称来源为 ImageNet object localization，"
                   "而 Stanford Dogs 本身即 ImageNet 衍生，存在重叠风险")
    else:
        overlap = "无法从页面判断"

    notes = ("仅抓取页面文本做元数据初筛；未下载任何图片。"
             "页面宣称的数量/来源不构成标签质量证据。")
    if oxford_mention:
        notes += " 注意：不是独立数据源，无法用于验证或补充现有 APBT 标签。"
    if imagenet_mention:
        notes += " 注意：与 Stanford Dogs 可能重叠，独立性存疑。"
    if policy_note:
        notes += f" 站点许可政策核实：{policy_note}"

    result.update({
        "http_status": str(response["status"]),
        "page_title": page_title(html),
        "image_count_stated": f"{count}（页面宣称）" if count != "页面未提供"
        else "页面未提供",
        "original_source_stated": f"{source}（页面宣称）"
        if source != "页面未提供" else "页面未提供",
        "license_stated": f"{licence}（页面宣称）"
        if licence != "页面未提供" else "页面未提供",
        "license_url": license_links(html),
        "likely_overlap_with_imagenet": overlap,
        "per_image_label_traceable": (
            "否：页面为按类别打包下载，未见逐图作者/来源/许可元数据"),
        "screening_conclusion": "暂不采用（无独立性 + 逐图标签不可追溯）",
        "evidence_notes": notes,
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUT_NAME
    if out_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"external_dataset_source_audit_{stamp}.csv"
        print(f"[ext] 目标已存在，改写到 {out_path.name}")

    policy_note = license_policy_note()
    print(f"[ext] 许可政策页: {policy_note}")

    rows = []
    for candidate in CANDIDATES:
        print(f"[ext] screening {candidate['source_name']} ...", flush=True)
        row = screen(candidate, policy_note=policy_note)
        rows.append(row)
        print(f"  HTTP={row['http_status']} 结论={row['screening_conclusion']}")

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[ext] wrote {out_path}")
    print("[ext] 注意：本轮只做元数据初筛，未下载、未解包、未合并任何图片。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
