from flask import Flask, request, jsonify, render_template
import base64, json
from io import BytesIO
from PIL import Image
import numpy as np

# --- PyTorch ---
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models
from torchvision.models import EfficientNet_B0_Weights
# ---------------

from policy_engine import decide_action

app = Flask(__name__)

# ---------- Config ----------
STATE_PATH = "best_efficientnet_model.pth"
CLASS_NAMES_PATH = "artifacts/class_names.json"   # will be used if present
NUM_CLASSES_FALLBACK = 6
THRESH = 0.75  # abstain threshold; tune later
# ----------------------------

# -------- helpers (typed + robust) --------
def infer_num_classes_from_state(state_dict: dict) -> int | None:
    for k, v in state_dict.items():
        if k.endswith("classifier.1.weight") and hasattr(v, "shape"):
            return int(v.shape[0])
    for k, v in state_dict.items():
        if k.endswith("classifier.1.bias") and hasattr(v, "shape"):
            return int(v.shape[0])
    return None

def get_in_features(classifier: nn.Module) -> int:
    if isinstance(classifier, nn.Linear):
        return int(classifier.in_features)
    if isinstance(classifier, nn.Sequential):
        for mod in reversed(classifier):
            if isinstance(mod, nn.Linear):
                return int(mod.in_features)
    return 1280

def load_class_names(path: str) -> list[str]:
    try:
        with open(path, "r") as f:
            classes = json.load(f)
        if isinstance(classes, list) and all(isinstance(x, str) for x in classes):
            return classes
    except Exception:
        pass
    return ["Cardboard", "Glass", "Metal", "Paper", "Plastic", "Trash"]

# -------- build model + load weights --------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_state = torch.load(STATE_PATH, map_location="cpu")

num_classes_inferred = infer_num_classes_from_state(_state)
num_classes = num_classes_inferred if num_classes_inferred is not None else int(NUM_CLASSES_FALLBACK)

_model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
in_features = get_in_features(_model.classifier)
_model.classifier = nn.Sequential(nn.Dropout(0.2), nn.Linear(in_features, num_classes))

_missing, _unexpected = _model.load_state_dict(_state, strict=False)
_model.eval()
model = _model.to(device)

CLASS_NAMES = load_class_names(CLASS_NAMES_PATH)

# -------- preprocessing (matches training) --------
def prepare_image(img: Image.Image) -> torch.Tensor:
    img = img.convert('RGB').resize((224, 224))
    arr = np.array(img).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))  # CHW
    return torch.from_numpy(arr).unsqueeze(0).to(device)

TIPS = {
    "Cardboard": "Flatten boxes and keep them dry; remove packing tape if you can.",
    "Glass": "Rinse and remove caps; most programs take bottles and jars only.",
    "Metal": "Rinse cans; crushing is optional but saves space.",
    "Paper": "Keep it clean and dry; no greasy pizza boxes.",
    "Plastic": "#1 and #2 bottles are most widely accepted.",
    "Trash": "This item is not recyclable locally; consider reusing or proper disposal.",
    "Unsure": "Try another angle or better light, or choose from a list."
}

# ----------------- Routes -----------------
@app.route('/')
def index():
    return render_template('home.html')

@app.route("/charities")
def charities():
    return render_template("charities.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "device": str(device),
        "classes": CLASS_NAMES,
        "missing_keys": len(_missing),
        "unexpected_keys": len(_unexpected)
    })

@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.get_json() or {}
    img_data = data.get('image_data')
    if not img_data:
        return jsonify({'error': 'No image data provided.'}), 400

    try:
        _, encoded = img_data.split(',', 1)
    except ValueError:
        encoded = img_data

    try:
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes))
    except Exception as e:
        return jsonify({'error': f'Invalid image data: {e}'}), 400

    x = prepare_image(img)
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1).cpu().numpy()[0]

    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])
    label = CLASS_NAMES[pred_idx] if 0 <= pred_idx < len(CLASS_NAMES) else f"Class_{pred_idx}"

    attrs = data.get("attrs") or {}       # e.g., {"rigid": true, "film": false, "food_soiled": false}
    user_city = data.get("city") or "default"

    if confidence < THRESH:
        return jsonify({
            "material": label,
            "action": "Unsure",
            "why": "Low confidence prediction. Try another angle or better light.",
            "confidence": confidence,
            "confidence_text": f"{confidence*100:.1f} % (low)",
            "tip": TIPS.get("Unsure"),
            "abstained": True
        })

    action, why = decide_action(label, attrs, user_city)

    return jsonify({
        "material": label,
        "action": action,
        "why": why,
        "confidence": confidence,
        "confidence_text": f"{confidence*100:.1f} % Confidence Score",
        "tip": TIPS.get(label, "Check local recycling guidelines for your area."),
        "abstained": False
    })

# ------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
