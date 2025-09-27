#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, os, time
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torchvision.models import EfficientNet_B0_Weights

# ------------------- Constants -------------------
STATE_PATH = "best_efficientnet_model.pth"
CLASS_NAMES_PATH = "artifacts/class_names.json"

# ------------------- Small utils -----------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def torch_safe_load(path: str):
    """Torch load that works across versions, preferring CPU."""
    # Try weights_only (PyTorch >= 2.1), fall back if not supported.
    try:
        return torch.load(path, map_location="cpu", weights_only=True)  # type: ignore[call-arg]
    except TypeError:
        return torch.load(path, map_location="cpu")

def extract_state_dict(ckpt):
    """Return a plain state_dict from various checkpoint formats."""
    if isinstance(ckpt, dict):
        for key in ("state_dict", "model_state", "model"):
            val = ckpt.get(key)
            if isinstance(val, dict):
                return val
    return ckpt  # already a state_dict

def strip_dataparallel_prefix(state_dict: dict) -> dict:
    """Remove leading 'module.' (DataParallel) from keys."""
    out = {}
    for k, v in state_dict.items():
        nk = k[7:] if k.startswith("module.") else k
        out[nk] = v
    return out

def save_artifacts(class_to_idx: Dict[str, int]) -> List[str]:
    """Write class names file in correct order and return the list."""
    classes: List[str] = [name for name, _ in sorted(class_to_idx.items(), key=lambda kv: kv[1])]
    ensure_dir(Path(CLASS_NAMES_PATH).parent)
    with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=2)
    return classes

def get_in_features(classifier: nn.Module) -> int:
    if isinstance(classifier, nn.Linear):
        return int(classifier.in_features)
    if isinstance(classifier, nn.Sequential):
        for mod in reversed(classifier):
            if isinstance(mod, nn.Linear):
                return int(mod.in_features)
    return 1280  # EfficientNet-B0 default fallback

# ------------------- Data ------------------------

def build_loaders(data_dir: str, batch_size: int, num_workers: int) -> Tuple[DataLoader, DataLoader, List[str]]:
    # Use stable ImageNet normalization (works across torchvision versions)
    IMAGENET_MEAN = (0.485, 0.456, 0.406)
    IMAGENET_STD  = (0.229, 0.224, 0.225)

    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(0.1, 0.1, 0.1, 0.05),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    train_dir = os.path.join(data_dir, "train")
    val_dir   = os.path.join(data_dir, "val")

    train_ds = datasets.ImageFolder(train_dir, transform=train_tf)
    val_ds   = datasets.ImageFolder(val_dir,   transform=val_tf)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=num_workers, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)

    # Persist class list in index order
    classes: List[str] = [name for name, _ in sorted(train_ds.class_to_idx.items(), key=lambda kv: kv[1])]
    ensure_dir(Path(CLASS_NAMES_PATH).parent)
    with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(classes, f, indent=2)

    return train_loader, val_loader, classes

# ------------------- Model -----------------------

def build_model(num_classes: int, device: torch.device) -> nn.Module:
    m = models.efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
    in_features = get_in_features(m.classifier)
    m.classifier = nn.Sequential(nn.Dropout(0.2), nn.Linear(in_features, num_classes))
    return m.to(device)

def load_model(num_classes: int, device: torch.device, checkpoint_path: str = STATE_PATH) -> nn.Module:
    """
    Build EfficientNet-B0 and attempt to load an existing checkpoint.
    Uses strict=False so a different classifier head size won't crash.
    """
    model = build_model(num_classes, device)

    if not os.path.exists(checkpoint_path):
        print(f"[finetune] No checkpoint at '{checkpoint_path}'. Starting from ImageNet weights.")
        return model

    try:
        ckpt = torch_safe_load(checkpoint_path)
        state_dict = extract_state_dict(ckpt)
        if not isinstance(state_dict, dict):
            raise ValueError("Checkpoint is not a state_dict or dict with state_dict.")
        state_dict = strip_dataparallel_prefix(state_dict)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        print(f"[finetune] Loaded checkpoint from {checkpoint_path}")
        if missing:
            print(f"[finetune]   Missing keys: {missing}")
        if unexpected:
            print(f"[finetune]   Unexpected keys: {unexpected}")
    except Exception as e:
        print(f"[finetune] Failed to load '{checkpoint_path}': {e}")
        print("[finetune] Proceeding with ImageNet-pretrained weights.")
    return model

# ------------------- Eval / Train ----------------

def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> Tuple[float, float]:
    model.eval()
    total, correct, running_loss = 0, 0, 0.0
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            logits = model(x)
            loss = F.cross_entropy(logits, y)
            running_loss += loss.item() * y.size(0)
            pred = logits.argmax(1)
            correct += (pred == y).sum().item()
            total += y.size(0)
    avg_loss = running_loss / max(1, total)
    acc = correct / max(1, total)
    return avg_loss, acc

def train_one_epoch(model: nn.Module, loader: DataLoader, device: torch.device, optimizer: torch.optim.Optimizer):
    model.train()
    running = 0.0
    seen = 0
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = F.cross_entropy(logits, y)
        loss.backward()
        optimizer.step()
        bsz = y.size(0)
        running += loss.item() * bsz
        seen += bsz
    return running / max(1, seen)


# ------------------- Main Train ------------------

def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, classes = build_loaders(args.data_dir, args.batch_size, args.num_workers)

    model = load_model(len(classes), device, checkpoint_path=args.checkpoint)

    # Simple, robust optimizer (single param group to avoid typing weirdness)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_acc = 0.0
    ensure_dir(Path(STATE_PATH).parent)
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss = train_one_epoch(model, train_loader, device, optimizer)
        val_loss, val_acc = evaluate(model, val_loader, device)
        dt = time.time() - t0
        print(f"[{epoch:03d}/{args.epochs}] train_loss={tr_loss:.4f}  val_loss={val_loss:.4f}  val_acc={val_acc*100:.2f}%  ({dt:.1f}s)")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), STATE_PATH)  # state_dict only (what app.py expects)
            print(f"[finetune] Saved best to {STATE_PATH}  (val_acc={best_acc*100:.2f}%)")

    print(f"[finetune] Done. Best val_acc={best_acc*100:.2f}%")

# ------------------- CLI ------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data", help="Root with train/ and val/ subfolders")
    p.add_argument("--checkpoint", default=STATE_PATH, help="Path to starting checkpoint (.pth).")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--num-workers", type=int, default=4)
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    train(args)
