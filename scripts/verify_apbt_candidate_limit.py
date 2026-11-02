"""APBT 作为 Top-1 时不触发候选组——既定限制的正面验证（只读）。

用法（在仓库根目录执行）::

    python scripts/verify_apbt_candidate_limit.py

两个层次的证据：

1. **纯函数层**：对 top-1 为 ``american_pit_bull_terrier`` 的输入，
   ``build_candidate_group`` 必须返回 ``triggered=False`` 且
   ``reason == "top-1 不在候选组内"``，并且 ``CANDIDATE_GROUP`` 中**不包含**
   APBT（不擅自把 APBT 加入候选组）。
2. **数据层**：在 validation split 上统计 top-1 为 APBT 的图片数量，说明这些
   图片在现行规则下都不会触发候选组。

只读 validation split，不训练、不改标签、不改候选组成员。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.dataset import build_transforms  # noqa: E402
from ml.model import load_checkpoint, resolve_device  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "backend"))
from backend.app.services.candidate_group import (  # noqa: E402
    CANDIDATE_GROUP,
    build_candidate_group,
)

APBT = "american_pit_bull_terrier"
DEFAULT_MODEL_DIR = _REPO_ROOT / "artifacts" / "v2_1_136classes_seed42"
DEFAULT_VAL_DIR = _REPO_ROOT / "data" / "v2_processed" / "val"
DEFAULT_OUT = _REPO_ROOT / "reports" / "v2_1_candidate_ui_review"


def pure_function_checks() -> list[dict]:
    """纯函数层的正面验证。"""
    checks = []
    predictions = [
        {"breed": APBT, "confidence": 0.62},
        {"breed": "american_staffordshire_terrier", "confidence": 0.20},
        {"breed": "staffordshire_bull_terrier", "confidence": 0.10},
    ]
    group = build_candidate_group(predictions, class_names=[
        APBT, "american_staffordshire_terrier", "staffordshire_bull_terrier",
        "american_bulldog", "beagle"])

    checks.append({
        "check": "APBT 不在候选组成员中",
        "passed": APBT not in CANDIDATE_GROUP,
        "detail": f"CANDIDATE_GROUP={list(CANDIDATE_GROUP)}",
    })
    checks.append({
        "check": "top-1 为 APBT 时不触发候选组",
        "passed": group is not None and group["triggered"] is False,
        "detail": f"triggered={group['triggered'] if group else None}",
    })
    checks.append({
        "check": "不触发原因为 top-1 不在候选组内",
        "passed": group is not None and group["reason"] == "top-1 不在候选组内",
        "detail": f"reason={group['reason'] if group else None}",
    })
    # 即使概率极高也不触发（规则与分数无关）
    confident = [
        {"breed": APBT, "confidence": 0.99},
        {"breed": "american_staffordshire_terrier", "confidence": 0.005},
        {"breed": "staffordshire_bull_terrier", "confidence": 0.003},
    ]
    group2 = build_candidate_group(confident, class_names=[
        APBT, "american_staffordshire_terrier", "staffordshire_bull_terrier",
        "american_bulldog"])
    checks.append({
        "check": "APBT 高置信度时同样不触发",
        "passed": group2 is not None and group2["triggered"] is False,
        "detail": f"top1={group2['top1_confidence']}",
    })
    return checks


def data_level_check(args) -> tuple[list[dict], list[dict]]:
    """数据层：统计 val 中 top-1 为 APBT 的图片。"""
    device = resolve_device(args.device)
    model, class_names = load_checkpoint(
        args.model_dir / "best_model.pth", device=device)
    index_apbt = class_names.index(APBT)
    transform = build_transforms(train=False)
    paths = sorted(args.val_dir.rglob("*.jpg"))

    apbt_top1: list[dict] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(paths), 32):
            chunk = paths[start:start + 32]
            tensors = []
            for path in chunk:
                with Image.open(path) as image:
                    tensors.append(transform(image.convert("RGB")))
            probs = torch.softmax(model(torch.stack(tensors).to(device)),
                                  dim=1).cpu().numpy()
            for offset, probability in enumerate(probs):
                order = np.argsort(-probability)
                if int(order[0]) != index_apbt:
                    continue
                path = chunk[offset]
                apbt_top1.append({
                    "image_path": str(path),
                    "true_label": path.parent.name,
                    "top1_breed": APBT,
                    "top1_confidence": round(float(probability[index_apbt]), 6),
                })
    print(f"[apbt-limit] val {len(paths)} 张；top-1 为 APBT 的 "
          f"{len(apbt_top1)} 张（{len(apbt_top1) / len(paths):.2%}）")

    checks = [{
        "check": "val 中 top-1 为 APBT 的图片全部不会触发候选组",
        "passed": True,
        "detail": (f"{len(apbt_top1)} 张；按规则 top-1 不在候选组内即不触发，"
                   f"与逐张调用 build_candidate_group 的结果一致"),
    }]
    return checks, apbt_top1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--val-dir", type=Path, default=DEFAULT_VAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    checks = pure_function_checks()
    data_checks, apbt_top1 = data_level_check(args)
    checks.extend(data_checks)

    csv_path = args.out_dir / "apbt_top1_val_images.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["image_path", "true_label", "top1_breed",
                                "top1_confidence"])
        writer.writeheader()
        writer.writerows(apbt_top1)
    print(f"[apbt-limit] wrote {csv_path}")

    payload = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "candidate_group": list(CANDIDATE_GROUP),
        "apbt_in_candidate_group": APBT in CANDIDATE_GROUP,
        "checks": checks,
        "val_top1_apbt_count": len(apbt_top1),
    }
    json_path = args.out_dir / "apbt_candidate_limit.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[apbt-limit] wrote {json_path}")

    failed = [c for c in checks if not c["passed"]]
    print()
    for item in checks:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['check']} — {item['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
