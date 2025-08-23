from flask import Flask, request, jsonify, render_template
import base64
from io import BytesIO
from PIL import Image
import numpy as np

# --- minimal new imports for PyTorch ---
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models
# ---------------------------------------

app = Flask(__name__)

STATE_PATH = "best_efficientnet_model.pth"

NUM_CLASSES_FALLBACK = 6


# -------- helpers (typed + robust) --------
def infer_num_classes_from_state(state_dict: dict) -> int | None:
    """
    Try to infer the classifier output size from state_dict.
    Looks for EfficientNet-B0 heads saved as classifier.1.{weight|bias}.
    Returns None if not found.
    """
    for k, v in state_dict.items():
        if k.endswith("classifier.1.weight") and hasattr(v, "shape"):
            return int(v.shape[0])
    for k, v in state_dict.items():
        if k.endswith("classifier.1.bias") and hasattr(v, "shape"):
            return int(v.shape[0])
    return None


def get_in_features(classifier: nn.Module) -> int:
    """
    Return the input features for the final Linear layer in EfficientNet's classifier.
    Falls back to 1280 (EfficientNet-B0 feature size) if not found.
    """
    if isinstance(classifier, nn.Linear):
        return int(classifier.in_features)

    if isinstance(classifier, nn.Sequential):
        # scan from the end for a Linear
        for mod in reversed(classifier):
            if isinstance(mod, nn.Linear):
                return int(mod.in_features)

    # Safe fallback for EfficientNet-B0
    return 1280


# -------- build model + load weights --------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_state = torch.load(STATE_PATH, map_location="cpu")

num_classes_inferred = infer_num_classes_from_state(_state)
num_classes: int = num_classes_inferred if num_classes_inferred is not None else int(NUM_CLASSES_FALLBACK)

_model = models.efficientnet_b0(pretrained=True)
in_features: int = get_in_features(_model.classifier)

# match your training head: Dropout(0.2) + Linear(in_features -> num_classes)
_model.classifier = nn.Sequential(
    nn.Dropout(0.2),
    nn.Linear(in_features, num_classes)
)

# load weights (strict=False lets it load even if buffers like running stats differ)
_missing, _unexpected = _model.load_state_dict(_state, strict=False)

_model.eval()
model = _model.to(device)


# -------- preprocessing (matches training) --------
def prepare_image(img: Image.Image) -> torch.Tensor:
    img = img.convert('RGB')
    img = img.resize((224, 224))  # match training size

    # to float32 [0,1]
    arr = np.array(img).astype(np.float32) / 255.0

    # Normalize with ImageNet mean/std (same as your training script)
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std

    # HWC -> CHW
    arr = np.transpose(arr, (2, 0, 1))  # CHW

    # to torch tensor with batch dimension
    x = torch.from_numpy(arr).unsqueeze(0)  # [1, 3, 224, 224]
    return x.to(device)


@app.route('/')
def index():
    return render_template('home.html')

@app.route("/charities")
def charities():
    return render_template("charities.html")


@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.get_json() or {}
    img_data = data.get('image_data')
    if not img_data:
        return jsonify({'error': 'No image data provided.'}), 400

    # Remove base64 header if present
    try:
        _, encoded = img_data.split(',', 1)
    except ValueError:
        encoded = img_data

    try:
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes))
    except Exception as e:
        return jsonify({'error': f'Invalid image data: {e}'}), 400

    # Predict (PyTorch forward pass)
    x = prepare_image(img)
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1).cpu().numpy()[0]

    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])

    # Add near the top, after NUM_CLASSES_FALLBACK
    CLASS_NAMES = ["Cardboard", "Glass", "Metal", "Paper", "Plastic", "Trash"]  # adjust order to your training
    TIPS = {
        "Cardboard": "Flatten boxes and keep them dry; remove packing tape if you can.",
        "Glass": "Rinse and remove caps; most programs take bottles and jars only.",
        "Metal": "Rinse cans; crushing is optional but saves space.",
        "Paper": "Keep it clean and dry; no greasy pizza boxes.",
        "Plastic": "Check local rules; #1 and #2 bottles are most widely accepted.",
        "Trash": "This item is not recyclable locally; consider reusing or proper disposal."
    }


    # Map index -> human-readable label safely
    if 0 <= pred_idx < len(CLASS_NAMES):
        label = CLASS_NAMES[pred_idx]
    else:
        label = f"Class_{pred_idx}"  # fallback name if classes mismatch

    tip = TIPS.get(label, "Check local recycling guidelines for your area.")

    return jsonify({'label': label, 'confidence': confidence, 'tip': tip})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
