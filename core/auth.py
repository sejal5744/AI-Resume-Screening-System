"""User Management Module: registration, login and password hashing (bcrypt)."""
import re

import bcrypt

import config
from core import database as db

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def validate_registration(name: str, email: str, password: str) -> str | None:
    """Return an error message, or None when the input is valid."""
    if not name.strip():
        return "Name is required."
    if not EMAIL_RE.match(email.strip()):
        return "Enter a valid email address."
    if len(password) < 8 or not re.search(r"\d", password) or not re.search(r"[A-Za-z]", password):
        return "Password must be at least 8 characters and contain letters and digits."
    if db.get_user_by_email(email):
        return "An account with this email already exists."
    return None


def register(name: str, email: str, password: str, role: str = "recruiter") -> int:
    user_id = db.create_user(name.strip(), email, hash_password(password), role)
    db.log_activity(user_id, "register", f"New {role} account")
    return user_id


def login(email: str, password: str) -> dict | None:
    user = db.get_user_by_email(email)
    if user and verify_password(password, user["password"]):
        db.log_activity(user["user_id"], "login", "Successful login")
        user.pop("password", None)
        return user
    if user:
        db.log_activity(user["user_id"], "login_failed", "Wrong password")
    return None


def ensure_default_admin():
    if db.count_users() == 0:
        register("Administrator", config.DEFAULT_ADMIN_EMAIL, config.DEFAULT_ADMIN_PASSWORD, role="admin")
