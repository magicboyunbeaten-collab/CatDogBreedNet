"""U6-C：**仅对目标两类生效**的训练期增强与采样工具。

背景
----
``ml/dataset.py`` 的 ``AUGMENT_PRESETS`` 是**全类别**增强（例如 ``+colorjitter``
会给所有 136 类都加颜色扰动）。U6 的诊断只指向 ``collie`` / ``border_collie``
两类，因此需要"只影响这两类"的通道，避免把无关类别也一起搅动。

设计约束
--------
* **不修改** ``ml/dataset.py`` 的既有 preset 语义；本模块是独立包装层。
* 增强**只在训练 DataLoader 内即时生效**，不落盘任何增强图像。
* 默认不启用（``--pair-color-jitter`` 关闭、``--pair-sampler-weight`` 为 1.0），
  因此默认训练行为与 V2.1 完全一致。

本模块只被 ``ml/train.py`` 按需导入；导入本模块本身不会改变任何全局状态。
"""
from __future__ import annotations

from typing import Iterable, Sequence

import torch
from PIL import Image
from torch.utils.data import Dataset, WeightedRandomSampler
from torchvision import transforms

#: 本任务的目标两类（与 reports/u6_border_collie 中 TARGETS 保持一致）。
PAIR_LABELS: tuple[str, ...] = ("collie", "border_collie")

#: 保守的默认颜色扰动参数（brightness, contrast, saturation, hue）。
#: 刻意温和：避免破坏貂色/陨石色/三色等本身有判别价值的外观特征。
DEFAULT_PAIR_JITTER = (0.2, 0.2, 0.3, 0.05)


def parse_jitter(spec: str | None) -> tuple[float, float, float, float]:
    """把 ``"b,c,s,h"`` 解析成四元组；``None`` 或空串返回默认值。"""
    if not spec:
        return DEFAULT_PAIR_JITTER
    parts = [item.strip() for item in spec.split(",") if item.strip()]
    if len(parts) != 4:
        raise ValueError(
            f"pair color jitter expects 'brightness,contrast,saturation,hue', "
            f"got {spec!r}")
    return tuple(float(value) for value in parts)  # type: ignore[return-value]


class PairColorJitterDataset(Dataset):
    """仅当样本类别属于 ``PAIR_LABELS`` 时追加温和 ``ColorJitter`` 的数据集。

    参数
    ----
    base:
        原始的 ``ImageFolder``。只借用它的 ``samples``（路径 + 类别索引）与
        ``class_to_idx``，**不调用**它自带的 transform（避免变换顺序错乱）。
    class_names:
        与 ``base.class_to_idx`` 对应的有序类别名。
    transform:
        本该由 ``ImageFolder`` 应用的训练变换（在 jitter 之后执行）。
    jitter:
        ``(brightness, contrast, saturation, hue)``。
    """

    def __init__(self, base: Dataset, class_names: Sequence[str],
                 transform, jitter: tuple[float, float, float, float]) -> None:
        if not hasattr(base, "samples"):
            raise TypeError("base dataset must expose .samples (ImageFolder)")
        self.base = base
        self.samples = list(base.samples)
        self.transform = transform
        name_to_index = {name: index for index, name in
                         enumerate(class_names)}
        missing = [label for label in PAIR_LABELS if label not in name_to_index]
        if missing:
            raise ValueError(
                f"pair labels absent from class_names: {missing}. "
                f"U6 pair-only augmentation needs both target classes.")
        self.pair_indices = {name_to_index[label] for label in PAIR_LABELS}
        self.jitter = transforms.ColorJitter(
            brightness=jitter[0], contrast=jitter[1],
            saturation=jitter[2], hue=jitter[3])
        self.pair_sample_count = sum(
            1 for _, label in self.samples if label in self.pair_indices)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        path, label = self.samples[index]
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            if label in self.pair_indices:
                rgb = self.jitter(rgb)
            tensor = self.transform(rgb)
        return tensor, label


def make_pair_weighted_sampler(base: Dataset, class_names: Sequence[str],
                               pair_weight: float, seed: int = 42,
                               num_samples: int | None = None
                               ) -> WeightedRandomSampler:
    """目标两类样本权重乘 ``pair_weight``（其余类保持 1.0）。

    ``pair_weight <= 1.0`` 时抛错——调用方应完全跳过加权，保持基线行为。
    """
    if pair_weight <= 1.0:
        raise ValueError(
            f"pair_weight must be > 1.0 to enable sampling, got {pair_weight}")
    if not hasattr(base, "samples"):
        raise TypeError("base dataset must expose .samples (ImageFolder)")

    name_to_index = {name: index for index, name in enumerate(class_names)}
    missing = [label for label in PAIR_LABELS if label not in name_to_index]
    if missing:
        raise ValueError(f"pair labels absent from class_names: {missing}")
    pair_indices = {name_to_index[label] for label in PAIR_LABELS}

    weights = torch.ones(len(base.samples), dtype=torch.double)
    for index, (_, label) in enumerate(base.samples):
        if label in pair_indices:
            weights[index] = float(pair_weight)

    generator = torch.Generator()
    generator.manual_seed(seed)
    return WeightedRandomSampler(
        weights=weights,
        num_samples=num_samples or len(base.samples),
        replacement=True,
        generator=generator,
    )


def pair_sample_share(dataset: Dataset, class_names: Sequence[str]) -> float:
    """目标两类在训练集中的样本占比（用于日志与配置记录）。"""
    samples = getattr(dataset, "samples", None)
    if samples is None:
        return float("nan")
    name_to_index = {name: index for index, name in enumerate(class_names)}
    pair_indices = {name_to_index[label] for label in PAIR_LABELS
                    if label in name_to_index}
    if not samples:
        return float("nan")
    return sum(1 for _, label in samples if label in pair_indices) / len(samples)


def describe(iterable: Iterable[str]) -> str:
    """小工具：把标签序列拼成稳定字符串（便于写入 experiment_config）。"""
    return ",".join(iterable)
