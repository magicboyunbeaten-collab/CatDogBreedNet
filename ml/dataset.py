"""Dataset loading and transforms for the cat/dog breed classifier.

Train, validation, test and online inference all share the normalization
constants from ``ml.config`` so that training and inference preprocessing
stay consistent (CODEBUDDY.md sections 5.4 and 6.4).

Layout expected under ``data/processed``::

    train/<Breed>/*.jpg
    val/<Breed>/*.jpg
    test/<Breed>/*.jpg
"""
from __future__ import annotations

from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import ImageFolder

from ml.config import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    IMAGE_SIZE,
    PROCESSED_DATA_DIR,
)

SPLITS = ("train", "val", "test")


def build_transforms(image_size: int = IMAGE_SIZE, train: bool = False):
    """Return the transform pipeline for a split.

    ``train=True``  -> moderate augmentation: RandomResizedCrop + horizontal
                       flip + slight rotation (CODEBUDDY.md 5.4).
    ``train=False`` -> deterministic eval/inference pipeline: Resize(256) +
                       CenterCrop(224). Both paths end with the same ImageNet
                       normalization used by the ResNet18 pretrained weights.
    """
    normalize = transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    if train:
        return transforms.Compose([
            transforms.RandomResizedCrop(image_size, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(10),
            transforms.ToTensor(),
            normalize,
        ])
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(image_size),
        transforms.ToTensor(),
        normalize,
    ])


def class_names_from_class_to_idx(class_to_idx: dict[str, int]) -> list[str]:
    """Return class names ordered by their index (ImageFolder convention)."""
    return [name for name, _ in sorted(class_to_idx.items(), key=lambda kv: kv[1])]


def build_datasets(processed_dir: Path = PROCESSED_DATA_DIR):
    """Build train/val/test ``ImageFolder`` datasets.

    Raises ``FileNotFoundError`` with setup instructions when a split
    directory is missing, and ``ValueError`` when the class-to-index
    mappings differ between splits.
    """
    processed_dir = Path(processed_dir)
    for split in SPLITS:
        split_dir = processed_dir / split
        if not split_dir.is_dir():
            raise FileNotFoundError(
                f"missing data directory: {split_dir}. "
                f"Run 'python scripts/prepare_dataset.py download' and "
                f"'python scripts/prepare_dataset.py build' first.")

    train_ds = ImageFolder(root=str(processed_dir / "train"),
                           transform=build_transforms(train=True))
    val_ds = ImageFolder(root=str(processed_dir / "val"),
                         transform=build_transforms(train=False))
    test_ds = ImageFolder(root=str(processed_dir / "test"),
                          transform=build_transforms(train=False))

    if not (train_ds.class_to_idx == val_ds.class_to_idx == test_ds.class_to_idx):
        raise ValueError(
            "class_to_idx mismatch between splits: "
            f"train={train_ds.class_to_idx}, val={val_ds.class_to_idx}, "
            f"test={test_ds.class_to_idx}. Rebuild the dataset with "
            "'python scripts/prepare_dataset.py build'.")
    return train_ds, val_ds, test_ds


def build_dataloaders(
    processed_dir: Path = PROCESSED_DATA_DIR,
    batch_size: int = 32,
    num_workers: int = 0,
    pin_memory: bool | None = None,
) -> tuple[dict[str, DataLoader], list[str]]:
    """Build dataloaders for all splits plus the ordered class names.

    ``num_workers`` defaults to 0 so the pipeline runs on Windows without
    multiprocessing issues (CODEBUDDY.md section 3). ``pin_memory`` defaults
    to True only when CUDA is available.
    """
    train_ds, val_ds, test_ds = build_datasets(processed_dir)
    if pin_memory is None:
        pin_memory = torch.cuda.is_available()

    loaders = {
        "train": DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                            num_workers=num_workers, pin_memory=pin_memory),
        "val": DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                          num_workers=num_workers, pin_memory=pin_memory),
        "test": DataLoader(test_ds, batch_size=batch_size, shuffle=False,
                           num_workers=num_workers, pin_memory=pin_memory),
    }
    class_names = class_names_from_class_to_idx(train_ds.class_to_idx)
    return loaders, class_names
