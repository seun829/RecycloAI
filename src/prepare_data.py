#!/usr/bin/env python3
"""
Robustly prepare the TrashNet dataset by downloading and splitting into train/val directories.

Usage:
    python prepare_trashnet.py [--output-dir OUTPUT_DIR] [--test-size TEST_SIZE] [--seed SEED]
"""

import os
import sys
import argparse
import tempfile
import urllib.request
import zipfile
import random
import shutil

def download_zip(url, dest_path):
    try:
        print(f"Downloading {url} to {dest_path}...")
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        print(f"Error downloading dataset: {e}", file=sys.stderr)
        sys.exit(1)

def extract_zip(zip_path, extract_to):
    try:
        print(f"Extracting {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    except Exception as e:
        print(f"Error extracting zip file: {e}", file=sys.stderr)
        sys.exit(1)

def split_and_copy(source_dir, output_dir, test_size, seed):
    random.seed(seed)
    classes = [d for d in os.listdir(source_dir)
               if os.path.isdir(os.path.join(source_dir, d))]
    for cls in classes:
        class_dir = os.path.join(source_dir, cls)
        images = [f for f in os.listdir(class_dir)
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        random.shuffle(images)
        split_idx = int(len(images) * (1 - test_size))
        train_imgs = images[:split_idx]
        val_imgs   = images[split_idx:]
        for phase, files in [('train', train_imgs), ('val', val_imgs)]:
            target_dir = os.path.join(output_dir, phase, cls)
            os.makedirs(target_dir, exist_ok=True)
            for fname in files:
                shutil.copy2(os.path.join(class_dir, fname),
                             os.path.join(target_dir, fname))

def main():
    parser = argparse.ArgumentParser(
        description="Prepare TrashNet dataset (download → split)."
    )
    parser.add_argument(
        '--output-dir', '-o', default="data",
        help="Output directory for train/val folders (default: './data')."
    )
    parser.add_argument(
        '--test-size', '-t', type=float, default=0.2,
        help="Fraction of data for validation (default: 0.2)."
    )
    parser.add_argument(
        '--seed', '-s', type=int, default=42,
        help="Random seed for shuffling (default: 42)."
    )
    args = parser.parse_args()

    # Ensure base output exists
    os.makedirs(args.output_dir, exist_ok=True)

    # 1) Download the GitHub repo ZIP
    temp_dir = tempfile.mkdtemp(prefix='trashnet_')
    zip_url  = 'https://github.com/garythung/trashnet/archive/refs/heads/master.zip'
    zip_path = os.path.join(temp_dir, 'trashnet.zip')
    download_zip(zip_url, zip_path)

    # 2) Extract the repo ZIP
    extract_zip(zip_path, temp_dir)
    extracted_subdirs = [
        d for d in os.listdir(temp_dir)
        if os.path.isdir(os.path.join(temp_dir, d))
    ]
    if not extracted_subdirs:
        print("No directories found after initial extraction.", file=sys.stderr)
        shutil.rmtree(temp_dir)
        sys.exit(1)
    extracted_root = os.path.join(temp_dir, extracted_subdirs[0])

    # 3) Unzip the nested dataset-resized.zip if present
    nested_zip = os.path.join(extracted_root, 'data', 'dataset-resized.zip')
    if os.path.isfile(nested_zip):
        print(f"Found nested zip at {nested_zip}, extracting...")
        with zipfile.ZipFile(nested_zip, 'r') as z:
            z.extractall(os.path.join(extracted_root, 'data'))
    else:
        print(f"No nested dataset-resized.zip found at {nested_zip}")

    # 4) Auto-locate the folder that contains the class dirs
    images_dir = None
    for root, dirs, files in os.walk(extracted_root):
        # look for the standard TrashNet classes
        if {'cardboard','glass','metal','paper','plastic','trash'}.issubset(set(dirs)):
            images_dir = root
            break

    if not images_dir:
        print(f"❌ Could not find the image folders under {extracted_root}.", file=sys.stderr)
        print("Here’s what was found:")
        for root, dirs, _ in os.walk(extracted_root):
            print(f"- {root} → subdirs: {dirs}")
        shutil.rmtree(temp_dir)
        sys.exit(1)

    print(f"Using images from: {images_dir}")

    # 5) Split into train/val
    split_and_copy(images_dir, args.output_dir, args.test_size, args.seed)
    print(f"✅ Data prep complete. Train/val splits are in '{args.output_dir}'.")

    # Cleanup
    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()
