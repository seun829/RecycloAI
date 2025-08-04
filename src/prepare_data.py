"""
Robustly prepare the TrashNet dataset by downloading and splitting into train/val directories.

Usage:
    python prepare_trashnet.py --output-dir path/to/data [--test-size 0.2] [--seed 42]
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
    classes = [d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))]
    for cls in classes:
        class_dir = os.path.join(source_dir, cls)
        images = [f for f in os.listdir(class_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        random.shuffle(images)
        split_idx = int(len(images) * (1 - test_size))
        train_imgs = images[:split_idx]
        val_imgs = images[split_idx:]
        for phase, files in [('train', train_imgs), ('val', val_imgs)]:
            target_dir = os.path.join(output_dir, phase, cls)
            os.makedirs(target_dir, exist_ok=True)
            for fname in files:
                src = os.path.join(class_dir, fname)
                dst = os.path.join(target_dir, fname)
                shutil.copy2(src, dst)

def main():
    parser = argparse.ArgumentParser(description="Prepare TrashNet dataset.")
    parser.add_argument('--output-dir', '-o', required=True,
                        help="Output directory for train/val folders.")
    parser.add_argument('--test-size', '-t', type=float, default=0.2,
                        help="Fraction of data for validation.")
    parser.add_argument('--seed', '-s', type=int, default=42,
                        help="Random seed for shuffling.")
    args = parser.parse_args()

    temp_dir = tempfile.mkdtemp(prefix='trashnet_')
    zip_url = 'https://github.com/garythung/trashnet/archive/refs/heads/master.zip'
    zip_path = os.path.join(temp_dir, 'trashnet.zip')

    download_zip(zip_url, zip_path)
    extract_zip(zip_path, temp_dir)

    # Locate extracted images directory
    extracted_subdirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
    if not extracted_subdirs:
        print("No directories found after extraction.", file=sys.stderr)
        sys.exit(1)
    extracted_root = os.path.join(temp_dir, extracted_subdirs[0])
    images_dir = os.path.join(extracted_root, 'images')
    if not os.path.isdir(images_dir):
        print(f"Expected images directory at {images_dir}, but not found.", file=sys.stderr)
        sys.exit(1)

    split_and_copy(images_dir, args.output_dir, args.test_size, args.seed)
    print(f"Data preparation complete. Train/val splits are in '{args.output_dir}'.")
    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()
