"""Unit tests for the dataset preparation pipeline.

These tests use tiny synthetic images to verify the software logic only
(CODEBUDDY.md section 10.2). They do not require the real dataset and the
synthetic images are never used as model experiment data.
"""
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prepare_dataset import (  # noqa: E402
    build_splits,
    compute_stats,
    md5_of_file,
    parse_breed_mapping,
    read_split_file,
)

CLASSES = ["Breed_A", "Breed_B", "Breed_C"]
PER_CLASS = 12


def make_fake_dataset(root: Path, classes=CLASSES, per_class=PER_CLASS) -> None:
    """Create a miniature Oxford-IIIT-like raw layout with real JPEG files."""
    (root / "annotations").mkdir(parents=True)
    (root / "images").mkdir(parents=True)
    list_lines, trainval_lines, test_lines = [], [], []
    for ci, breed in enumerate(classes, start=1):
        for j in range(per_class):
            image_id = f"{breed}_{1000 + j}"
            Image.new("RGB", (8, 8), (ci * 20 % 256, j * 10 % 256, 0)).save(
                root / "images" / f"{image_id}.jpg")
            list_lines.append(f"{image_id} {ci} 1 {ci}")
            # official trainval/test files use "image class species breed"
            # columns; every 6th sample goes to the official-style test split
            (test_lines if j % 6 == 0 else trainval_lines).append(
                f"{image_id} {ci} 1 {ci}")
    (root / "annotations" / "list.txt").write_text(
        "\n".join(list_lines) + "\n", encoding="utf-8")
    (root / "annotations" / "trainval.txt").write_text(
        "\n".join(trainval_lines) + "\n", encoding="utf-8")
    (root / "annotations" / "test.txt").write_text(
        "\n".join(test_lines) + "\n", encoding="utf-8")


def test_build_splits_creates_imagefolder_layout(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    make_fake_dataset(raw)
    summary = build_splits(raw_dir=raw, out_dir=out, seed=42, val_ratio=0.1)

    assert summary["totals"]["train"] + summary["totals"]["val"] \
        + summary["totals"]["test"] == len(CLASSES) * PER_CLASS
    assert summary["num_classes"] == len(CLASSES)
    for split in ("train", "val", "test"):
        for cls in CLASSES:
            assert (out / split / cls).is_dir()
    # ImageFolder convention: identical class ordering in every split
    for split in ("train", "val", "test"):
        present = sorted(p.name for p in (out / split).iterdir() if p.is_dir())
        assert present == sorted(CLASSES)


def test_build_splits_is_deterministic(tmp_path):
    raw = tmp_path / "raw"
    make_fake_dataset(raw)
    s1 = build_splits(raw_dir=raw, out_dir=tmp_path / "out1", seed=42, val_ratio=0.1)
    s2 = build_splits(raw_dir=raw, out_dir=tmp_path / "out2", seed=42, val_ratio=0.1)
    assert s1["per_class_trainval"] == s2["per_class_trainval"]


def test_build_splits_rejects_id_in_two_splits(tmp_path):
    raw = tmp_path / "raw"
    make_fake_dataset(raw)
    ann = raw / "annotations"
    # put one trainval id into the test split as well
    first = (ann / "trainval.txt").read_text().splitlines()[0]
    with (ann / "test.txt").open("a", encoding="utf-8") as fh:
        fh.write(first + "\n")
    with pytest.raises(ValueError, match="appears in both"):
        build_splits(raw_dir=raw, out_dir=tmp_path / "out", seed=42, val_ratio=0.1)


def test_build_splits_missing_data_raises(tmp_path):
    # Completely empty raw dir: the pipeline must fail with a clear error
    # (either about the missing archive or the missing annotations).
    with pytest.raises(FileNotFoundError, match="archive|list.txt"):
        build_splits(raw_dir=tmp_path / "empty", out_dir=tmp_path / "out")


def test_parse_breed_mapping_missing_list_txt(tmp_path):
    # Annotations dir exists but list.txt is missing.
    (tmp_path / "annotations").mkdir()
    with pytest.raises(FileNotFoundError, match="list.txt"):
        parse_breed_mapping(tmp_path)


def test_compute_stats_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="processed data directory"):
        compute_stats(tmp_path / "nope")


def test_compute_stats_counts(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "processed"
    make_fake_dataset(raw)
    build_splits(raw_dir=raw, out_dir=out, seed=42, val_ratio=0.1)
    stats = compute_stats(out)
    assert set(stats) == {"train", "val", "test"}
    assert stats["train"]["total"] + stats["val"]["total"] \
        + stats["test"]["total"] == len(CLASSES) * PER_CLASS
    for split in stats:
        assert sum(stats[split]["classes"].values()) == stats[split]["total"]


def test_parse_breed_mapping_and_split_files(tmp_path):
    raw = tmp_path / "raw"
    make_fake_dataset(raw)
    mapping = parse_breed_mapping(raw)
    assert len(mapping) == len(CLASSES) * PER_CLASS
    assert all(v in CLASSES for v in mapping.values())
    assert len(read_split_file(raw / "annotations" / "test.txt")) > 0


def test_md5_of_file(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    assert md5_of_file(f) == "5eb63bbbe01eeed093cb22bb8f5acdc3"
