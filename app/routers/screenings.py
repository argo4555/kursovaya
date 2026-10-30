from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import admin_user
from app.database import get_db
from app.models import Film, Screening, User
from app.templating import templates

router = APIRouter()

EMPTY_FORM = {"film_id": "", "hall": "", "start_time": "", "price": ""}


def screenings_page(request: Request, db: Session, user: User, form=None, error=None):
    screenings = db.scalars(select(Screening).order_by(Screening.start_time)).all()
    films = db.scalars(select(Film).order_by(Film.title)).all()
    return templates.TemplateResponse(request, "screenings.html", {
        "user": user,
        "screenings": screenings,
        "films": films,
        "form": form or EMPTY_FORM,
        "error": error,
    })


@router.get("/screenings")
def screening_list(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    return screenings_page(request, db, user)


@router.post("/screenings/add")
def add_screening(
    request: Request,
    film_id: str = Form(""),
    hall: str = Form(""),
    start_time: str = Form(""),
    price: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    form = {"film_id": film_id, "hall": hall, "start_time": start_time, "price": price}
    if not film_id or not hall or not start_time or not price.strip():
        return screenings_page(request, db, user, form, "Заполните все поля сеанса")
    if not price.strip().isdigit() or int(price) == 0:
        return screenings_page(request, db, user, form, "Цена должна быть положительным числом")

    screening = Screening(
        film_id=int(film_id),
        hall=int(hall),
        # Поле datetime-local присылает дату в виде 2026-11-01T18:30
        start_time=datetime.fromisoformat(start_time),
        price=int(price),
    )
    db.add(screening)
    db.commit()
    return RedirectResponse("/screenings", status_code=303)


@router.post("/screenings/{screening_id}/delete")
def delete_screening(
    request: Request,
    screening_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    screening = db.get(Screening, screening_id)
    if screening is not None:
        if screening.tickets:
            return screenings_page(request, db, user, error="Нельзя удалить сеанс: на него проданы билеты")
        db.delete(screening)
        db.commit()
    return RedirectResponse("/screenings", status_code=303)
