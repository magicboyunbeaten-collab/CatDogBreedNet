"""Project-level configuration for the cat/dog breed classification system.

All paths are resolved relative to the repository root so the project runs on
any machine without hard-coded absolute paths (CODEBUDDY.md rule 7).
"""
from __future__ import annotations

from pathlib import Path

# Repository root: e:/CatDogBreedNet (this file lives in <root>/ml/config.py)
ROOT_DIR = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Data directories
# ---------------------------------------------------------------------------
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"               # official tar.gz + extracted originals
PROCESSED_DATA_DIR = DATA_DIR / "processed"   # ImageFolder layout
TRAIN_DIR = PROCESSED_DATA_DIR / "train"
VAL_DIR = PROCESSED_DATA_DIR / "val"
TEST_DIR = PROCESSED_DATA_DIR / "test"

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = ROOT_DIR / "artifacts"        # model weights, class maps, configs
REPORTS_DIR = ROOT_DIR / "reports"            # metrics, curves, dataset report

# ---------------------------------------------------------------------------
# Dataset: Oxford-IIIT Pet Dataset (official source)
# ---------------------------------------------------------------------------
DATASET_NAME = "Oxford-IIIT Pet Dataset"
DATASET_HOMEPAGE = "https://www.robots.ox.ac.uk/~vgg/data/pets/"
DATASET_BASE_URL = "https://www.robots.ox.ac.uk/~vgg/data/pets/data"
DATASET_FILES = ("images.tar.gz", "annotations.tar.gz")
# Parkhi et al., CVPR 2012
DATASET_PAPER_URL = (
    "https://www.robots.ox.ac.uk/~vgg/publications/2012/Parkhi12/parkhi12.pdf"
)

# ---------------------------------------------------------------------------
# Split policy (documented in reports/dataset.md)
#   test       = official test split (annotations/test.txt)
#   train/val  = official trainval split (annotations/trainval.txt),
#                stratified per class with SEED, VAL_RATIO held out for val.
# ---------------------------------------------------------------------------
SEED = 42
VAL_RATIO = 0.1

# ---------------------------------------------------------------------------
# Image preprocessing standard (torchvision ResNet18 / ImageNet).
# Used from phase 2 onwards; kept here so train/eval/inference share one source.
# ---------------------------------------------------------------------------
IMAGE_SIZE = 224
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
