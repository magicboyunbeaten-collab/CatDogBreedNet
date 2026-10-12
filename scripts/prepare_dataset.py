#!/usr/bin/env python
"""Oxford-IIIT Pet Dataset preparation pipeline.

Usage (run from the repository root):

    python scripts/prepare_dataset.py download
    python scripts/prepare_dataset.py build --seed 42 --val-ratio 0.1
    python scripts/prepare_dataset.py stats

Split policy (also documented in reports/dataset.md):
    * test      -> official test split (annotations/test.txt)
    * train/val -> official trainval split (annotations/trainval.txt),
                   stratified per class, random seed 42, VAL_RATIO held out
                   for validation (each class keeps >= 1 validation sample
                   when it has at least 10 trainval samples).

The pipeline never fabricates data: files are only copied from the official
archives, and every step asserts what it actually finds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import tarfile
import urllib.request
from collections import defaultdict
from pathlib import Path

# Allow running as a plain script: python scripts/prepare_dataset.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.config import (  # noqa: E402
    DATASET_BASE_URL,
    DATASET_FILES,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    REPORTS_DIR,
    SEED,
    VAL_RATIO,
)

_CHUNK = 1024 * 1024


def md5_of_file(path: Path, chunk_size: int = _CHUNK) -> str:
    """Return the hex MD5 digest of a file's contents."""
    digest = hashlib.md5()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(
    raw_dir: Path = RAW_DATA_DIR,
    files=DATASET_FILES,
    base_url: str = DATASET_BASE_URL,
    skip_existing: bool = True,
) -> list[dict]:
    """Download the official archives into *raw_dir* and record their MD5."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for name in files:
        dest = raw_dir / name
        if skip_existing and dest.exists() and dest.stat().st_size > 0:
            print(f"[download] {name} already present "
                  f"({dest.stat().st_size} bytes), skipping")
        else:
            url = f"{base_url}/{name}"
            print(f"[download] {url} -> {dest}")
            tmp = dest.with_name(dest.name + ".part")
            with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as out:
                total = int(resp.headers.get("Content-Length", 0))
                done = 0
                while True:
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r[download] {name}: "
                              f"{done / 1e6:.1f}/{total / 1e6:.1f} MB",
                              end="", flush=True)
            print()
            tmp.replace(dest)
        entry = {
            "file": name,
            "url": f"{base_url}/{name}",
            "size_bytes": dest.stat().st_size,
            "md5": md5_of_file(dest),
        }
        manifest.append(entry)
        print(f"[download] {name}: {entry['size_bytes']} bytes, "
              f"md5={entry['md5']}")
    (raw_dir / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def extract_archives(raw_dir: Path = RAW_DATA_DIR, skip_existing: bool = True) -> None:
    """Extract images.tar.gz / annotations.tar.gz into *raw_dir* (idempotent)."""
    raw_dir = Path(raw_dir)
    for name, marker in (("images.tar.gz", "images"),
                         ("annotations.tar.gz", "annotations")):
        target = raw_dir / marker
        if skip_existing and target.is_dir() and any(target.iterdir()):
            print(f"[extract] {marker}/ already present, skipping")
            continue
        archive = raw_dir / name
        if not archive.exists():
            raise FileNotFoundError(
                f"missing archive {archive}; run 'download' first")
        print(f"[extract] {archive.name} -> {raw_dir}")
        with tarfile.open(archive, "r:gz") as tf:
            try:
                tf.extractall(raw_dir, filter="data")
            except TypeError:  # older Python without the extraction filter
                tf.extractall(raw_dir)


def parse_breed_mapping(raw_dir: Path = RAW_DATA_DIR) -> dict[str, str]:
    """image_id -> breed name, parsed from annotations/list.txt."""
    list_txt = Path(raw_dir) / "annotations" / "list.txt"
    if not list_txt.exists():
        raise FileNotFoundError(
            f"missing {list_txt}; run 'download' and extraction first")
    mapping: dict[str, str] = {}
    class_to_breeds: dict[int, set[str]] = defaultdict(set)
    for line in list_txt.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue  # official header/comment lines
        parts = line.split()
        if len(parts) < 2:
            continue
        image_id, class_id = parts[0], int(parts[1])
        breed = image_id.rsplit("_", 1)[0]
        mapping[image_id] = breed
        class_to_breeds[class_id].add(breed)
    for class_id, breeds in sorted(class_to_breeds.items()):
        if len(breeds) != 1:
            raise ValueError(
                f"class {class_id} maps to multiple breed names: {sorted(breeds)}")
    if not mapping:
        raise ValueError(f"no entries parsed from {list_txt}")
    return mapping


def read_split_file(path: Path) -> list[str]:
    """Read an official split file.

    Official trainval.txt / test.txt lines have the format
    ``image_id class_id species breed_id``; only the image id is used here.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"missing split file {path}")
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split()[0])
    return ids


def build_splits(
    raw_dir: Path = RAW_DATA_DIR,
    out_dir: Path = PROCESSED_DATA_DIR,
    seed: int = SEED,
    val_ratio: float = VAL_RATIO,
) -> dict:
    """Build the ImageFolder layout under *out_dir*.

    Returns a summary dict; also writes reports/split_summary.json.
    Raises on missing files, unknown image ids, cross-split id/content
    duplication, or inconsistent class-to-index mappings.
    """
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    extract_archives(raw_dir)

    breed_of = parse_breed_mapping(raw_dir)
    images_dir = raw_dir / "images"
    ann_dir = raw_dir / "annotations"
    test_ids = read_split_file(ann_dir / "test.txt")
    trainval_ids = read_split_file(ann_dir / "trainval.txt")

    known = set(breed_of)
    for name, ids in (("test", test_ids), ("trainval", trainval_ids)):
        missing = [i for i in ids if i not in known]
        if missing:
            raise ValueError(
                f"{len(missing)} ids in {name}.txt absent from list.txt, "
                f"e.g. {missing[:5]}")

    # Stratified split of the official trainval set (deterministic per seed).
    trainval_by_class: dict[str, list[str]] = defaultdict(list)
    for image_id in trainval_ids:
        trainval_by_class[breed_of[image_id]].append(image_id)
    rng = random.Random(seed)
    train_ids: list[str] = []
    val_ids: list[str] = []
    per_class: dict[str, dict[str, int]] = {}
    for breed in sorted(trainval_by_class):
        ids = sorted(trainval_by_class[breed])
        rng.shuffle(ids)
        n_val = int(round(len(ids) * val_ratio))
        if len(ids) >= 10:
            n_val = max(1, n_val)
        per_class[breed] = {
            "trainval_total": len(ids),
            "train": len(ids) - n_val,
            "val": n_val,
        }
        val_ids.extend(ids[:n_val])
        train_ids.extend(ids[n_val:])

    test_by_class: dict[str, int] = defaultdict(int)
    for image_id in test_ids:
        test_by_class[breed_of[image_id]] += 1

    splits = {"train": train_ids, "val": val_ids, "test": test_ids}

    # --- leakage checks: no image id or identical content in two splits ---
    seen_ids: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    for split, ids in splits.items():
        for image_id in ids:
            if image_id in seen_ids:
                raise ValueError(
                    f"image id {image_id} appears in both "
                    f"{seen_ids[image_id]} and {split}")
            seen_ids[image_id] = split

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split, ids in splits.items():
        for image_id in ids:
            src = images_dir / f"{image_id}.jpg"
            if not src.exists():
                raise FileNotFoundError(f"image file not found: {src}")
            dst = out_dir / split / breed_of[image_id] / f"{image_id}.jpg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            digest = md5_of_file(src)
            if digest in seen_hashes:
                raise ValueError(
                    f"duplicate image content: {image_id} has the same bytes "
                    f"as {seen_hashes[digest]} (cross-split leak)")
            seen_hashes[digest] = image_id

    # --- class_to_idx consistency (ImageFolder convention: alphabetical) ---
    breeds = sorted(set(breed_of.values()))
    expected = {name: idx for idx, name in enumerate(breeds)}
    for split in splits:
        present = sorted(p.name for p in (out_dir / split).iterdir()
                         if p.is_dir())
        if present != breeds:
            diff = set(present) ^ set(breeds)
            raise ValueError(f"class set mismatch in split '{split}': {diff}")
        actual = {name: idx for idx, name in enumerate(present)}
        if actual != expected:
            raise ValueError(f"class_to_idx mismatch in split '{split}'")

    summary = {
        "dataset": "Oxford-IIIT Pet Dataset (official archives)",
        "split_policy": (
            "test = official test split; train/val = official trainval split "
            f"stratified per class, seed={seed}, val_ratio={val_ratio}"),
        "seed": seed,
        "val_ratio": val_ratio,
        "num_classes": len(breeds),
        "totals": {split: len(ids) for split, ids in splits.items()},
        "classes": breeds,
        "per_class_trainval": per_class,
        "per_class_test": dict(sorted(test_by_class.items())),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "split_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[build] wrote ImageFolder layout to {out_dir}")
    print(f"[build] totals: {summary['totals']}, classes: {len(breeds)}")
    print(f"[build] summary saved to {REPORTS_DIR / 'split_summary.json'}")
    return summary


def compute_stats(processed_dir: Path = PROCESSED_DATA_DIR) -> dict:
    """Count samples per class per split under an ImageFolder directory."""
    processed_dir = Path(processed_dir)
    if not processed_dir.is_dir():
        raise FileNotFoundError(
            f"processed data directory not found: {processed_dir}; "
            f"run 'build' first")
    stats: dict[str, dict] = {}
    for split in ("train", "val", "test"):
        split_dir = processed_dir / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"missing split directory: {split_dir}")
        classes = {
            class_dir.name: sum(1 for p in class_dir.iterdir() if p.is_file())
            for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir())
        }
        stats[split] = {"total": sum(classes.values()), "classes": classes}
    return stats


def print_stats(stats: dict) -> None:
    splits = ("train", "val", "test")
    classes = sorted({c for s in stats.values() for c in s["classes"]})
    header = f"{'class':<24}" + "".join(f"{s:>8}" for s in splits)
    print(header)
    for cls in classes:
        row = f"{cls:<24}"
        for s in splits:
            row += f"{stats[s]['classes'].get(cls, 0):>8}"
        print(row)
    print("-" * len(header))
    row = f"{'TOTAL':<24}"
    for s in splits:
        row += f"{stats[s]['total']:>8}"
    print(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the Oxford-IIIT Pet Dataset for training.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="download official archives into data/raw")

    p_build = sub.add_parser("build", help="build ImageFolder train/val/test")
    p_build.add_argument("--seed", type=int, default=SEED)
    p_build.add_argument("--val-ratio", type=float, default=VAL_RATIO)

    sub.add_parser("stats", help="print per-split and per-class sample counts")

    args = parser.parse_args(argv)

    if args.command == "download":
        download_dataset()
        return 0
    if args.command == "build":
        build_splits(seed=args.seed, val_ratio=args.val_ratio)
        return 0
    if args.command == "stats":
        stats = compute_stats()
        print_stats(stats)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "split_stats.json").write_text(
            json.dumps(stats, indent=2), encoding="utf-8")
        print(f"\n[stats] saved to {REPORTS_DIR / 'split_stats.json'}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
