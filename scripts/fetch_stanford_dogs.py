#!/usr/bin/env python
"""下载并校验 Stanford Dogs Dataset（MODEL_UPGRADE_PLAN U3 数据源准备）。

用法（在仓库根目录执行）::

    python scripts/fetch_stanford_dogs.py --check     # 只检查本地状态，不下载
    python scripts/fetch_stanford_dogs.py             # 下载缺失/不完整的文件
    python scripts/fetch_stanford_dogs.py --force     # 忽略本地缓存，重新下载

设计要点：

* **只写 ``data/external_raw/stanford_dogs/``**，绝不触碰 ``data/processed/``、
  ``data/processed_clean/``、``artifacts/``、``data/app.db``、``uploads/``；
* **断点续传**：用 ``.part`` 临时文件 + HTTP ``Range`` 请求，网络中断后可重入；
* **可重复执行**：已存在且校验一致的文件直接跳过，不重复下载 756MB；
* **哈希口径（重要）**：官方**未发布**可核对的 SHA256，因此脚本计算的
  SHA256 只称为**本地完整性指纹**（用于确认文件未损坏、两次下载一致），
  **不能**用它独立证明文件来源真实性。可核对的官方信息是**文件大小 /
  服务器 ``Content-Length``**，脚本会一并记录并比对；
* 全程记录来源 URL、下载时间、字节数、Content-Length、本地指纹，写入
  ``data/external_raw/stanford_dogs/download_manifest.json``。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

BASE_URL = "http://vision.stanford.edu/aditya86/ImageNetDogs/"
DEST_DIR = _REPO_ROOT / "data" / "external_raw" / "stanford_dogs"

#: 需要下载的文件（键为本地文件名，值为相对 URL）
FILES = {
    "images.tar": BASE_URL + "images.tar",
    "lists.tar": BASE_URL + "lists.tar",
    "annotation.tar": BASE_URL + "annotation.tar",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def head_info(url: str) -> dict:
    """取官方服务器声明的 Content-Length（可核对的官方大小信息）。"""
    request = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        length = response.headers.get("Content-Length")
        return {
            "http_status": response.status,
            "content_length": int(length) if length and length.isdigit()
            else None,
            "last_modified": response.headers.get("Last-Modified"),
            "content_type": response.headers.get("Content-Type"),
        }


def download(url: str, destination: Path, expected_size: int | None,
             retries: int = 5) -> dict:
    """下载到 ``.part``，完成后原子改名；支持 Range 续传。"""
    part = destination.with_suffix(destination.suffix + ".part")
    resume_from = part.stat().st_size if part.exists() else 0

    for attempt in range(1, retries + 1):
        headers = {"User-Agent": USER_AGENT}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                mode = "ab" if resume_from else "wb"
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
                if response.status == 200 and resume_from:
                    # 服务器不支持 Range，已整体重下
                    resume_from = 0
            break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[fetch] 第 {attempt}/{retries} 次尝试失败："
                  f"{type(exc).__name__}: {exc}", flush=True)
            if attempt == retries:
                raise
            time.sleep(3 * attempt)

    if expected_size is not None and part.stat().st_size != expected_size:
        raise IOError(
            f"下载大小与服务器 Content-Length 不一致："
            f"本地 {part.stat().st_size} vs 服务器 {expected_size}")
    part.replace(destination)
    return {"bytes": destination.stat().st_size,
            "sha256": sha256_file(destination)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="只检查本地状态与服务器信息，不下载")
    parser.add_argument("--force", action="store_true",
                        help="忽略本地已完整文件，重新下载")
    args = parser.parse_args(argv)

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = DEST_DIR / "download_manifest.json"
    manifest = {
        "source": {
            "name": "Stanford Dogs Dataset",
            "homepage": BASE_URL,
            "paper_primary": ("Aditya Khosla, Nityananda Jayadevaprakash, "
                              "Bangpeng Yao, Li Fei-Fei. Novel dataset for "
                              "Fine-Grained Image Categorization. FGVC @ "
                              "CVPR 2011."),
            "paper_secondary": ("J. Deng, W. Dong, R. Socher, L.-J. Li, "
                                "K. Li, L. Fei-Fei. ImageNet: A Large-Scale "
                                "Hierarchical Image Database. CVPR 2009."),
            "stated_categories": 120,
            "stated_images": 20580,
            "note": ("官方页面未发布可核对的 SHA256；本清单中的 sha256 为"
                     "**本地完整性指纹**，仅用于确认文件未损坏与两次下载"
                     "一致，不能独立证明文件来源真实性。可核对的官方信息是"
                     "服务器 Content-Length（下方 content_length）。"),
        },
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    all_ok = True
    for name, url in FILES.items():
        destination = DEST_DIR / name
        print(f"[fetch] {name}", flush=True)
        try:
            server = head_info(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[fetch]   无法连接服务器：{type(exc).__name__}: {exc}",
                  flush=True)
            manifest["files"][name] = {"url": url, "status": "unreachable",
                                       "error": str(exc)}
            all_ok = False
            continue

        size_text = (f"{server['content_length']:,} B"
                     if server["content_length"] else "unknown")
        print(f"[fetch]   服务器 Content-Length = {size_text}", flush=True)

        entry = {"url": url, "http_status": server["http_status"],
                 "content_length": server["content_length"],
                 "server_last_modified": server["last_modified"]}

        if destination.exists() and not args.force:
            local_bytes = destination.stat().st_size
            if (server["content_length"] is None
                    or local_bytes == server["content_length"]):
                entry.update({"status": "present",
                              "bytes": local_bytes,
                              "sha256": sha256_file(destination),
                              "size_matches_server": True})
                print(f"[fetch]   已存在且大小匹配，跳过下载 "
                      f"({local_bytes:,} B)", flush=True)
                manifest["files"][name] = entry
                continue
            print(f"[fetch]   本地大小 {local_bytes:,} 与服务器不符，重新下载",
                  flush=True)

        if args.check:
            entry["status"] = "missing_or_incomplete"
            manifest["files"][name] = entry
            all_ok = False
            continue

        started = time.time()
        info = download(url, destination, server["content_length"])
        entry.update({"status": "downloaded", **info,
                      "download_seconds": round(time.time() - started, 1),
                      "size_matches_server": (
                          server["content_length"] is None
                          or info["bytes"] == server["content_length"])})
        print(f"[fetch]   完成 {info['bytes']:,} B，"
              f"本地指纹 sha256={info['sha256'][:16]}...，"
              f"耗时 {entry['download_seconds']}s", flush=True)
        manifest["files"][name] = entry

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[fetch] wrote {manifest_path}", flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
