from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import admin_user
from app.database import get_db
from app.models import Film, Screening, Ticket, User
from app.routers.posters import PALETTES
from app.templating import templates

router = APIRouter()

AGE_LIMITS = ["0+", "6+", "12+", "16+", "18+"]
GENRES = list(PALETTES)
FIELDS = ["title", "genre", "year", "duration", "age_limit", "description", "poster_url", "backdrop_url"]


def check_film(form: dict) -> str | None:
    """Проверяет данные фильма. Возвращает текст ошибки или None."""
    if not form["title"] or len(form["title"]) > 150:
        return "Укажите название фильма (до 150 символов)"
    if not form["genre"] or len(form["genre"]) > 50:
        return "Выберите жанр"
    if not form["year"].isdigit() or not 1900 <= int(form["year"]) <= date.today().year + 2:
        return "Год выпуска указан неверно"
    if not form["duration"].isdigit() or not 30 <= int(form["duration"]) <= 300:
        return "Длительность — число минут от 30 до 300"
    if form["age_limit"] not in AGE_LIMITS:
        return "Выберите возрастное ограничение"
    for field, name in (("poster_url", "постер"), ("backdrop_url", "кадр")):
        if form[field] and (not form[field].startswith(("http://", "https://")) or len(form[field]) > 300):
            return f"Ссылка на {name} должна начинаться с http:// или https://"
    return None


def apply(film: Film, form: dict):
    film.title, film.genre, film.age_limit = form["title"], form["genre"], form["age_limit"]
    film.year, film.duration = int(form["year"]), int(form["duration"])
    film.description = form["description"]
    film.poster_url = form["poster_url"] or None
    film.backdrop_url = form["backdrop_url"] or None


def form_page(request, user, form, film=None, error=None):
    return templates.TemplateResponse(request, "film_form.html", {
        "user": user, "form": form, "film": film, "error": error, "genres": GENRES, "ages": AGE_LIMITS,
    })


def read_form(title, genre, year, duration, age_limit, description, poster_url, backdrop_url):
    return {"title": title.strip(), "genre": genre.strip(), "year": year.strip(), "duration": duration.strip(),
            "age_limit": age_limit, "description": description.strip(), "poster_url": poster_url.strip(),
            "backdrop_url": backdrop_url.strip()}


@router.get("/films")
def film_list(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    films = db.scalars(select(Film).order_by(Film.title)).all()
    # Сколько сеансов впереди и сколько билетов продано по каждому фильму
    upcoming = dict(db.execute(select(Screening.film_id, func.count()).where(Screening.start_time >= datetime.now())
                               .group_by(Screening.film_id)).all())
    sold = dict(db.execute(select(Screening.film_id, func.count(Ticket.id)).join(Screening.tickets)
                           .group_by(Screening.film_id)).all())
    return templates.TemplateResponse(request, "films.html", {
        "user": user, "films": films, "upcoming": upcoming, "sold": sold,
        "message": request.query_params.get("msg"), "error": request.query_params.get("err"),
    })


@router.get("/films/new")
def new_film_page(request: Request, user: User = Depends(admin_user)):
    return form_page(request, user, {f: "" for f in FIELDS} | {"age_limit": "12+", "genre": GENRES[0]})


@router.post("/films/new")
def new_film(request: Request, title: str = Form(""), genre: str = Form(""), year: str = Form(""),
             duration: str = Form(""), age_limit: str = Form(""), description: str = Form(""),
             poster_url: str = Form(""), backdrop_url: str = Form(""),
             db: Session = Depends(get_db), user: User = Depends(admin_user)):
    form = read_form(title, genre, year, duration, age_limit, description, poster_url, backdrop_url)
    error = check_film(form)
    if error:
        return form_page(request, user, form, error=error)
    film = Film()
    apply(film, form)
    db.add(film)
    db.commit()
    return RedirectResponse("/films?msg=Фильм добавлен", status_code=303)


@router.get("/films/{film_id}/edit")
def edit_film_page(request: Request, film_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    film = db.get(Film, film_id)
    if film is None:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    form = {f: str(getattr(film, f) or "") for f in FIELDS}
    return form_page(request, user, form, film)


@router.post("/films/{film_id}/edit")
def edit_film(request: Request, film_id: int, title: str = Form(""), genre: str = Form(""), year: str = Form(""),
              duration: str = Form(""), age_limit: str = Form(""), description: str = Form(""),
              poster_url: str = Form(""), backdrop_url: str = Form(""),
              db: Session = Depends(get_db), user: User = Depends(admin_user)):
    film = db.get(Film, film_id)
    if film is None:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    form = read_form(title, genre, year, duration, age_limit, description, poster_url, backdrop_url)
    error = check_film(form)
    if error:
        return form_page(request, user, form, film, error)
    apply(film, form)
    db.commit()
    return RedirectResponse("/films?msg=Изменения сохранены", status_code=303)


@router.post("/films/{film_id}/delete")
def delete_film(film_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    film = db.get(Film, film_id)
    if film is not None:
        if film.screenings:
            return RedirectResponse("/films?err=Нельзя удалить фильм: по нему есть сеансы", status_code=303)
        db.delete(film)
        db.commit()
    return RedirectResponse("/films?msg=Фильм удалён", status_code=303)
