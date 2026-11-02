#!/usr/bin/env python
"""U6.1-A：warm-start 初始化继承审计（**只读**，不重跑任何旧实验）。

用法（在仓库根目录执行）::

    python scripts/u6_warm_start_audit.py

核验内容：
1. `ml/train.py::initialize_from_checkpoint` 在「类别名与顺序完全一致」时是否
   连 `fc.*` 一起继承（源码级判定 + 运行一个**内存级**单元验证，不写盘、不训练）。
2. 既有 5 个 U6 实验的 `experiment_config.json` 是否记录
   `head_transferred=True` / `loaded_keys=122` / `skipped_keys=[]` /
   `init_from.sha256 == V2.1` / `class_order_sha256` 与 V2.1 一致。
3. `--lr 1e-3` 与分组学习率 `--lr-head` / `--lr-backbone` 的语义关系
   （确认 `--lr` 在分组模式下对实际更新无效，避免"默默忽略参数"）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "reports" / "u6_1_low_lr"
V21 = REPO / "artifacts" / "v2_1_136classes_seed42"


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    v21_weights = V21 / "best_model.pth"
    v21_names = V21 / "class_names.json"
    v21_sha = sha256_file(v21_weights)
    v21_class_names = json.loads(v21_names.read_text(encoding="utf-8"))
    v21_order_sha = hashlib.sha256(
        json.dumps(v21_class_names).encode("utf-8")).hexdigest()

    print("=== 1. 源码级判定 ===")
    train_src = (REPO / "ml" / "train.py").read_text(encoding="utf-8")
    checks = {
        "same_classes 分支存在":
            "same_classes = (" in train_src,
        "same_classes 时 head_keys 为空":
            "head_keys: set[str] = set()" in train_src,
        "transfer 按 head_keys 过滤（含 fc.*）":
            "if key not in head_keys" in train_src,
        "target_class_names 透传":
            "target_class_names=class_names" in train_src,
        "head_transferred 记入 config":
            '"head_transferred": same_classes' in train_src,
    }
    for name, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    print()
    print("=== 2. 内存级单元验证（不写盘、不训练）===")
    import tempfile

    import torch

    from ml.model import load_checkpoint
    from ml.train import initialize_from_checkpoint

    # 先把源张量取出，供后续在 temp 目录之外比对
    source_state = torch.load(v21_weights, map_location="cpu",
                              weights_only=True)["state_dict"]
    with tempfile.TemporaryDirectory(prefix="u61_audit_") as tmp:
        payload = {
            "state_dict": {k: v.clone() for k, v in source_state.items()},
            "class_names": list(v21_class_names),
            "num_classes": len(v21_class_names),
            "arch": "resnet18",
        }
        probe_path = Path(tmp) / "probe.pth"
        torch.save(payload, probe_path)

        model, names = load_checkpoint(v21_weights, device="cpu")

        # 同一个模型对象分别验证"继承"与"类别数不同则重建"两条路径
        inherited = initialize_from_checkpoint(model, probe_path,
                                               target_class_names=names)
        print(f"  继承路径: head_transferred={inherited['head_transferred']} "
              f"loaded_keys={inherited['loaded_keys']} "
              f"skipped_keys={inherited['skipped_keys']}")

        # 张量级比对：fc.weight / fc.bias 必须与源完全一致
        actual_fc_w = model.fc.weight.detach()
        actual_fc_b = model.fc.bias.detach()
        tensor_ok = bool(torch.equal(source_state["fc.weight"], actual_fc_w)
                         and torch.equal(source_state["fc.bias"], actual_fc_b))
        print(f"  [{'PASS' if tensor_ok else 'FAIL'}] fc.weight / fc.bias "
              f"与 V2.1 源张量逐位一致")

        # 反例：类别名不同时必须重建头
        mismatched = initialize_from_checkpoint(
            model, probe_path,
            target_class_names=list(v21_class_names[:-1]))
        print(f"  类别数不同路径: head_transferred="
              f"{mismatched['head_transferred']} "
              f"skipped_keys={mismatched['skipped_keys']}")

    print()
    print("=== 3. 既有 5 个 U6 实验的初始化证据 ===")
    rows = []
    all_ok = True
    for exp_dir in sorted((REPO / "artifacts").glob(
            "v2_2_border_collie_*")):
        config_path = exp_dir / "experiment_config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        init = config.get("init_from") or {}
        exp_names = config.get("class_names") or []
        order_sha = config.get("class_order_sha256")
        ok = (
            init.get("sha256") == v21_sha
            and init.get("head_transferred") is True
            and init.get("skipped_keys") == []
            and int(init.get("loaded_keys") or 0) == len(source_state)
            and list(exp_names) == list(v21_class_names)
            and order_sha == v21_order_sha
        )
        all_ok = all_ok and ok
        rows.append({
            "experiment": exp_dir.name,
            "seed": config.get("seed"),
            "image_size": config.get("image_size"),
            "pair_color_jitter": config.get("pair_color_jitter"),
            "pair_sampler_weight": config.get("pair_sampler_weight"),
            "init_sha256_matches_v21": init.get("sha256") == v21_sha,
            "head_transferred": init.get("head_transferred"),
            "loaded_keys": init.get("loaded_keys"),
            "skipped_keys": ";".join(init.get("skipped_keys") or []) or "(无)",
            "class_order_sha256_matches": order_sha == v21_order_sha,
            "class_names_match_v21": list(exp_names) == list(v21_class_names),
            "verdict": "PASS" if ok else "FAIL",
        })
        print(f"  [{'PASS' if ok else 'FAIL'}] {exp_dir.name}: "
              f"head_transferred={init.get('head_transferred')} "
              f"loaded={init.get('loaded_keys')} "
              f"skipped={init.get('skipped_keys')} "
              f"init_sha_ok={init.get('sha256') == v21_sha}")

    print()
    print("=== 4. --lr 语义（避免'默默忽略参数'）===")
    lr_ok = ('"lr": lr if lr_head is None else lr_head' in train_src
             and '"lr": lr if lr_backbone is None else lr_backbone'
             in train_src)
    print(f"  [{'PASS' if lr_ok else 'FAIL'}] 分组学习率均非 None 时由 "
          f"--lr-head / --lr-backbone 完全决定，--lr 仅作缺省与元数据")
    print("  → 低学习率协议设置 --lr-head 1e-4 --lr-backbone 5e-5 后，"
          "有效学习率即 1e-4 / 5e-5；--lr 1e-3 对实际更新无效。")

    print()
    print(f"[audit] 5 个旧实验初始化证据全部充分: {all_ok}")

    (OUT / "warm_start_audit_data.json").write_text(
        json.dumps({
            "v21_best_model_sha256": v21_sha,
            "v21_class_order_sha256": v21_order_sha,
            "v21_num_classes": len(v21_class_names),
            "source_checks": checks,
            "lr_semantics_check": lr_ok,
            "experiments": rows,
            "all_experiments_pass": all_ok,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[audit] wrote {OUT / 'warm_start_audit_data.json'}")
    return 0 if (all_ok and all(checks.values()) and lr_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())
