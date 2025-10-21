# app.py
from datetime import datetime, timedelta
from io import BytesIO
import base64, json
import random  # <-- for random tip selection

from flask import Flask, request, jsonify, render_template
from sqlalchemy import text, func
from PIL import Image
import numpy as np

# Torch
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models
from torchvision.models import EfficientNet_B0_Weights

# Local modules
from extensions import db, login_manager
from models import User, ClassificationLog, normalize_label
from auth import auth_bp, login_required, current_user  # re-exported from auth
from auth import auth_bp, api_logout as bp_api_logout

from policy_engine import decide_action

# ---------------- App & Config ----------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me"               # set via env var in prod
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recycloai.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"  # type: ignore[assignment]

# ---------------- SQLite schema repair ----------------
def _table_exists(conn, name: str) -> bool:
    row = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:n"
    ), {"n": name}).fetchone()
    return row is not None

def _cols(conn, name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({name})")).fetchall()
    return {r[1] for r in rows}  # r[1] = column name

def ensure_sqlite_schema(app: Flask):
    """
    Make the live recycloai.db compatible with our models without losing data.
    - If a legacy 'user' table exists, rename to 'users' (if 'users' missing).
    - Create missing tables.
    - Add any missing columns on existing tables.
    """
    with app.app_context():
        with db.engine.begin() as conn:
            # 1) Rename legacy table 'user' -> 'users' if needed
            has_users = _table_exists(conn, "users")
            has_user  = _table_exists(conn, "user")
            if has_user and not has_users:
                conn.execute(text("ALTER TABLE user RENAME TO users"))

        # 2) Create missing tables (no-op if they already exist)
        db.create_all()

        with db.engine.begin() as conn:
            # 3) Add missing columns on 'users' (or legacy 'user' if both exist)
            target_user_table = "users" if _table_exists(conn, "users") else ("user" if _table_exists(conn, "user") else None)
            if target_user_table:
                ucols = _cols(conn, target_user_table)
                if "email" not in ucols:
                    conn.execute(text(f"ALTER TABLE {target_user_table} ADD COLUMN email TEXT"))
                if "name" not in ucols:
                    conn.execute(text(f"ALTER TABLE {target_user_table} ADD COLUMN name TEXT"))
                if "password_hash" not in ucols:
                    conn.execute(text(f"ALTER TABLE {target_user_table} ADD COLUMN password_hash TEXT"))

            # 4) Ensure 'classification_logs' table exists and has all columns
            if not _table_exists(conn, "classification_logs"):
                # create_all should have created it; if not, force-create
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS classification_logs (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        label TEXT,
                        confidence REAL,
                        city TEXT,
                        created_at DATETIME
                    )
                """))

            lcols = _cols(conn, "classification_logs")
            if "user_id" not in lcols:
                conn.execute(text("ALTER TABLE classification_logs ADD COLUMN user_id INTEGER"))
            if "label" not in lcols:
                conn.execute(text("ALTER TABLE classification_logs ADD COLUMN label TEXT"))
            if "confidence" not in lcols:
                conn.execute(text("ALTER TABLE classification_logs ADD COLUMN confidence REAL"))
            if "city" not in lcols:
                conn.execute(text("ALTER TABLE classification_logs ADD COLUMN city TEXT"))
            if "created_at" not in lcols:
                conn.execute(text("ALTER TABLE classification_logs ADD COLUMN created_at DATETIME"))

# ---------------- Model / Inference setup ----------------
STATE_PATH = "best_efficientnet_model.pth"
CLASS_NAMES_PATH = "artifacts/class_names.json"
NUM_CLASSES_FALLBACK = 6
THRESH = 0.75

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_state = torch.load(STATE_PATH, map_location="cpu")

def _infer_num_classes(state_dict: dict) -> int | None:
    for k, v in state_dict.items():
        if k.endswith("classifier.1.weight") and hasattr(v, "shape"):
            return int(v.shape[0])
    for k, v in state_dict.items():
        if k.endswith("classifier.1.bias") and hasattr(v, "shape"):
            return int(v.shape[0])
    return None

num_classes = _infer_num_classes(_state) or NUM_CLASSES_FALLBACK

_model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
# grab in_features
def _in_features(classifier: nn.Module) -> int:
    if isinstance(classifier, nn.Linear):
        return int(classifier.in_features)
    if isinstance(classifier, nn.Sequential):
        for mod in reversed(classifier):
            if isinstance(mod, nn.Linear):
                return int(mod.in_features)
    return 1280

in_features = _in_features(_model.classifier)
_model.classifier = nn.Sequential(nn.Dropout(0.2), nn.Linear(in_features, num_classes))
_missing, _unexpected = _model.load_state_dict(_state, strict=False)
_model.eval()
model = _model.to(device)

def _load_class_names(path: str) -> list[str]:
    try:
        with open(path, "r") as f:
            classes = json.load(f)
        if isinstance(classes, list) and all(isinstance(x, str) for x in classes):
            return classes
    except Exception:
        pass
    return ["Cardboard", "Glass", "Metal", "Paper", "Plastic", "Trash"]

CLASS_NAMES = _load_class_names(CLASS_NAMES_PATH)

def prepare_image(img: Image.Image) -> torch.Tensor:
    img = img.convert('RGB').resize((224, 224))
    arr = np.array(img).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))
    return torch.from_numpy(arr).unsqueeze(0).to(device)

# ---------------- Tips (3 per class/action) + random selection ----------------
TIPS = {
    "Cardboard": [
        "Flatten boxes to save bin space and keep them dry.",
        "Remove excessive tape and labels if possible.",
        "Large boxes? Cut them down to 2×2 ft pieces."
    ],
    "Glass": [
        "Rinse bottles and jars; remove caps and lids.",
        "Only bottles and jars are accepted in most cities.",
        "Avoid breaking glass—loose shards can contaminate."
    ],
    "Metal": [
        "Rinse food and beverage cans before recycling.",
        "Crushing cans is optional but saves space.",
        "Foil is OK if it’s clean and balled up."
    ],
    "Paper": [
        "Keep paper clean and dry; wet paper belongs in trash/compost per city rules.",
        "No greasy pizza boxes unless your city allows food-soiled paper in organics.",
        "Remove plastic windows from envelopes if easy; not required in many programs."
    ],
    "Plastic": [
        "Rinse and empty; caps on or off depends on your city (on is common).",
        "Prioritize #1 and #2 bottles and jugs—most widely accepted.",
        "If it’s soft, scrunchable film, take it to store drop-off (not curbside)."
    ],
    "Trash": [
        "This item isn’t accepted curbside—avoid wish-cycling.",
        "When in doubt, check your city’s A-Z guide for proper disposal.",
        "Consider reusing the item or choosing a reusable alternative next time."
    ],
    "Unsure": [
        "Try another angle, better lighting, or remove background clutter.",
        "Manually select a material or add attributes like ‘greasy/wet’.",
        "Check your local recycling guide for specific items."
    ],
}

ACTION_TIPS = {
    "Recyclable": [
        "Rinse/empty items and keep them dry to avoid contamination.",
        "Don’t bag recyclables—place them loose in the cart.",
        "If a piece is smaller than a credit card, it may not get captured."
    ],
    "Compost": [
        "Remove plastic liners or stickers; only food-soiled fiber belongs.",
        "Tear large pieces into smaller bits to speed up composting.",
        "No plastics, glass, or metal in organics—even if ‘biodegradable’."
    ],
    "Landfill": [
        "If it’s not accepted locally, place it in trash—don’t wish-cycle.",
        "Reduce and reuse where possible to cut landfill waste.",
        "Bundle messy trash to prevent leaks and pests."
    ],
    "Unsure": TIPS["Unsure"],  # reuse same three
}

def _pick_from_list(items: list[str]) -> str:
    """Pick a tip based on a random number from 1 to 3 (index 0..2)."""
    if not items:
        return "Check local recycling guidelines for your area."
    n = random.randint(1, 3)  # user request: choose a random number from 1..3
    # If the list has fewer than 3 items, wrap safely
    idx = (n - 1) % len(items)
    return items[idx]

def _tip_for(label: str | None, action: str | None) -> str:
    """
    Case-insensitive material tip lookup with random choice among 3 tips.
    Fallback to action-level tips, then to a generic default.
    """
    # Try material tips (case-insensitive)
    if label:
        key = label.strip()
        if key in TIPS:
            return _pick_from_list(TIPS[key])
        low = key.lower()
        for k in TIPS.keys():
            if k.lower() == low:
                return _pick_from_list(TIPS[k])
    # Fallback to action-level tips
    if action and action in ACTION_TIPS:
        return _pick_from_list(ACTION_TIPS[action])
    return "Check local recycling guidelines for your area."

# ---------------- Blueprints ----------------
app.register_blueprint(auth_bp)  # /login, /signup, /api/logout

# ---- add the alias RIGHT AFTER blueprint registration ----
@app.route("/api/logout", methods=["POST"], endpoint="api_logout")
def api_logout_alias():
    return bp_api_logout()

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("progress.html")

# ---------------- Pages ----------------
@app.route("/", endpoint="index")
def home():
    return render_template("home.html")  # or "index.html" if that's your file

# --- keep this public ---
@app.route("/charities")
def charities():
    return render_template("charities.html")

@app.route("/progress")
@login_required
def progress():
    return render_template("progress.html")

# ---------------- Health ----------------
@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "device": str(device),
        "classes": CLASS_NAMES,
        "missing_keys": len(_missing),
        "unexpected_keys": len(_unexpected)
    })

# ---------------- Inference ----------------
@app.route("/process_image", methods=["POST"])
def process_image():
    data = request.get_json() or {}
    img_data = data.get("image_data")
    if not img_data:
        return jsonify({"error": "No image data provided."}), 400

    try:
        _, encoded = img_data.split(",", 1)
    except ValueError:
        encoded = img_data

    try:
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes))
    except Exception as e:
        return jsonify({"error": f"Invalid image data: {e}"}), 400

    x = prepare_image(img)
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1).cpu().numpy()[0]

    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])
    label = CLASS_NAMES[pred_idx] if 0 <= pred_idx < len(CLASS_NAMES) else f"Class_{pred_idx}"

    attrs = data.get("attrs") or {}
    user_city = data.get("city") or "default"

    # abstain
    if confidence < 0.75:
        action = "Unsure"
        resp = {
            "material": label,
            "action": action,
            "why": "Low confidence prediction. Try another angle or better light.",
            "confidence": confidence,
            "confidence_text": f"{confidence*100:.1f} % (low)",
            "tip": _tip_for("Unsure", "Unsure"),
            "abstained": True
        }
        try:
            if current_user.is_authenticated:
                db.session.add(ClassificationLog(
                    user_id=current_user.id,
                    label=normalize_label(action),
                    confidence=confidence,
                    city=user_city
                ))
                db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify(resp)

    # policy decision
    action, why = decide_action(label, attrs, user_city)

    # log per-user
    try:
        if current_user.is_authenticated:
            db.session.add(ClassificationLog(
                user_id=current_user.id,
                label=normalize_label(action),
                confidence=confidence,
                city=user_city
            ))
            db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({
        "material": label,
        "action": action,
        "why": why,
        "confidence": confidence,
        "confidence_text": f"{confidence*100:.1f} % Confidence Score",
        "tip": _tip_for(label, action),
        "abstained": False
    })

# ---------------- Progress APIs ----------------
@app.route("/api/progress/summary", methods=["GET"])
@login_required
def api_progress_summary():
    # overall totals
    totals = {"Recyclable": 0, "Compost": 0, "Landfill": 0, "Unsure": 0, "Other": 0}
    rows = (db.session.query(ClassificationLog.label, func.count())
            .filter(ClassificationLog.user_id == current_user.id)
            .group_by(ClassificationLog.label).all())
    for label, cnt in rows:
        totals[normalize_label(label)] = cnt

    # last 14 days
    today = datetime.utcnow().date()
    since = today - timedelta(days=13)
    since_dt = datetime.combine(since, datetime.min.time())

    by_day = {(since + timedelta(days=i)).isoformat():
              {"Recyclable":0,"Compost":0,"Landfill":0,"Unsure":0,"Other":0}
              for i in range(14)}

    per = (db.session.query(
              text("date(created_at) as day"),
              ClassificationLog.label,
              func.count().label("cnt"))
           .filter(ClassificationLog.user_id == current_user.id)
           .filter(ClassificationLog.created_at >= since_dt)
           .group_by(text("day"), ClassificationLog.label)
           .all())

    for day, label, cnt in per:
        k = str(day)
        if k in by_day:
            by_day[k][normalize_label(label)] += cnt

    total = sum(totals.values())
    return jsonify({"ok": True, "total": total, "totals": totals, "per_day": by_day})

@app.route("/api/progress/logs", methods=["GET"])
@login_required
def api_progress_logs():
    limit = min(int(request.args.get("limit", 200)), 1000)
    logs = (ClassificationLog.query
            .filter_by(user_id=current_user.id)
            .order_by(ClassificationLog.created_at.desc())
            .limit(limit).all())
    return jsonify({
        "ok": True,
        "logs": [{
            "id": l.id,
            "ts": l.created_at.isoformat(),
            "label": l.label,
            "confidence": l.confidence,
            "city": l.city
        } for l in logs]
    })

@app.route("/api/logs", methods=["DELETE"])
@login_required
def api_clear_logs():
    ClassificationLog.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})

# ---------------- Main ----------------
if __name__ == "__main__":
    ensure_sqlite_schema(app)   # repair/align existing DB
    app.run(debug=True)
