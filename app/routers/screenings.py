from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import admin_user
from app.database import get_db
from app.halls import CLEANING_MINUTES, HALLS, capacity
from app.models import Film, Screening, Ticket, User
from app.templating import templates

router = APIRouter()

DAY_START, DAY_HOURS = 10, 14   # таймлайн с 10:00 до 24:00


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def schedule_page(request: Request, db: Session, user: User, day: date, form=None, error=None, message=None):
    start = datetime.combine(day, time.min)
    rows = db.execute(select(Screening, func.count(Ticket.id)).outerjoin(Screening.tickets)
                      .where(Screening.start_time.between(start, start + timedelta(days=1)))
                      .group_by(Screening.id).order_by(Screening.start_time)).all()
    origin = datetime.combine(day, time(DAY_START))
    lanes = {hall: [] for hall in HALLS}
    for s, sold in rows:
        left = (s.start_time - origin).total_seconds() / 60 / (DAY_HOURS * 60) * 100
        width = s.film.duration / (DAY_HOURS * 60) * 100
        lanes[s.hall].append({"s": s, "sold": sold, "left": max(left, 0), "width": min(width, 100 - max(left, 0)),
                              "pct": round(sold / capacity(s.hall) * 100)})
    films = db.scalars(select(Film).order_by(Film.title)).all()
    return templates.TemplateResponse(request, "screenings.html", {
        "user": user, "day": day, "lanes": lanes, "films": films, "error": error, "message": message,
        "days": [date.today() + timedelta(days=i) for i in range(7)],
        "hours": list(range(DAY_START, DAY_START + DAY_HOURS + 1)),
        "form": form or {"film_id": "", "hall": "1", "time": "18:00", "price": "400"},
        "total": len(rows),
    })


@router.get("/screenings")
def schedule(request: Request, day: str = "", db: Session = Depends(get_db), user: User = Depends(admin_user)):
    msg = request.query_params.get("msg")
    return schedule_page(request, db, user, parse_day(day), message=msg)


def check_screening(db: Session, film: Film | None, hall: str, start: datetime | None, price: str) -> str | None:
    """Проверяет новый сеанс. Возвращает текст ошибки или None."""
    if film is None or not hall.isdigit() or int(hall) not in HALLS or start is None:
        return "Заполните все поля сеанса"
    if not price.isdigit() or not 50 <= int(price) <= 5000:
        return "Цена — число от 50 до 5000 рублей"
    if start < datetime.now():
        return "Нельзя добавить сеанс в прошлом"
    if not time(9, 0) <= start.time() <= time(23, 30):
        return "Сеансы начинаются с 09:00 до 23:30"
    # Сеанс не должен пересекаться с другими в этом зале (с учётом уборки зала)
    end = start + timedelta(minutes=film.duration + CLEANING_MINUTES)
    same_day = db.scalars(select(Screening).where(
        Screening.hall == int(hall),
        Screening.start_time.between(start - timedelta(hours=6), end))).all()
    for other in same_day:
        other_end = other.end_time + timedelta(minutes=CLEANING_MINUTES)
        if other.start_time < end and start < other_end:
            return (f"Зал занят: «{other.film.title}» с {other.start_time:%H:%M} до {other.end_time:%H:%M}, "
                    f"плюс {CLEANING_MINUTES} мин на уборку")
    return None


@router.post("/screenings/add")
def add_screening(
    request: Request,
    day: str = Form(""),
    film_id: str = Form(""),
    hall: str = Form(""),
    start: str = Form(""),
    price: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    selected = parse_day(day)
    form = {"film_id": film_id, "hall": hall, "time": start, "price": price.strip()}
    film = db.get(Film, int(film_id)) if film_id.isdigit() else None
    try:
        start_time = datetime.combine(selected, time.fromisoformat(start))
    except ValueError:
        start_time = None
    error = check_screening(db, film, hall, start_time, price.strip())
    if error:
        return schedule_page(request, db, user, selected, form, error)
    db.add(Screening(film=film, hall=int(hall), start_time=start_time, price=int(price)))
    db.commit()
    return RedirectResponse(f"/screenings?day={selected}&msg=Сеанс добавлен", status_code=303)


@router.post("/screenings/{screening_id}/delete")
def delete_screening(request: Request, screening_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    screening = db.get(Screening, screening_id)
    if screening is None:
        return RedirectResponse("/screenings", status_code=303)
    day = screening.start_time.date()
    if screening.tickets:
        return schedule_page(request, db, user, day, error="Нельзя удалить сеанс: на него проданы билеты")
    db.delete(screening)
    db.commit()
    return RedirectResponse(f"/screenings?day={day}&msg=Сеанс удалён", status_code=303)
