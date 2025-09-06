# models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, pw: str) -> None:
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

class ClassificationLog(db.Model):
    __tablename__ = "classification_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float)
    city = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

def normalize_label(raw: str) -> str:
    s = (raw or "").lower()
    if "recycl" in s: return "Recyclable"
    if "compost" in s or "organic" in s: return "Compost"
    if "landfill" in s or "trash" in s or "garbage" in s: return "Landfill"
    if "unsure" in s or "abstain" in s: return "Unsure"
    return "Other"
