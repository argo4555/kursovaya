from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import admin_user
from app.database import get_db
from app.models import Film, User
from app.templating import templates

router = APIRouter()

EMPTY_FORM = {"title": "", "genre": "", "duration": "", "age_limit": ""}


def films_page(request: Request, db: Session, user: User, form=None, error=None):
    films = db.scalars(select(Film).order_by(Film.title)).all()
    return templates.TemplateResponse(request, "films.html", {
        "user": user,
        "films": films,
        "form": form or EMPTY_FORM,
        "error": error,
    })


@router.get("/films")
def film_list(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return films_page(request, db, user)


@router.post("/films/add")
def add_film(
    request: Request,
    title: str = Form(""),
    genre: str = Form(""),
    duration: str = Form(""),
    age_limit: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    form = {"title": title, "genre": genre, "duration": duration, "age_limit": age_limit}
    if not title.strip() or not genre.strip() or not duration.strip() or not age_limit:
        return films_page(request, db, user, form, "Заполните все поля фильма")
    if not duration.strip().isdigit() or int(duration) == 0:
        return films_page(request, db, user, form, "Длительность должна быть положительным числом")

    db.add(Film(title=title.strip(), genre=genre.strip(), duration=int(duration), age_limit=age_limit))
    db.commit()
    return RedirectResponse("/films", status_code=303)


@router.post("/films/{film_id}/delete")
def delete_film(
    request: Request,
    film_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    film = db.get(Film, film_id)
    if film is not None:
        if film.screenings:
            return films_page(request, db, user, error="Нельзя удалить фильм: на него назначены сеансы")
        db.delete(film)
        db.commit()
    return RedirectResponse("/films", status_code=303)
