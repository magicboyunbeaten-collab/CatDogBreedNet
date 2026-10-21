#!/usr/bin/env python
"""Single-image breed prediction CLI.

Usage (from the repository root):

    python -m ml.predict --image path/to/pet.jpg --top-k 3

Loads the best checkpoint saved by ``ml.train`` together with its class
mapping and prints the Top-K breeds with softmax scores and the inference
latency. The preprocessing is exactly the evaluation transform from
``ml.dataset`` (deterministic, no random augmentation), so train/validation/
inference preprocessing stay consistent.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow running as a plain script: python ml/predict.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import torch  # noqa: E402
from PIL import Image  # noqa: E402

from ml.model import BEST_WEIGHTS_PATH  # noqa: E402


def load_image(image_path: Path) -> Image.Image:
    """Open an image file and convert it to RGB; raise clear errors."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    try:
        with Image.open(image_path) as im:
            return im.convert("RGB")
    except Exception as exc:  # PIL raises UnidentifiedImageError and friends
        raise ValueError(
            f"cannot decode image {image_path} ({type(exc).__name__}: {exc}); "
            f"supported formats include JPEG/PNG") from exc


def predict_from_tensor(model, image_tensor, class_names, top_k=3, device="cpu"):
    """Run the model on a single image tensor (C,H,W); return a result dict.

    Besides the Top-K list the result also carries the **full softmax vector**
    under ``probabilities`` (``{class_name: score}``). Top-K alone is not enough
    for look-alike candidate groups: a candidate ranked below ``top_k`` would
    otherwise be treated as a zero probability and shown as 0 %, which would
    misrepresent the model output. The extra key is internal only — the API
    response schema never exposes it.
    """
    num_classes = len(class_names)
    if not 1 <= top_k <= num_classes:
        raise ValueError(
            f"top_k must be between 1 and {num_classes}, got {top_k}")
    model.eval()
    started = time.perf_counter()
    with torch.inference_mode():
        logits = model(image_tensor.unsqueeze(0).to(device))
        scores = torch.softmax(logits, dim=1).squeeze(0)
        k = min(top_k, num_classes)
        top_scores, top_indices = torch.topk(scores, k)
    elapsed_ms = (time.perf_counter() - started) * 1000
    predictions = [
        {"breed": class_names[idx], "confidence": round(float(score), 6)}
        for score, idx in zip(top_scores.tolist(), top_indices.tolist())
    ]
    probabilities = {
        class_names[index]: round(float(score), 6)
        for index, score in enumerate(scores.tolist())
    }
    return {"predictions": predictions, "probabilities": probabilities,
            "elapsed_ms": round(elapsed_ms, 3)}


def predict_image(
    image_path: Path,
    top_k: int = 3,
    weights_path: Path = BEST_WEIGHTS_PATH,
    device: str = "auto",
    model_factory=None,
) -> dict:
    """Predict the breeds of a single image file.

    Returns a JSON-serialisable dict with the Top-K breeds, their softmax
    scores and the inference latency in milliseconds. Scores are normalized
    over the trained class set only -- they are not true probabilities.

    Internally this builds the shared ``ml.predictor.Predictor`` service, so
    the CLI and the FastAPI backend use exactly the same preprocessing, class
    mapping and Top-K logic. A CLI process loads the checkpoint once.
    """
    from ml.predictor import Predictor  # local import avoids a module cycle

    predictor = Predictor(weights_path=weights_path, device=device,
                          model_factory=model_factory)
    started = time.perf_counter()
    image = load_image(image_path)
    result = predictor.predict_pil(image, top_k=top_k)
    total_ms = (time.perf_counter() - started) * 1000

    return {
        "success": True,
        "image_path": str(image_path),
        "top_k": top_k,
        "num_classes": predictor.num_classes,
        "predictions": result["predictions"],
        "inference_ms": result["inference_ms"],
        "preprocess_ms": result["preprocess_ms"],
        "device": str(predictor.device),
        "note": ("confidence is a softmax score over the trained class set, "
                 "not a true probability"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Predict the cat/dog breed of a single image.")
    parser.add_argument("--image", type=Path, required=True,
                        help="path to a local image file")
    parser.add_argument("--top-k", type=int, default=3,
                        help="number of top predictions to show (default 3)")
    parser.add_argument("--weights", type=Path, default=BEST_WEIGHTS_PATH,
                        help="path to the model checkpoint")
    parser.add_argument("--device", default="auto",
                        choices=["auto", "cpu", "cuda"])
    args = parser.parse_args(argv)

    try:
        result = predict_image(args.image, top_k=args.top_k,
                               weights_path=args.weights, device=args.device)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[predict] error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    top = result["predictions"][0]
    print(f"\n[predict] {args.image} -> {top['breed']} "
          f"(score={top['confidence']:.4f}, "
          f"inference={result['inference_ms']:.1f} ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
