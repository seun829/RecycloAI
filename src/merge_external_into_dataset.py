"""
Merge images from data/external/<Class>/ into existing train/val folders.
Keeps your ImageFolder layout intact. Default split: 90% train, 10% val.

Usage:
  python src/merge_external_into_dataset.py \
    --external data/external --train data/train --val data/val \
    --val-ratio 0.1 --mode copy --max-per-class 0
"""
from __future__ import annotations
import argparse, pathlib, random, shutil

IMG_EXT = {".jpg", ".jpeg", ".png"}


def gather_images(root: pathlib.Path):
    by_class = {}
    for cls_dir in root.iterdir():
        if not cls_dir.is_dir():
            continue
        imgs = [p for p in cls_dir.glob('*') if p.suffix.lower() in IMG_EXT]
        if imgs:
            by_class[cls_dir.name] = imgs
    return by_class


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--external', default='data/external')
    ap.add_argument('--train', default='data/train')
    ap.add_argument('--val', default='data/val')
    ap.add_argument('--val-ratio', type=float, default=0.10)
    ap.add_argument('--mode', choices=['copy','move'], default='copy')
    ap.add_argument('--max-per-class', type=int, default=0, help='0 = no cap')
    args = ap.parse_args()

    src_root = pathlib.Path(args.external)
    tr_root  = pathlib.Path(args.train)
    va_root  = pathlib.Path(args.val)
    tr_root.mkdir(parents=True, exist_ok=True)
    va_root.mkdir(parents=True, exist_ok=True)

    by_class = gather_images(src_root)
    total_copied = 0
    rng = random.Random(42)

    for cls, imgs in by_class.items():
        rng.shuffle(imgs)
        if args.max_per_class > 0:
            imgs = imgs[:args.max_per_class]
        n = len(imgs)
        k = max(1, int(n * args.val_ratio)) if n > 10 else max(1, n//10 or 1)
        val_split = imgs[:k]
        train_split = imgs[k:]

        for d in (tr_root/cls, va_root/cls):
            d.mkdir(parents=True, exist_ok=True)

        op = shutil.copy2 if args.mode == 'copy' else shutil.move
        for p in train_split:
            op(p, (tr_root/cls/p.name))
        for p in val_split:
            op(p, (va_root/cls/p.name))
        total_copied += len(imgs)
        print(f"{cls}: added {len(train_split)} train, {len(val_split)} val")

    print(f"Done. Added {total_copied} images across {len(by_class)} classes.")

if __name__ == '__main__':
    main()