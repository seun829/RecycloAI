# auth.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        if request.is_json:
            return jsonify({"ok": False, "error": "Invalid credentials"}), 401
        return render_template("login.html", error="Invalid credentials"), 401
    login_user(user)
    if request.is_json:
        return jsonify({"ok": True, "user": {"email": user.email, "name": user.name}})
    return redirect(url_for("home"))

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    name = data.get("name") or ""
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"ok": False, "error": "Email already registered"}), 409
    u = User(email=email, name=name)
    u.set_password(password)
    db.session.add(u); db.session.commit()
    return jsonify({"ok": True})

@auth_bp.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})

@auth_bp.route("/api/reset", methods=["POST"])
def api_reset():
    return jsonify({"ok": True})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout_post():
  logout_user()
  return jsonify({"ok": True}), 200

@auth_bp.route("/logout", methods=["GET"])
@login_required
def logout_get():
  logout_user()
  return redirect("/")


