"""V2 数据准备管线的单元测试（全部使用合成数据，不依赖真实下载）。

覆盖 MODEL_UPGRADE_PLAN U3 的关键不变式：

* 标签归一化与人工核验别名表的一致性（不重复计数、不误合并）；
* 近重复簇的并查集合并；
* **簇原子分配**（含跨类簇必须整簇同 split，这是本轮实际踩到的坑）；
* 图片质量检查（解码失败 / 分辨率过低）；
* 增量同步（写入、删除多余、清理空目录，且不整目录删除）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_v2_class_catalog as catalog_module  # noqa: E402
from scripts import build_v2_dataset as dataset_module  # noqa: E402


# ---------------------------------------------------------------------------
# 标签归一化与别名表
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Chihuahua", "chihuahua"),
    ("Border_collie", "border_collie"),
    ("soft-coated_wheaten_terrier", "soft_coated_wheaten_terrier"),
    ("Shih-Tzu", "shih_tzu"),
    ("  beagle  ", "beagle"),
    ("black-and-tan_coonhound", "black_and_tan_coonhound"),
])
def test_normalize_label(raw, expected):
    assert catalog_module.normalize(raw) == expected


def test_confident_aliases_have_no_duplicate_targets():
    """两个不同 Oxford 品种不得映射到同一个 Stanford 类别（否则等于错误合并）。"""
    targets = list(catalog_module.CONFIDENT_ALIASES.values())
    assert len(targets) == len(set(targets))


def test_confident_aliases_do_not_overlap_ambiguous():
    """已确信的别名不应同时出现在歧义表里，避免自相矛盾。"""
    assert not (set(catalog_module.CONFIDENT_ALIASES)
                & set(catalog_module.AMBIGUOUS_ALIASES))


def test_scottish_terrier_is_resolved_as_alias_not_ambiguous():
    """Scotch Terrier 是 Scottish Terrier 的旧同义名，按同一品种处理。

    这是本轮真实发现的问题：若把它当作新品种，会出现
    ``scottish_terrier`` 与 ``scotch_terrier`` 两个类别指同一品种，
    同时还会与既有训练图形成跨类近重复。
    """
    assert catalog_module.CONFIDENT_ALIASES["scottish_terrier"] == "Scotch_terrier"
    assert "scottish_terrier" not in catalog_module.AMBIGUOUS_ALIASES


def test_border_collie_is_not_merged_with_similar_names():
    """Border Collie / Border Terrier / Collie 是三个不同品种，不得互相映射。"""
    aliases = catalog_module.CONFIDENT_ALIASES
    assert "border_collie" not in aliases
    assert aliases.get("border_terrier") is None
    assert aliases.get("collie") is None
    # 归一化后三者互不相同，且得到预期的三个 canonical label
    names = {catalog_module.normalize(n)
             for n in ("Border_collie", "Border_terrier", "collie")}
    assert names == {"border_collie", "border_terrier", "collie"}
    # 三者都应有中文名，避免后续回退成英文标签
    for label in names:
        assert catalog_module.CHINESE_NAMES.get(label)


def test_excluded_stanford_classes_are_documented():
    """排除项必须带有可读理由，且当前只应有 cocker_spaniel。

    V2.1 起 AmStaff 已改为独立有效类别，不得再出现在排除表里。
    """
    for name, reason in catalog_module.EXCLUDED_STANFORD_CLASSES.items():
        assert reason.strip()
    assert set(catalog_module.EXCLUDED_STANFORD_CLASSES) == {"cocker_spaniel"}
    assert "American_Staffordshire_terrier" not in \
        catalog_module.EXCLUDED_STANFORD_CLASSES


def test_cocker_spaniel_exclusion_reason_is_stable():
    """排除理由必须说明「无法区分美式/英式」且「不猜测性重标」。"""
    reason = catalog_module.EXCLUDED_STANFORD_CLASSES["cocker_spaniel"]
    assert "无法可靠区分" in reason
    assert "不进行猜测性重标" in reason


# ---------------------------------------------------------------------------
# V2.1 AmStaff 口径
# ---------------------------------------------------------------------------

def test_amstaff_has_chinese_name():
    """AmStaff 必须有唯一中文名：美国斯塔福郡梗。"""
    assert (catalog_module.CHINESE_NAMES["american_staffordshire_terrier"]
            == "美国斯塔福郡梗")


def test_amstaff_is_not_an_alias_of_apbt():
    """AmStaff 不得作为 APBT 的别名，也不得与 APBT 互相映射。"""
    assert "american_staffordshire_terrier" not in catalog_module.CONFIDENT_ALIASES
    assert ("American_Staffordshire_terrier"
            not in catalog_module.CONFIDENT_ALIASES.values())
    # APBT 不应出现在任何别名表的键或值里指向 AmStaff
    assert catalog_module.CONFIDENT_ALIASES.get(
        "american_pit_bull_terrier") is None
    for targets in catalog_module.AMBIGUOUS_ALIASES.values():
        assert "American_Staffordshire_terrier" not in targets


def test_apbt_and_english_cocker_are_documented_as_not_merged():
    """APBT 与 English Cocker 属于「有相似类但不合并」，须有明确说明。"""
    not_merged = catalog_module.NOT_MERGED_REASONS
    assert "american_pit_bull_terrier" in not_merged
    assert "english_cocker_spaniel" in not_merged
    assert "独立新增类别" in not_merged["american_pit_bull_terrier"]
    assert "不合并" in not_merged["american_pit_bull_terrier"]
    assert "不与本类合并" in not_merged["english_cocker_spaniel"]
    # 它们不应被误归为「确实没有对应类别」
    assert "american_pit_bull_terrier" not in catalog_module.EXPECTED_NO_MATCH
    assert "english_cocker_spaniel" not in catalog_module.EXPECTED_NO_MATCH


def test_amstaff_has_dedicated_note():
    """AmStaff 的目录说明须写明独立成类、不互设别名、不因相似删图。"""
    note = catalog_module.NEW_BREED_NOTES["American_Staffordshire_terrier"]
    assert "独立新增类别" in note
    assert "american_staffordshire_terrier" in note
    assert "不互设别名" in note


def test_ambiguous_aliases_cleared_after_v21_review():
    """V2.1 人工审核已裁定原两项歧义，歧义表应为空（机制保留）。"""
    assert catalog_module.AMBIGUOUS_ALIASES == {}


def test_cat_breeds_are_not_expected_in_dog_dataset():
    assert "Abyssinian" in catalog_module.CAT_BREEDS
    assert len(catalog_module.CAT_BREEDS) == 12


# ---------------------------------------------------------------------------
# 近重复簇：并查集
# ---------------------------------------------------------------------------

def test_union_find_clusters_transitive():
    items = ["a", "b", "c", "d"]
    pairs = [("a", "b", 0), ("b", "c", 3)]
    clusters = dataset_module.union_find_clusters(items, pairs)
    assert clusters["a"] == clusters["b"] == clusters["c"]
    assert clusters["d"] != clusters["a"]


def test_union_find_clusters_no_pairs():
    items = ["x", "y"]
    clusters = dataset_module.union_find_clusters(items, [])
    assert clusters["x"] != clusters["y"]


# ---------------------------------------------------------------------------
# 簇原子分配（本轮修复的核心 bug）
# ---------------------------------------------------------------------------

def _sizes_by_split(assignment: dict[str, str]) -> dict[str, int]:
    counts = {"train": 0, "val": 0, "test": 0}
    for split in assignment.values():
        counts[split] += 1
    return counts


def test_assign_clusters_keeps_cluster_together():
    """同一簇的所有成员必须落在同一个 split。"""
    cluster_members = {0: ["a1", "a2", "a3"], 1: ["b1"], 2: ["c1", "c2"]}
    class_of = {"a1": "A", "a2": "A", "a3": "A",
                "b1": "B", "c1": "C", "c2": "C"}
    import random
    assignment = dataset_module.assign_clusters_to_splits(
        cluster_members, class_of, dataset_module.SPLIT_RATIOS,
        random.Random(42))
    for cluster in cluster_members.values():
        assert len({assignment[m] for m in cluster}) == 1


def test_assign_clusters_cross_class_cluster_stays_together():
    """**跨类别的近重复簇**也必须整簇同 split。

    Stanford Dogs 中确有跨类近重复（同一照片出现在两个品种下）；
    若按类独立分配，这些图片会被拆到不同 split，造成跨集合泄漏。
    """
    cluster_members = {0: ["fox_1", "walker_1"], 1: ["fox_2"], 2: ["walker_2"]}
    class_of = {"fox_1": "english_foxhound", "fox_2": "english_foxhound",
                "walker_1": "walker_hound", "walker_2": "walker_hound"}
    import random
    assignment = dataset_module.assign_clusters_to_splits(
        cluster_members, class_of, dataset_module.SPLIT_RATIOS,
        random.Random(7))
    assert assignment["fox_1"] == assignment["walker_1"]


def test_assign_clusters_approximates_target_ratios():
    """大量单图簇时，各 split 占比应接近 80/10/10。"""
    members = {}
    class_of = {}
    for index in range(200):
        key = f"img_{index}"
        members[index] = [key]
        class_of[key] = "breed_a"
    import random
    assignment = dataset_module.assign_clusters_to_splits(
        members, class_of, dataset_module.SPLIT_RATIOS, random.Random(2026))
    sizes = _sizes_by_split(assignment)
    assert sizes["train"] == pytest.approx(160, abs=6)
    assert sizes["val"] == pytest.approx(20, abs=6)
    assert sizes["test"] == pytest.approx(20, abs=6)
    assert sum(sizes.values()) == 200


def test_assign_clusters_covers_every_image_exactly_once():
    cluster_members = {0: ["a"], 1: ["b", "c"], 2: ["d"]}
    class_of = {"a": "A", "b": "B", "c": "B", "d": "C"}
    import random
    assignment = dataset_module.assign_clusters_to_splits(
        cluster_members, class_of, dataset_module.SPLIT_RATIOS,
        random.Random(1))
    assert sorted(assignment) == ["a", "b", "c", "d"]


# ---------------------------------------------------------------------------
# 图片质量检查
# ---------------------------------------------------------------------------

def _write_png(path: Path, size=(200, 200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 90, 60)).save(path, format="JPEG")


def test_inspect_image_accepts_valid(tmp_path):
    image = tmp_path / "ok.jpg"
    _write_png(image, (200, 180))
    verdict = dataset_module.inspect_image(image)
    assert verdict["ok"] is True
    assert (verdict["width"], verdict["height"]) == (200, 180)


def test_inspect_image_rejects_too_small(tmp_path):
    image = tmp_path / "small.jpg"
    _write_png(image, (32, 32))
    verdict = dataset_module.inspect_image(image)
    assert verdict["ok"] is False
    assert verdict["reason"].startswith("resolution_too_small")


def test_inspect_image_rejects_corrupt(tmp_path):
    image = tmp_path / "broken.jpg"
    image.write_bytes(b"not an image at all")
    verdict = dataset_module.inspect_image(image)
    assert verdict["ok"] is False
    assert verdict["reason"].startswith("decode_error")


# ---------------------------------------------------------------------------
# 增量同步
# ---------------------------------------------------------------------------

def test_sync_directory_writes_and_removes_stale(tmp_path):
    out_dir = tmp_path / "out"
    sources = {}
    for name, color in (("a/one.jpg", (255, 0, 0)),
                        ("b/two.jpg", (0, 255, 0))):
        source = tmp_path / "src" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 120), color).save(source, format="JPEG")
        sources[str(out_dir / name)] = source

    stats = dataset_module.sync_directory(out_dir, sources)
    assert stats["written"] == 2
    assert stats["removed_stale"] == 0
    assert (out_dir / "a" / "one.jpg").exists()
    assert (out_dir / "b" / "two.jpg").exists()

    # 移除一个条目后重同步：多余文件应被删除，空目录被清理
    stale = out_dir / "b" / "two.jpg"
    sources.pop(str(stale))
    stats = dataset_module.sync_directory(out_dir, sources)
    assert stats["removed_stale"] == 1
    assert not stale.exists()
    assert not (out_dir / "b").exists()


def test_sync_directory_does_not_rewrite_identical_file(tmp_path):
    out_dir = tmp_path / "out"
    source = tmp_path / "src" / "x.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 120), (10, 20, 30)).save(source, format="JPEG")
    sources = {str(out_dir / "x.jpg"): source}

    dataset_module.sync_directory(out_dir, sources)
    first_mtime = (out_dir / "x.jpg").stat().st_mtime_ns

    dataset_module.sync_directory(out_dir, sources)
    assert (out_dir / "x.jpg").stat().st_mtime_ns == first_mtime


# ---------------------------------------------------------------------------
# 哈希工具
# ---------------------------------------------------------------------------

def test_md5_file_matches_hashlib(tmp_path):
    import hashlib
    payload = b"deterministic content"
    path = tmp_path / "f.bin"
    path.write_bytes(payload)
    assert dataset_module.md5_file(path) == hashlib.md5(payload).hexdigest()


def test_md5_file_differs_for_different_content(tmp_path):
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    assert dataset_module.md5_file(first) != dataset_module.md5_file(second)


def test_phash_roundtrip_through_string_cache():
    """哈希缓存用字符串存储，必须能无损还原。"""
    bits = np.random.default_rng(3).integers(0, 2, size=64).astype(bool)
    bits = bits.reshape(8, 8)
    text = dataset_module.phash_bits_to_str(bits)
    restored = dataset_module.str_to_phash_bits(text)
    assert np.array_equal(bits, restored)


# ---------------------------------------------------------------------------
# 常量口径
# ---------------------------------------------------------------------------

def test_split_ratios_sum_to_one():
    total = sum(ratio for _name, ratio in dataset_module.SPLIT_RATIOS)
    assert total == pytest.approx(1.0)


def test_phash_threshold_matches_clean_split_protocol():
    """防泄漏阈值必须与 build_clean_split 的口径一致，否则两套数据不可比。"""
    from scripts.build_clean_split import DEFAULT_THRESHOLD
    assert dataset_module.PHASH_THRESHOLD == DEFAULT_THRESHOLD
