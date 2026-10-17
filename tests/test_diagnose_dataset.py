"""Unit tests for the U1 read-only diagnostics script.

All tests use synthetic images/files in ``tmp_path``; they do not require the
real dataset, pretrained weights, or any trained checkpoint. Nothing here is a
model-accuracy claim (CODEBUDDY.md section 10.2).
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from diagnose_dataset import (  # noqa: E402
    _HAS_SCIPY,
    check_label_consistency,
    find_near_duplicates,
    hamming_distance,
    image_phash,
    md5_of_file,
    near_duplicate_breed_counts,
    pearson_correlation,
    review_training_log,
    scan_splits,
)


def _save_image(path: Path, array: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array, "RGB").save(path, format="JPEG", quality=95)
    return path


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def test_md5_of_file(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    assert md5_of_file(p) == hashlib.md5(b"hello world").hexdigest()


def test_hamming_distance():
    a = np.array([True, False, True, False])
    assert hamming_distance(a, a) == 0
    assert hamming_distance(a, ~a) == a.size


def test_pearson_correlation_basics():
    assert pearson_correlation([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert pearson_correlation([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert pearson_correlation([1, 2, 3], [2, 2, 2]) is None  # 零方差
    assert pearson_correlation([1, 2], [1, 2, 3]) is None    # 长度不一致
    assert pearson_correlation([1], [1]) is None             # 样本不足


@pytest.mark.skipif(not _HAS_SCIPY, reason="scipy 不可用")
def test_image_phash_identical_vs_different(tmp_path):
    same = np.random.default_rng(3).integers(
        0, 255, size=(96, 96, 3), dtype=np.uint8)
    other = np.random.default_rng(4).integers(
        0, 255, size=(96, 96, 3), dtype=np.uint8)
    p1 = _save_image(tmp_path / "a.jpg", same)
    p2 = _save_image(tmp_path / "b.jpg", same)
    p3 = _save_image(tmp_path / "c.jpg", other)

    h1, h2, h3 = image_phash(p1), image_phash(p2), image_phash(p3)
    assert h1 is not None and h1.shape == (8, 8)
    assert hamming_distance(h1, h2) == 0        # 同内容 -> 距离 0
    assert hamming_distance(h1, h3) > 5         # 不同内容 -> 远于阈值


# ---------------------------------------------------------------------------
# 样本扫描与标签一致性
# ---------------------------------------------------------------------------

def _make_split_tree(root: Path, classes=("a_class", "b_class"), per=2):
    for split in ("train", "val", "test"):
        for cls in classes:
            d = root / split / cls
            d.mkdir(parents=True)
            for i in range(per):
                (d / f"{cls}_{i}.jpg").write_bytes(b"not-a-real-image")
    return root


def test_scan_splits_counts_and_order(tmp_path):
    _make_split_tree(tmp_path, classes=("a_class", "b_class"), per=2)
    scan = scan_splits(tmp_path)
    for split in ("train", "val", "test"):
        assert scan[split]["total"] == 4
        assert scan[split]["classes"] == {"a_class": 2, "b_class": 2}
    consistency = check_label_consistency(scan)
    assert consistency["class_sets_identical"] is True
    assert consistency["orders_identical_across_splits"] is True
    assert consistency["train_order_is_alphabetical"] is True


def test_scan_splits_order_matches_imagefolder_case_sensitivity(tmp_path):
    """顺序必须是大小写敏感的字符串排序（与 ImageFolder 一致）。

    Windows 上按 Path 排序会大小写不敏感，导致 B_class/a_class 顺序颠倒，
    曾造成“标签顺序不一致”的假警报。
    """
    _make_split_tree(tmp_path, classes=("a_class", "B_class"), per=1)
    scan = scan_splits(tmp_path)
    assert scan["train"]["order"] == ["B_class", "a_class"]  # ASCII：大写在前


def test_check_label_consistency_detects_missing_class():
    scan = {
        "train": {"total": 2, "classes": {"a": 1, "b": 1},
                  "order": ["a", "b"]},
        "val": {"total": 1, "classes": {"a": 1}, "order": ["a"]},
        "test": {"total": 1, "classes": {"a": 1}, "order": ["a"]},
    }
    result = check_label_consistency(scan)
    assert result["class_sets_identical"] is False
    assert result["classes_missing_per_split"]["val"] == ["b"]


def test_scan_splits_requires_all_splits(tmp_path):
    (tmp_path / "train" / "a").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        scan_splits(tmp_path)


# ---------------------------------------------------------------------------
# 近重复检测
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAS_SCIPY, reason="scipy 不可用")
def test_find_near_duplicates_flags_cross_split(tmp_path):
    same = np.random.default_rng(11).integers(
        0, 255, size=(96, 96, 3), dtype=np.uint8)
    other = np.random.default_rng(12).integers(
        0, 255, size=(96, 96, 3), dtype=np.uint8)
    items = [
        {"split": "train", "class": "beagle",
         "path": _save_image(tmp_path / "train/beagle/1.jpg", same)},
        {"split": "test", "class": "beagle",
         "path": _save_image(tmp_path / "test/beagle/2.jpg", same)},
        {"split": "val", "class": "beagle",
         "path": _save_image(tmp_path / "val/beagle/3.jpg", same)},
        {"split": "train", "class": "boxer",
         "path": _save_image(tmp_path / "train/boxer/4.jpg", other)},
    ]
    result = find_near_duplicates(items, threshold=5)

    assert result["available"] is True
    assert result["images_hashed"] == 4
    zero_pairs = [p for p in result["pairs"] if p["distance"] == 0]
    assert len(zero_pairs) == 3  # 前三张内容相同，C(3,2)=3
    assert all(p["cross_split"] for p in zero_pairs)
    assert all(p["a"]["class"] == p["b"]["class"] for p in zero_pairs)
    # 不同内容的图片不应出现在 <= 5 的结果中
    assert all(p["a"]["path"] != items[3]["path"]
               and p["b"]["path"] != items[3]["path"]
               for p in result["pairs"])


@pytest.mark.skipif(not _HAS_SCIPY, reason="scipy 不可用")
def test_find_near_duplicates_no_false_negative_for_distinct(tmp_path):
    """多张互不相同的图片：即使很多，也不应误报为近重复。"""
    rng = np.random.default_rng(21)
    items = []
    for i in range(12):
        arr = rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8)
        items.append({
            "split": "train", "class": "c",
            "path": _save_image(tmp_path / f"img_{i}.jpg", arr)})
    result = find_near_duplicates(items, threshold=5)
    assert result["pair_count"] == 0


def test_find_near_duplicates_degrades_without_scipy(monkeypatch):
    """scipy 缺失时必须显式降级，而不是静默返回空结果。"""
    import diagnose_dataset as mod

    monkeypatch.setattr(mod, "_HAS_SCIPY", False)
    result = mod.find_near_duplicates(
        [{"split": "train", "class": "c", "path": Path("missing.jpg")}])
    assert result["available"] is False
    assert "reason" in result and result["pairs"] == []


def test_near_duplicate_breed_counts():
    """每对近重复会给两个品种各计 1 次；cross_split 只在跨子集对计。"""
    near = {"pairs": [
        {"distance": 0, "cross_split": True,
         "a": {"split": "train", "class": "beagle", "path": "x"},
         "b": {"split": "test", "class": "beagle", "path": "y"}},
        {"distance": 3, "cross_split": False,
         "a": {"split": "train", "class": "beagle", "path": "x"},
         "b": {"split": "train", "class": "boxer", "path": "z"}},
    ]}
    counts = near_duplicate_breed_counts(near)
    # 第 1 对：beagle 计 2 次（两端同类）；第 2 对：beagle +1、boxer +1
    assert counts["beagle"] == {"total": 3, "cross_split": 2}
    assert counts["boxer"] == {"total": 1, "cross_split": 0}


# ---------------------------------------------------------------------------
# 训练日志复核
# ---------------------------------------------------------------------------

def test_review_training_log(tmp_path):
    p = tmp_path / "train_log.csv"
    p.write_text(
        "epoch,train_loss,train_acc,val_loss,val_acc,lr,epoch_seconds\n"
        "1,0.50,0.900,0.60,0.800,0.001,10.0\n"
        "2,0.30,0.950,0.55,0.850,0.001,11.0\n"
        "3,0.20,0.980,0.60,0.840,0.001,12.0\n",
        encoding="utf-8")
    result = review_training_log(p)
    assert result["available"] is True
    assert result["epochs_completed"] == 3
    assert result["best_epoch"] == 2
    assert result["best_val_acc"] == pytest.approx(0.85)
    assert result["final_train_val_gap"] == pytest.approx(0.14)
    assert result["total_train_seconds"] == pytest.approx(33.0)
    assert result["mean_epoch_seconds"] == pytest.approx(11.0)


def test_review_training_log_missing_file(tmp_path):
    assert review_training_log(tmp_path / "nope.csv") == {"available": False}
