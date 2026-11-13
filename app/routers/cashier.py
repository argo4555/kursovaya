"""Касса: плитки сеансов, схема зала, продажа билетов, печать, продажи кассира за смену."""
import secrets
import string
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import sales_user
from app.database import get_db
from app.halls import HALLS, capacity
from app.models import Screening, Ticket, User
from app.templating import templates

router = APIRouter()

MAX_SEATS = 10                          # мест в одной покупке
SALE_AFTER_START = timedelta(minutes=15)  # продажа ещё 15 минут после начала сеанса


def sold_counts(db: Session, screening_ids) -> dict[int, int]:
    """Количество проданных билетов по каждому сеансу."""
    rows = db.execute(select(Ticket.screening_id, func.count())
                      .where(Ticket.screening_id.in_(screening_ids))
                      .group_by(Ticket.screening_id)).all()
    return dict(rows)


def can_sell(screening: Screening) -> bool:
    return datetime.now() < screening.start_time + SALE_AFTER_START


@router.get("/")
def board(request: Request, d: int = 0, db: Session = Depends(get_db), user: User = Depends(sales_user)):
    """Главный экран кассира: фильмы дня плитками, на плитке — время сеансов и свободные места."""
    d = min(max(d, 0), 2)
    day = date.today() + timedelta(days=d)
    start, end = datetime.combine(day, time.min), datetime.combine(day, time.max)
    screenings = db.scalars(select(Screening).where(Screening.start_time.between(start, end))
                            .order_by(Screening.start_time)).all()
    sold = sold_counts(db, [s.id for s in screenings])

    # Группируем сеансы по фильмам; первым идёт фильм с ближайшим доступным сеансом
    films = {}
    for s in screenings:
        free = capacity(s.hall) - sold.get(s.id, 0)
        films.setdefault(s.film, []).append({"s": s, "free": free, "open": can_sell(s) and free > 0})
    tiles = sorted(films.items(), key=lambda item: min(
        (x["s"].start_time for x in item[1] if x["open"]), default=datetime.max))

    # Сводка кассира за сегодня для цветных плиток
    today_start = datetime.combine(date.today(), time.min)
    my_count, my_sum = db.execute(select(func.count(), func.coalesce(func.sum(Ticket.price), 0))
                                  .where(Ticket.user_id == user.id, Ticket.sold_at >= today_start)).one()
    upcoming = next((s for s in screenings if s.start_time >= datetime.now()), None)

    return templates.TemplateResponse(request, "board.html", {
        "user": user, "tiles": tiles, "d": d, "days": [date.today() + timedelta(days=i) for i in range(3)],
        "my_count": my_count, "my_sum": my_sum, "upcoming": upcoming,
        "free_total": sum(x["free"] for v in films.values() for x in v if x["open"]),
    })


def sell_page(request, db, user, screening, error=None, picked=""):
    taken = {(t.row_num, t.seat_num) for t in screening.tickets}
    return templates.TemplateResponse(request, "sell.html", {
        "user": user, "s": screening, "hall": HALLS[screening.hall], "taken": taken,
        "free": capacity(screening.hall) - len(taken), "error": error, "picked": picked,
        "can_sell": can_sell(screening), "max_seats": MAX_SEATS,
    })


@router.get("/sell/{screening_id}")
def sell_form(request: Request, screening_id: int, db: Session = Depends(get_db), user: User = Depends(sales_user)):
    screening = db.get(Screening, screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="Сеанс не найден")
    return sell_page(request, db, user, screening)


def parse_seats(value: str, hall: dict):
    """Разбирает строку «3-5,3-6» в список (ряд, место). Возвращает (места, ошибка)."""
    seats = []
    for part in filter(None, value.split(",")):
        row, _, seat = part.partition("-")
        if not (row.isdigit() and seat.isdigit()):
            return [], "Неверный формат выбранных мест"
        row, seat = int(row), int(seat)
        if not (1 <= row <= hall["rows"] and 1 <= seat <= hall["seats"]):
            return [], "Выбрано место, которого нет в зале"
        seats.append((row, seat))
    if not seats:
        return [], "Выберите хотя бы одно место на схеме зала"
    if len(set(seats)) != len(seats):
        return [], "Одно место выбрано дважды"
    if len(seats) > MAX_SEATS:
        return [], f"В одной покупке не больше {MAX_SEATS} билетов"
    return seats, None


@router.post("/sell/{screening_id}")
def sell(
    request: Request,
    screening_id: int,
    seats: str = Form(""),
    payment: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(sales_user),
):
    screening = db.get(Screening, screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="Сеанс не найден")
    if not can_sell(screening):
        return sell_page(request, db, user, screening, "Продажа на этот сеанс закрыта")
    places, error = parse_seats(seats, HALLS[screening.hall])
    if error is None and payment not in ("cash", "card"):
        error = "Выберите способ оплаты"
    taken = {(t.row_num, t.seat_num) for t in screening.tickets}
    if error is None and any(p in taken for p in places):
        error = "Часть выбранных мест уже продана — выберите другие"
    if error:
        return sell_page(request, db, user, screening, error, seats)

    # Все билеты покупки получают общий код заказа и сохраняются одной транзакцией
    code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    for row, seat in places:
        db.add(Ticket(screening=screening, row_num=row, seat_num=seat, price=screening.price,
                      payment=payment, order_code=code, cashier=user))
    try:
        db.commit()
    except IntegrityError:
        # Ограничение UNIQUE в базе: место успели продать с другой кассы
        db.rollback()
        db.refresh(screening)
        return sell_page(request, db, user, screening, "Это место только что продали с другой кассы — выберите другое")
    return RedirectResponse(f"/order/{code}", status_code=303)


@router.get("/order/{code}")
def order(request: Request, code: str, db: Session = Depends(get_db), user: User = Depends(sales_user)):
    """Билеты одной покупки — для печати."""
    tickets = db.scalars(select(Ticket).where(Ticket.order_code == code)
                         .order_by(Ticket.row_num, Ticket.seat_num)).all()
    if not tickets:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return templates.TemplateResponse(request, "order.html", {
        "user": user, "tickets": tickets, "code": code, "s": tickets[0].screening,
        "total": sum(t.price for t in tickets), "fresh": request.query_params.get("new") is None,
    })


@router.get("/my")
def my_sales(request: Request, db: Session = Depends(get_db), user: User = Depends(sales_user)):
    """Продажи текущего кассира за сегодня, сгруппированные по заказам."""
    start = datetime.combine(date.today(), time.min)
    tickets = db.scalars(select(Ticket).where(Ticket.user_id == user.id, Ticket.sold_at >= start)
                         .order_by(Ticket.sold_at.desc())).all()
    orders = {}
    for t in tickets:
        orders.setdefault(t.order_code, []).append(t)
    total = sum(t.price for t in tickets)
    card = sum(t.price for t in tickets if t.payment == "card")
    return templates.TemplateResponse(request, "my.html", {
        "user": user, "orders": orders, "count": len(tickets), "total": total,
        "card": card, "cash": total - card,
    })
