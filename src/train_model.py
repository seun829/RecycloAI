"""
Fine-tune EfficientNet-B0 on a recycling image dataset.

Usage:
    pip install torch torchvision
    python train_efficientnet.py --data-dir path/to/data --epochs 10 --batch-size 32 --lr 1e-3
"""
import os
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models


def build_efficientnet(num_classes, device):
    # Load pretrained EfficientNet-B0
    model = models.efficientnet_b0(pretrained=True)
    # Freeze feature extractor
    for param in model.features.parameters():
        param.requires_grad = False
    # Replace classifier head
    if isinstance(model.classifier, nn.Sequential):
        # Find the first nn.Linear layer in the classifier
        for layer in model.classifier:
            if isinstance(layer, nn.Linear):
                in_features = layer.in_features
                break
        else:
            raise ValueError("No nn.Linear layer found in model.classifier")
    else:
        in_features = model.classifier.in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.2),
        nn.Linear(in_features, num_classes)
    )
    return model.to(device)


def train(model, dataloaders, dataset_sizes, criterion, optimizer, device, num_epochs):
    best_acc = 0.0
    best_path = 'best_efficientnet_model.pth'
    for epoch in range(num_epochs):
        print(f"Epoch {epoch+1}/{num_epochs}")
        print('-' * 20)
        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()
            else:
                model.eval()

            running_loss = 0.0
            running_corrects = 0

            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = float(running_corrects) / dataset_sizes[phase]

            print(f"{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")

            # Save best model
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                torch.save(model.state_dict(), best_path)

    print(f"Best validation accuracy: {best_acc:.4f}")
    print(f"Model saved to {best_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=str, required=True,
                        help='Directory with train/ and val/ subfolders')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size for training and validation')
    parser.add_argument('--lr', type=float, default=1e-3,
                        help='Learning rate for optimizer')
    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Data transformations
    transforms_dict = {
        'train': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                 [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                 [0.229, 0.224, 0.225])
        ]),
    }

    # Datasets and loaders
    data_dirs = {x: os.path.join(args.data_dir, x) for x in ['train', 'val']}
    image_datasets = {x: datasets.ImageFolder(data_dirs[x], transform=transforms_dict[x])
                      for x in ['train', 'val']}
    dataloaders = {x: DataLoader(image_datasets[x], batch_size=args.batch_size,
                                 shuffle=(x=='train'), num_workers=4)
                   for x in ['train', 'val']}
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}

    print(f"Classes: {image_datasets['train'].classes}")

    # Build and train model
    model = build_efficientnet(len(image_datasets['train'].classes), device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)

    train(model, dataloaders, dataset_sizes, criterion, optimizer, device, args.epochs)

if __name__ == '__main__':
    main()