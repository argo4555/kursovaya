"""Управление сотрудниками: добавление, смена пароля, удаление."""
import re
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import ROLE_NAMES, admin_user, hash_password
from app.database import get_db
from app.models import Ticket, User
from app.templating import templates

router = APIRouter()


def users_page(request: Request, db: Session, user: User, form=None, error=None, message=None):
    users = db.scalars(select(User).order_by(User.role, User.full_name)).all()
    total = dict(db.execute(select(Ticket.user_id, func.sum(Ticket.price)).group_by(Ticket.user_id)).all())
    today = dict(db.execute(select(Ticket.user_id, func.count())
                            .where(Ticket.sold_at >= datetime.combine(date.today(), time.min))
                            .group_by(Ticket.user_id)).all())
    return templates.TemplateResponse(request, "users.html", {
        "user": user, "users": users, "total": total, "today": today, "error": error,
        "message": message or request.query_params.get("msg"),
        "form": form or {"login": "", "full_name": "", "role": "cashier"},
    })


@router.get("/users")
def user_list(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return users_page(request, db, user)


@router.post("/users/add")
def add_user(request: Request, login: str = Form(""), full_name: str = Form(""), role: str = Form(""),
             password: str = Form(""), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    form = {"login": login.strip(), "full_name": " ".join(full_name.split()), "role": role}
    error = None
    if not re.fullmatch(r"[a-z0-9_]{3,30}", form["login"]):
        error = "Логин: от 3 до 30 латинских строчных букв, цифр или «_»"
    elif db.scalar(select(User).where(User.login == form["login"])):
        error = "Сотрудник с таким логином уже есть"
    elif len(form["full_name"].split()) < 2 or len(form["full_name"]) > 100:
        error = "Укажите фамилию и имя сотрудника"
    elif role not in ROLE_NAMES:
        error = "Выберите роль"
    elif len(password) < 4:
        error = "Пароль должен быть не короче 4 символов"
    if error:
        return users_page(request, db, user, form, error)
    db.add(User(login=form["login"], full_name=form["full_name"], role=role, password_hash=hash_password(password)))
    db.commit()
    return RedirectResponse(f"/users?msg=Сотрудник {form['login']} добавлен", status_code=303)


@router.post("/users/{user_id}/password")
def change_password(request: Request, user_id: int, password: str = Form(""),
                    db: Session = Depends(get_db), user: User = Depends(admin_user)):
    target = db.get(User, user_id)
    if target is None:
        return RedirectResponse("/users", status_code=303)
    if len(password) < 4:
        return users_page(request, db, user, error="Новый пароль должен быть не короче 4 символов")
    target.password_hash = hash_password(password)
    db.commit()
    return RedirectResponse(f"/users?msg=Пароль для {target.login} изменён", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(request: Request, user_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    target = db.get(User, user_id)
    if target is None:
        return RedirectResponse("/users", status_code=303)
    if target.id == user.id:
        return users_page(request, db, user, error="Нельзя удалить самого себя")
    if target.tickets:
        return users_page(request, db, user, error="Нельзя удалить кассира, который продавал билеты: продажи должны сохраниться в отчётах")
    db.delete(target)
    db.commit()
    return RedirectResponse("/users?msg=Сотрудник удалён", status_code=303)
