import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def hash_password(password: str) -> str:
    """Возвращает хеш пароля в виде «соль:хеш»."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет, что пароль соответствует сохранённому хешу."""
    salt_hex, digest_hex = password_hash.split(":")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


class NotLoggedIn(Exception):
    """Пользователь не выполнил вход."""


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Возвращает вошедшего сотрудника или отправляет на страницу входа."""
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise NotLoggedIn()
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    """Пропускает только администратора."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступно только администратору")
    return user
