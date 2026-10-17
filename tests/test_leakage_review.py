"""Unit tests for the leakage-review / clean-split helpers.

These tests target the exact defects found while building the de-duplicated
split, so they must keep passing:

1. ``find_near_duplicate_pairs`` must preserve the (left, right) orientation of
   each pair. An earlier version sorted the pair by string, which silently
   swapped sides whenever the *right* key sorted first alphabetically and made
   the "exclude train/val images that leak into test" step miss those images
   (25 known cross-split pairs -> only 23 excluded).
2. ``_blocks`` must flatten the (8, 8) pHash array before slicing; slicing a
   2-D array by flat indices silently produced empty blocks.
3. The multi-index search must be complete (no missed near-duplicates).

All tests use synthetic bit arrays; no real image, dataset or checkpoint is
needed.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (str(REPO_ROOT), str(REPO_ROOT / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from build_clean_split import (  # noqa: E402
    UnionFind,
    _blocks,
    find_near_duplicate_pairs,
    hamming,
    original_train_val_split,
)


def _hash_from_bits(bits: list[int]) -> np.ndarray:
    """Build an (8, 8) bool pHash-like array from 64 flat bits."""
    assert len(bits) == 64
    return np.array(bits, dtype=bool).reshape(8, 8)


def _flip(bits: list[int], *indices: int) -> list[int]:
    out = list(bits)
    for index in indices:
        out[index] = 1 - out[index]
    return out


# 用随机位模式而非周期模式：周期模式会让各分块键相同，掩盖分块逻辑问题
BASE = [int(v) for v in np.random.default_rng(0).integers(0, 2, size=64)]


# ---------------------------------------------------------------------------
# _blocks
# ---------------------------------------------------------------------------

def test_blocks_flattens_and_is_non_empty():
    keys = _blocks(_hash_from_bits(BASE), 6)
    assert len(keys) == 6
    assert all(len(key) > 0 for key in keys), "空块会使索引退化"
    assert len(set(keys)) == 6, "各块键应互不相同"


def test_blocks_only_changes_the_block_that_was_flipped():
    before = _blocks(_hash_from_bits(BASE), 6)
    # 翻转第 3 位（落在第 1 块）
    after = _blocks(_hash_from_bits(_flip(BASE, 3)), 6)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [0], f"只有第 1 块应变化，实际变化块={changed}"


# ---------------------------------------------------------------------------
# find_near_duplicate_pairs：归属方向
# ---------------------------------------------------------------------------

def test_pairs_preserve_left_right_orientation_when_right_sorts_first():
    """回归：右侧键字母序更小时，三元组必须仍是 (left, right, distance)。"""
    left_key = "z_train"      # 字母序更大
    right_key = "a_test"      # 字母序更小
    hashes = {
        left_key: _hash_from_bits(BASE),
        right_key: _hash_from_bits(_flip(BASE, 5, 9)),
    }
    pairs = find_near_duplicate_pairs([left_key], [right_key], hashes, 5)
    assert pairs == [(left_key, right_key, 2)], (
        "必须保持 (left, right, distance)；若被按字符串排序即回归")


def test_pairs_orientation_when_left_sorts_first():
    left_key, right_key = "a_train", "z_test"
    hashes = {
        left_key: _hash_from_bits(BASE),
        right_key: _hash_from_bits(_flip(BASE, 1)),
    }
    assert find_near_duplicate_pairs([left_key], [right_key], hashes, 5) == [
        (left_key, right_key, 1)]


def test_pairs_respect_threshold():
    hashes = {
        "x": _hash_from_bits(BASE),
        "near": _hash_from_bits(_flip(BASE, *range(5))),    # 距离 5
        "far": _hash_from_bits(_flip(BASE, *range(6))),     # 距离 6
    }
    pairs = find_near_duplicate_pairs(["x"], ["near", "far"], hashes, 5)
    assert pairs == [("x", "near", 5)]


def test_pairs_within_one_set_are_not_duplicated():
    """left 与 right 是同一集合时，同一无序对只应返回一次。"""
    hashes = {
        "p": _hash_from_bits(BASE),
        "q": _hash_from_bits(_flip(BASE, 2, 7)),
        "r": _hash_from_bits(_flip(BASE, *range(20))),
    }
    pairs = find_near_duplicate_pairs(["p", "q", "r"], ["p", "q", "r"],
                                      hashes, 5)
    assert len(pairs) == 1
    assert {frozenset(p[:2]) for p in pairs} == {frozenset(("p", "q"))}


def test_pairs_are_complete_no_missed_recall():
    """多索引分块不能漏召：构造多对近重复，逐一验证都能被找到。"""
    rng = np.random.default_rng(0)
    hashes = {}
    expected = set()
    for i in range(60):
        bits = list(rng.integers(0, 2, size=64))
        hashes[f"img_{i:03d}"] = _hash_from_bits(bits)
    # 人为制造 8 对距离 1-4 的近重复（右侧键字母序更小，专门覆盖回归点）
    for i in range(8):
        left_key = f"zz_left_{i}"
        right_key = f"aa_right_{i}"
        bits = list(rng.integers(0, 2, size=64))
        hashes[left_key] = _hash_from_bits(bits)
        hashes[right_key] = _hash_from_bits(_flip(bits, i, i + 1))
        expected.add(frozenset((left_key, right_key)))

    found = find_near_duplicate_pairs(list(hashes), list(hashes), hashes, 5)
    found_pairs = {frozenset(p[:2]) for p in found}
    missing = expected - found_pairs
    assert not missing, f"漏召了 {len(missing)} 对近重复"
    assert len(found_pairs) >= len(expected)


# ---------------------------------------------------------------------------
# 近重复簇
# ---------------------------------------------------------------------------

def test_union_find_groups_transitive_near_duplicates():
    union = UnionFind()
    for key in ("a", "b", "c", "d"):
        union.find(key)
    union.union("a", "b")
    union.union("b", "c")
    clusters = union.clusters()
    assert clusters == {union.find("a"): ["a", "b", "c"],
                        union.find("d"): ["d"]}


# ---------------------------------------------------------------------------
# 原始 train/val 划分复现
# ---------------------------------------------------------------------------

def test_original_train_val_split_matches_prepare_dataset():
    """必须与 scripts/prepare_dataset.py 的按类分层算法完全一致。"""
    breed_of = {}
    trainval_ids = []
    for breed in ("beagle", "boxer", "chihuahua"):
        for index in range(20):
            image_id = f"{breed}_{index}"
            breed_of[image_id] = breed
            trainval_ids.append(image_id)

    assignment = original_train_val_split(trainval_ids, breed_of,
                                          seed=42, val_ratio=0.1)
    assert set(assignment) == set(trainval_ids)
    # 每类 20 张 -> n_val = round(2.0) = 2，且 >= 10 时至少 1
    for breed in ("beagle", "boxer", "chihuahua"):
        val_count = sum(1 for i in trainval_ids
                        if breed_of[i] == breed and assignment[i] == "val")
        assert val_count == 2, f"{breed} 的 val 样本数应为 2，实际 {val_count}"
    # 确定性：同种子两次结果一致
    assert assignment == original_train_val_split(
        trainval_ids, breed_of, seed=42, val_ratio=0.1)
    # 换种子结果应不同
    assert assignment != original_train_val_split(
        trainval_ids, breed_of, seed=7, val_ratio=0.1)


def test_hamming_distance():
    a = _hash_from_bits(BASE)
    assert hamming(a, a) == 0
    assert hamming(a, _hash_from_bits(_flip(BASE, 0, 1, 2))) == 3
