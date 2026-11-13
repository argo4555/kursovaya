from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import HOME, verify_password
from app.database import get_db
from app.models import Film, User
from app.templating import templates

router = APIRouter()


def login_page(request: Request, db: Session, login: str = "", error: str | None = None):
    # Постеры фильмов для фоновой «стены»
    films = db.scalars(select(Film).order_by(Film.id)).all()
    return templates.TemplateResponse(request, "login.html", {
        "login_error": error, "login": login, "wall": (films * 4)[:36],
    })


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    return login_page(request, db)


@router.post("/login")
def login(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.login == login.strip()))
    if user is None or not verify_password(password, user.password_hash):
        return login_page(request, db, login, "Неверный логин или пароль")
    # Запоминаем сотрудника в сессии и открываем стартовую страницу его роли
    request.session["user_id"] = user.id
    return RedirectResponse(HOME[user.role], status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
