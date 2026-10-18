#!/usr/bin/env python
"""Train the ResNet18 baseline on the Oxford-IIIT Pet Dataset.

Usage (from the repository root):

    python -m ml.train                       # full run with defaults
    python -m ml.train --epochs 1            # quick smoke test
    python -m ml.train --batch-size 16       # reduce VRAM usage

Artifacts written by a run:
    artifacts/best_model.pth          best weights (by validation accuracy)
    artifacts/last_model.pth          weights of the final epoch
    artifacts/class_names.json        ordered class names (train set order)
    artifacts/experiment_config.json  full hyper-parameters and environment
    reports/train_log.csv             per-epoch train/val loss, accuracy, lr
    reports/loss_curve.png            loss curves
    reports/accuracy_curve.png        accuracy curves
"""
from __future__ import annotations

import argparse
import csv
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a plain script: python ml/train.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import numpy as np  # noqa: E402
import torchvision  # noqa: E402

# 训练脚本在无 GUI 环境运行：显式使用无头后端，避免加载 TkAgg 失败。
import matplotlib  # noqa: E402

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from torch.optim import AdamW  # noqa: E402
from torch.optim.lr_scheduler import StepLR  # noqa: E402

from ml.config import (  # noqa: E402
    ARTIFACTS_DIR,
    IMAGE_SIZE,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    SEED,
    VAL_RATIO,
)
from ml.dataset import AUGMENT_PRESETS, build_dataloaders  # noqa: E402
from ml.model import (  # noqa: E402
    ARCH,
    PRETRAINED_WEIGHTS,
    SUPPORTED_ARCHS,
    build_model,
    resolve_device,
    save_checkpoint,
    save_class_names,
    set_seed,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a ResNet18 cat/dog breed classifier.")
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DATA_DIR,
                        help="ImageFolder root with train/val/test subdirs")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--step-size", type=int, default=5,
                        help="StepLR decay period in epochs")
    parser.add_argument("--gamma", type=float, default=0.1,
                        help="StepLR decay factor")
    parser.add_argument("--patience", type=int, default=3,
                        help="early-stopping patience in epochs (0 disables)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--device", default="auto",
                        choices=["auto", "cpu", "cuda"])
    parser.add_argument("--num-workers", type=int, default=0,
                        help="DataLoader workers; 0 is the safe default on Windows")
    parser.add_argument("--limit-train", type=int, default=None,
                        help="use only the first N training samples (debugging)")
    parser.add_argument("--limit-val", type=int, default=None,
                        help="use only the first N validation samples (debugging)")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--arch", default=ARCH, choices=sorted(SUPPORTED_ARCHS),
                        help="backbone architecture (A4 experiment)")
    parser.add_argument("--augment", default="baseline",
                        choices=list(AUGMENT_PRESETS),
                        help="training augmentation preset (A2 experiment)")
    parser.add_argument("--freeze-strategy", default="none",
                        choices=["none", "layer4", "head"],
                        help="which modules stay trainable (A3 experiment): "
                             "none=full fine-tune (baseline), "
                             "layer4=last backbone stage + head, "
                             "head=classifier only")
    parser.add_argument("--lr-head", type=float, default=None,
                        help="learning rate for the classification head; "
                             "enables per-group learning rates")
    parser.add_argument("--lr-backbone", type=float, default=None,
                        help="learning rate for the backbone; "
                             "enables per-group learning rates")
    parser.add_argument("--label-smoothing", type=float, default=0.0,
                        help="label smoothing factor (0 disables, baseline)")
    parser.add_argument("--mixup-alpha", type=float, default=0.0,
                        help="Mixup Beta(alpha, alpha); 0 disables (baseline)")
    return parser.parse_args(argv)


def _subset_loader(loader, limit, shuffle):
    dataset = loader.dataset
    dataset.samples = dataset.samples[:limit]
    dataset.imgs = dataset.samples  # torchvision ImageFolder mirrors this list
    return torch.utils.data.DataLoader(
        dataset, batch_size=loader.batch_size, shuffle=shuffle,
        num_workers=loader.num_workers)


FREEZE_STRATEGIES = ("none", "layer4", "head")

#: 人类可读的增强描述，写入 experiment_config.json 以便复现。
AUGMENT_DESCRIPTIONS = {
    "baseline": ("RandomResizedCrop(224, scale=(0.8,1.0)) + "
                 "RandomHorizontalFlip(0.5) + RandomRotation(10)"),
    "+colorjitter": ("ColorJitter(0.2,0.2,0.2) + RandomResizedCrop(224, "
                     "scale=(0.8,1.0)) + RandomHorizontalFlip(0.5) + "
                     "RandomRotation(10)"),
    "+randomerasing": ("RandomResizedCrop(224, scale=(0.8,1.0)) + "
                       "RandomHorizontalFlip(0.5) + RandomRotation(10) + "
                       "RandomErasing(p=0.25)"),
}


def _head_module_names(arch: str) -> set[str]:
    """Top-level module names that form the classification head."""
    return {"fc"} if arch.startswith("resnet") else {"classifier"}


def apply_freeze_strategy(model: nn.Module, arch: str,
                          strategy: str = "none") -> str:
    """Freeze parameters and return a human-readable description.

    * ``"none"``   -- every parameter trainable (baseline, unchanged).
    * ``"head"``   -- only the classification head is trainable.
    * ``"layer4"`` -- the last backbone stage plus the head are trainable
      (ResNet: ``layer4`` + ``fc``; ConvNeXt/EfficientNet: the final block of
      ``features`` + ``classifier``).

    The returned description is recorded in ``experiment_config.json`` so the
    exact trainable parameter count is reproducible.
    """
    if strategy not in FREEZE_STRATEGIES:
        raise ValueError(
            f"unknown freeze strategy '{strategy}'; expected one of "
            f"{list(FREEZE_STRATEGIES)}")
    if strategy == "none":
        for param in model.parameters():
            param.requires_grad = True
        return "all parameters trainable"

    for param in model.parameters():
        param.requires_grad = False

    head_names = _head_module_names(arch)
    unfrozen: list[str] = []
    for name, module in model.named_children():
        if name in head_names:
            unfrozen.append(name)
            for param in module.parameters():
                param.requires_grad = True

    if strategy == "layer4":
        if arch.startswith("resnet"):
            for name, module in model.named_children():
                if name == "layer4":
                    unfrozen.append(name)
                    for param in module.parameters():
                        param.requires_grad = True
        else:
            # ConvNeXt/EfficientNet 把主干放在单个 features Sequential 中，
            # 解冻其最后一个子块（最后一级）作为 layer4 的对应物。
            last_block = list(model.features.children())[-1]
            unfrozen.append("features[-1]")
            for param in last_block.parameters():
                param.requires_grad = True

    if not unfrozen:
        raise ValueError(
            f"arch '{arch}' exposes no head module among {sorted(head_names)}; "
            f"cannot apply freeze strategy '{strategy}'")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return (f"trainable modules={sorted(unfrozen)}; "
            f"trainable params {trainable}/{total} ({trainable / total:.1%})")


def _split_head_backbone_params(model: nn.Module, arch: str):
    """Split parameters into (head, backbone) by top-level module name."""
    head_names = _head_module_names(arch)
    head, backbone = [], []
    for name, module in model.named_children():
        params = [p for p in module.parameters() if p.requires_grad]
        (head if name in head_names else backbone).extend(params)
    return head, backbone


def build_optimizer(model: nn.Module, arch: str, lr: float,
                    weight_decay: float, lr_head: float | None = None,
                    lr_backbone: float | None = None) -> AdamW:
    """Build AdamW, optionally with separate head/backbone learning rates.

    When both ``lr_head`` and ``lr_backbone`` are ``None`` the behaviour is
    identical to the baseline single-group optimizer.
    """
    if lr_head is None and lr_backbone is None:
        return AdamW([p for p in model.parameters() if p.requires_grad],
                     lr=lr, weight_decay=weight_decay)

    head_params, backbone_params = _split_head_backbone_params(model, arch)
    groups = []
    if head_params:
        groups.append({"params": head_params, "name": "head",
                       "lr": lr if lr_head is None else lr_head})
    if backbone_params:
        groups.append({"params": backbone_params, "name": "backbone",
                       "lr": lr if lr_backbone is None else lr_backbone})
    if not groups:
        raise ValueError(
            "no trainable parameters for per-group optimizer; check "
            "--freeze-strategy")
    return AdamW(groups, lr=lr, weight_decay=weight_decay)


def train_one_epoch(model, loader, criterion, optimizer, device,
                    mixup_alpha: float = 0.0):
    """Run one training epoch; return (avg_loss, accuracy).

    When ``mixup_alpha > 0`` each batch is mixed with a shuffled copy using
    ``lam ~ Beta(alpha, alpha)`` (clipped so ``lam >= 0.5``) and the loss uses
    both labels. The reported accuracy is measured against the dominant label,
    which is only meaningful as a rough progress signal while Mixup is on.
    """
    model.train()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        if mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            lam = max(lam, 1.0 - lam)
            shuffled = torch.randperm(images.size(0), device=device)
            mixed = lam * images + (1.0 - lam) * images[shuffled]
            logits = model(mixed)
            loss = (lam * criterion(logits, labels)
                    + (1.0 - lam) * criterion(logits, labels[shuffled]))
        else:
            logits = model(images)
            loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * labels.size(0)
        total_correct += (logits.argmax(dim=1) == labels).sum().item()
        total_samples += labels.size(0)
    return total_loss / total_samples, total_correct / total_samples


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    """Evaluate on a loader; return (avg_loss, accuracy)."""
    model.eval()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        logits = model(images)
        loss = criterion(logits, labels)
        total_loss += loss.item() * labels.size(0)
        total_correct += (logits.argmax(dim=1) == labels).sum().item()
        total_samples += labels.size(0)
    return total_loss / total_samples, total_correct / total_samples


def save_curves(rows: list[dict], reports_dir: Path) -> None:
    """Save loss and accuracy curves from the training log rows."""
    epochs = [r["epoch"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(epochs, [r["train_loss"] for r in rows], marker="o", label="train")
    ax.plot(epochs, [r["val_loss"] for r in rows], marker="s", label="val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("ResNet18 baseline - loss")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(reports_dir / "loss_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(epochs, [r["train_acc"] for r in rows], marker="o", label="train")
    ax.plot(epochs, [r["val_acc"] for r in rows], marker="s", label="val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("accuracy")
    ax.set_title("ResNet18 baseline - accuracy")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(reports_dir / "accuracy_curve.png", dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    started_at = datetime.now(timezone.utc).isoformat()

    set_seed(args.seed)
    device = resolve_device(args.device)

    loaders, class_names = build_dataloaders(
        processed_dir=args.data_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        augment=args.augment,
    )
    train_loader, val_loader = loaders["train"], loaders["val"]
    if args.limit_train is not None:
        train_loader = _subset_loader(train_loader, args.limit_train, shuffle=True)
    if args.limit_val is not None:
        val_loader = _subset_loader(val_loader, args.limit_val, shuffle=False)

    num_classes = len(class_names)
    print(f"[train] device={device} arch={args.arch} classes={num_classes} "
          f"augment={args.augment} freeze={args.freeze_strategy} "
          f"mixup_alpha={args.mixup_alpha} "
          f"label_smoothing={args.label_smoothing} "
          f"train={len(train_loader.dataset)} val={len(val_loader.dataset)} "
          f"test={len(loaders['test'].dataset)}")
    if device.type == "cuda":
        print(f"[train] gpu={torch.cuda.get_device_name(device)} "
              f"vram={torch.cuda.get_device_properties(device).total_memory / 1024**3:.1f} GiB")

    model = build_model(arch=args.arch, num_classes=num_classes,
                        pretrained=True).to(device)
    freeze_description = apply_freeze_strategy(
        model, args.arch, args.freeze_strategy)
    print(f"[train] freeze strategy '{args.freeze_strategy}': "
          f"{freeze_description}")
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = build_optimizer(
        model, arch=args.arch, lr=args.lr, weight_decay=args.weight_decay,
        lr_head=args.lr_head, lr_backbone=args.lr_backbone)
    scheduler = StepLR(optimizer, step_size=args.step_size, gamma=args.gamma)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    best_val_acc = -1.0
    best_epoch = -1
    epochs_without_improvement = 0

    try:
        for epoch in range(1, args.epochs + 1):
            epoch_started = time.time()
            train_loss, train_acc = train_one_epoch(
                model, train_loader, criterion, optimizer, device,
                mixup_alpha=args.mixup_alpha)
            val_loss, val_acc = evaluate(model, val_loader, criterion, device)
            scheduler.step()
            epoch_seconds = time.time() - epoch_started

            row = {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "train_acc": round(train_acc, 6),
                "val_loss": round(val_loss, 6),
                "val_acc": round(val_acc, 6),
                "lr": scheduler.get_last_lr()[0],
                "epoch_seconds": round(epoch_seconds, 2),
            }
            rows.append(row)
            print(f"[epoch {epoch:>3}/{args.epochs}] "
                  f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
                  f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} "
                  f"lr={row['lr']:.2e} ({epoch_seconds:.1f}s)", flush=True)

            # Keep the latest weights every epoch; best weights by val accuracy.
            # ``arch`` must be passed explicitly: save_checkpoint defaults to
            # the baseline resnet18, which would mislabel non-resnet18
            # checkpoints and break load_checkpoint's architecture dispatch.
            save_checkpoint(model, args.output_dir / "last_model.pth",
                            class_names, arch=args.arch,
                            extra={"epoch": epoch})
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_epoch = epoch
                epochs_without_improvement = 0
                save_checkpoint(model, args.output_dir / "best_model.pth",
                                class_names, arch=args.arch,
                                extra={"epoch": epoch, "val_acc": val_acc})
                print(f"[train] new best val_acc={val_acc:.4f} at epoch {epoch}; "
                      f"saved best_model.pth", flush=True)
            else:
                epochs_without_improvement += 1

            if args.patience and epochs_without_improvement >= args.patience:
                print(f"[train] early stopping: no val_acc improvement for "
                      f"{epochs_without_improvement} epochs")
                break
    except torch.cuda.OutOfMemoryError:
        print("[train] CUDA out of memory. Suggestions: reduce --batch-size "
              "(e.g. 16 or 8), close other GPU applications, or retry with "
              "--device cpu.", file=sys.stderr)
        raise

    if not rows:
        print("[train] no epochs completed", file=sys.stderr)
        return 1

    save_class_names(class_names, args.output_dir / "class_names.json")

    log_path = args.reports_dir / "train_log.csv"
    with log_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    save_curves(rows, args.reports_dir)

    experiment_config = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_seconds": round(time.time() - started, 2),
        "arch": args.arch,
        "pretrained_weights": PRETRAINED_WEIGHTS,
        "fine_tuning": freeze_description,
        "freeze_strategy": args.freeze_strategy,
        "augment_preset": args.augment,
        "num_classes": num_classes,
        "seed": args.seed,
        "epochs_requested": args.epochs,
        "epochs_completed": len(rows),
        "best_epoch": best_epoch,
        "best_val_acc": best_val_acc,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "lr_head": args.lr_head,
        "lr_backbone": args.lr_backbone,
        "weight_decay": args.weight_decay,
        "optimizer": (
            "AdamW (per-group lr: head/backbone)"
            if (args.lr_head is not None or args.lr_backbone is not None)
            else "AdamW"),
        "scheduler": f"StepLR(step_size={args.step_size}, gamma={args.gamma})",
        "loss": ("CrossEntropyLoss"
                 + (f"(label_smoothing={args.label_smoothing})"
                    if args.label_smoothing else "")),
        "mixup_alpha": args.mixup_alpha,
        "early_stopping_patience": args.patience,
        "image_size": IMAGE_SIZE,
        "train_augmentation": AUGMENT_DESCRIPTIONS[args.augment],
        "eval_transform": "Resize(256) + CenterCrop(224) + Normalize(ImageNet)",
        "normalization": "ImageNet mean/std",
        "data_dir": str(args.data_dir),
        "dataset_split_policy": (
            "test = official test split; train/val = official trainval split "
            f"stratified per class, seed={SEED}, val_ratio={VAL_RATIO}"),
        "dataset_sizes": {
            "train": len(loaders["train"].dataset),
            "val": len(loaders["val"].dataset),
            "test": len(loaders["test"].dataset),
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": str(device),
            "gpu": (torch.cuda.get_device_name(device)
                    if device.type == "cuda" else None),
            "platform": platform.platform(),
        },
    }
    config_path = args.output_dir / "experiment_config.json"
    config_path.write_text(
        __import__("json").dumps(experiment_config, indent=2, ensure_ascii=False),
        encoding="utf-8")

    print(f"[train] done in {time.time() - started:.1f}s; "
          f"best_val_acc={best_val_acc:.4f} (epoch {best_epoch})")
    print(f"[train] artifacts: {args.output_dir}/ "
          f"(best_model.pth, last_model.pth, class_names.json, experiment_config.json)")
    print(f"[train] reports: {log_path}, loss_curve.png, accuracy_curve.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
