#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch images into data/external/<Class>/ from the UCI RealWaste dataset (no keys).
Classes: Cardboard, Glass, Metal, Paper, Plastic, Trash

Usage (Windows PowerShell):
  pip install pillow requests
  python src\fetch_images.py --dest data\external --per-class 500
"""

from __future__ import annotations
import argparse
import io
import zipfile
import random
import sys
from typing import Dict, List, Tuple, Optional
import pathlib

import requests
from PIL import Image, ImageOps

# ---------------- Config ----------------

CLASSES = ["Cardboard", "Glass", "Metal", "Paper", "Plastic", "Trash"]

# RealWaste has these class folders; we map them to our 6:
REALWASTE_TO_OURS: Dict[str, str] = {
    "Cardboard": "Cardboard",
    "Glass": "Glass",
    "Metal": "Metal",
    "Paper": "Paper",
    "Plastic": "Plastic",
    "Miscellaneous Trash": "Trash",
    # ignore: "Food Organics", "Textile Trash", "Vegetation"
}

# Direct public ZIP from UCI (RealWaste dataset)
UCI_REALWASTE_ZIP = "https://archive.ics.uci.edu/static/public/908/realwaste.zip"

# ---------------- Utils ----------------

def ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def dhash(img: Image.Image, size: int = 8) -> str:
    """8x8 difference hash -> hex string."""
    img = ImageOps.exif_transpose(img).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    rows = [pixels[i*(size+1):(i+1)*(size+1)] for i in range(size)]
    bits = []
    for row in rows:
        for a, b in zip(row, row[1:]):
            bits.append('1' if a > b else '0')
    return f"{int(''.join(bits), 2):0{size*size//4}x}"

def file_dhash(path: pathlib.Path) -> Optional[str]:
    try:
        with Image.open(path) as im:
            return dhash(im)
    except Exception:
        return None

def collect_existing_hashes(root: pathlib.Path) -> Dict[str, set]:
    per = {c: set() for c in CLASSES}
    for c in CLASSES:
        d = root / c
        if not d.exists():
            continue
        for p in d.glob("*.jpg"):
            h = file_dhash(p)
            if h:
                per[c].add(h)
    return per

def save_image_to_class(img: Image.Image, class_dir: pathlib.Path, existing_hashes: set, min_side: int) -> Tuple[bool, str]:
    """Save as JPEG with hash filename; return (kept?, reason_or_empty)."""
    try:
        i = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        return False, f"decode_fail:{e}"
    if min(i.size) < min_side:
        return False, "too_small"
    h = dhash(i)
    if h in existing_hashes:
        return False, "dup"
    tmp = class_dir / f"{h}.jpg"
    try:
        i.save(tmp, format="JPEG", quality=92, optimize=True)
    except Exception as e:
        return False, f"save_fail:{e}"
    existing_hashes.add(h)
    return True, ""

def human_count(d: Dict[str, int]) -> str:
    return ", ".join(f"{k}:{v}" for k, v in d.items())

# --------------- Download / Extract ---------------

def download_realwaste(zip_path: pathlib.Path) -> None:
    ensure_dir(zip_path.parent)
    if zip_path.exists():
        print("[RealWaste] Using cached zip.")
        return
    print("[RealWaste] Downloading zip (≈650MB)…")
    headers = {"User-Agent": "RecycleAI/1.0 (dataset fetcher)"}
    with requests.get(UCI_REALWASTE_ZIP, stream=True, timeout=300, headers=headers) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)

def unzip_any(zip_path: pathlib.Path, out_dir: pathlib.Path) -> None:
    ensure_dir(out_dir)
    if any(out_dir.iterdir()):
        print("[RealWaste] Using existing unzipped contents.")
        return
    print("[RealWaste] Unzipping…")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)

def locate_realwaste_root(unzipped_root: pathlib.Path) -> Optional[pathlib.Path]:
    """
    Find the directory containing class subfolders like:
      RealWaste/Cardboard, RealWaste/Glass, …
    The zip typically has: realwaste-main/RealWaste/<Class>/*.jpg
    """
    candidates = []
    for p in unzipped_root.rglob("*"):
        if p.is_dir():
            # Heuristic: must contain at least one of the expected class dirs
            hits = 0
            for src_name in REALWASTE_TO_OURS.keys():
                if (p / src_name).exists():
                    hits += 1
            if hits >= 3:  # enough evidence
                candidates.append(p)
    if not candidates:
        return None
    # Prefer the deepest path (most specific)
    return max(candidates, key=lambda x: len(x.parts))

# --------------- Fetch from RealWaste ---------------

def fetch_from_realwaste(dest_root: pathlib.Path, per_class: int, min_side: int) -> Dict[str, int]:
    raw_dir = pathlib.Path("data/raw/realwaste")
    zip_path = raw_dir / "realwaste.zip"
    out_dir = raw_dir / "unzipped"

    download_realwaste(zip_path)
    unzip_any(zip_path, out_dir)

    data_root = locate_realwaste_root(out_dir)
    if data_root is None:
        raise RuntimeError("Could not locate RealWaste class folders after unzip.")

    print(f"[RealWaste] Data root: {data_root}")

    # Prepare output and dedupe
    for c in CLASSES:
        ensure_dir(dest_root / c)
    existing = collect_existing_hashes(dest_root)

    added = {c: 0 for c in CLASSES}
    dropped = {"dup": 0, "too_small": 0, "decode_fail": 0, "save_fail": 0}

    # Iterate source classes
    for src_name, tgt_name in REALWASTE_TO_OURS.items():
        # Stop if target already has enough
        if added[tgt_name] >= per_class:
            continue

        src_dir = data_root / src_name
        if not src_dir.exists():
            continue

        # Gather files
        files: List[pathlib.Path] = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
            files.extend(src_dir.rglob(ext))
        if not files:
            continue
        random.shuffle(files)

        tgt_dir = dest_root / tgt_name
        for p in files:
            if added[tgt_name] >= per_class:
                break
            try:
                with Image.open(p) as im:
                    ok, reason = save_image_to_class(im, tgt_dir, existing[tgt_name], min_side)
            except Exception as e:
                ok, reason = False, f"decode_fail:{e}"

            if ok:
                added[tgt_name] += 1
            else:
                # normalize reason key for counters
                key = reason.split(":")[0] if reason else "unknown"
                dropped[key] = dropped.get(key, 0) + 1

    print(f"[RealWaste] Added -> {human_count(added)}")
    print(f"[RealWaste] Drops -> " + ", ".join(f"{k}:{v}" for k, v in dropped.items()))
    return added

# ---------------- Main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data/external", help="Output root directory")
    ap.add_argument("--per-class", type=int, default=500, help="Max images per class to add")
    ap.add_argument("--min-side", type=int, default=224, help="Minimum shorter-side in pixels")
    args = ap.parse_args()

    dest_root = pathlib.Path(args.dest)
    for c in CLASSES:
        ensure_dir(dest_root / c)

    total = fetch_from_realwaste(dest_root, args.per_class, args.min_side)

    print(f"[TOTAL] Added -> {human_count(total)}")
    print(f"Images are saved under: {dest_root}")
    print("Next: merge with src\\merge_external_into_dataset.py")

if __name__ == "__main__":
    main()
