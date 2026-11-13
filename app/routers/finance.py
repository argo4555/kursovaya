"""Финансовые сводки для бухгалтера (и администратора)."""
import csv
import io
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth import finance_user
from app.database import get_db
from app.halls import HALLS, capacity
from app.models import Film, Screening, Ticket, User
from app.templating import templates

router = APIRouter()

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_period(period: str, date_from: str, date_to: str):
    """Возвращает (начало, конец, подпись) периода. По умолчанию — последние 7 дней."""
    today = date.today()
    if period == "30":
        return today - timedelta(days=29), today, "30 дней"
    if period == "month":
        return today.replace(day=1), today, "этот месяц"
    if period == "custom":
        try:
            start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
            if start <= end:
                return start, end, "период"
        except ValueError:
            pass
    return today - timedelta(days=6), today, "7 дней"


def totals(db: Session, start: date, end: date):
    """Выручка, количество билетов и заказов за период."""
    return db.execute(select(func.coalesce(func.sum(Ticket.price), 0), func.count(),
                             func.count(func.distinct(Ticket.order_code)))
                      .where(Ticket.sold_at.between(datetime.combine(start, time.min),
                                                    datetime.combine(end, time.max)))).one()


def daily(db: Session, start: date, end: date):
    """Выручка по дням: [(дата, билетов, выручка, картой)]."""
    day = func.date(Ticket.sold_at)
    rows = db.execute(select(day, func.count(), func.sum(Ticket.price),
                             func.sum(case((Ticket.payment == "card", Ticket.price), else_=0)))
                      .where(Ticket.sold_at.between(datetime.combine(start, time.min), datetime.combine(end, time.max)))
                      .group_by(day)).all()
    by_day = {r[0]: r for r in rows}
    result = []
    current = start
    while current <= end:  # дни без продаж тоже попадают в график с нулём
        r = by_day.get(current)
        result.append((current, r[1] if r else 0, r[2] if r else 0, r[3] if r else 0))
        current += timedelta(days=1)
    return result


@router.get("/finance")
def finance(request: Request, period: str = "7", date_from: str = "", date_to: str = "",
            db: Session = Depends(get_db), user: User = Depends(finance_user)):
    start, end, label = get_period(period, date_from, date_to)
    t_from, t_to = datetime.combine(start, time.min), datetime.combine(end, time.max)
    in_period = Ticket.sold_at.between(t_from, t_to)

    revenue, count, orders = totals(db, start, end)
    # Тот же по длине период перед выбранным — для сравнения
    length = (end - start).days + 1
    prev_revenue, prev_count, _ = totals(db, start - timedelta(days=length), start - timedelta(days=1))
    delta = round((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else None

    days = daily(db, start, end)
    card = sum(d[3] for d in days)

    by_film = db.execute(select(Film.title, func.count(), func.sum(Ticket.price))
                         .join(Ticket.screening).join(Screening.film).where(in_period)
                         .group_by(Film.title).order_by(func.sum(Ticket.price).desc())).all()

    by_cashier = db.execute(select(User.full_name, func.count(), func.sum(Ticket.price),
                                   func.sum(case((Ticket.payment == "card", Ticket.price), else_=0)),
                                   func.count(func.distinct(Ticket.order_code)))
                            .join(Ticket.cashier).where(in_period)
                            .group_by(User.full_name).order_by(func.sum(Ticket.price).desc())).all()

    weekday_sum = [0] * 7
    for d in days:
        weekday_sum[d[0].weekday()] += d[2]

    # Заполняемость залов по прошедшим сеансам периода
    shows = db.execute(select(Screening.id, Screening.hall, func.count(Ticket.id))
                       .outerjoin(Screening.tickets)
                       .where(Screening.start_time.between(t_from, min(t_to, datetime.now())))
                       .group_by(Screening.id, Screening.hall)).all()
    hall_fill = {}
    for _, hall, sold in shows:
        seats, total_sold = hall_fill.get(hall, (0, 0))
        hall_fill[hall] = (seats + capacity(hall), total_sold + sold)
    occupancy = {h: round(sold / seats * 100) for h, (seats, sold) in sorted(hall_fill.items())}
    all_seats = sum(v[0] for v in hall_fill.values())
    occupancy_total = round(sum(v[1] for v in hall_fill.values()) / all_seats * 100) if all_seats else 0

    chart = {
        "days": [d[0].strftime("%d.%m") for d in days],
        "revenue": [d[2] for d in days],
        "card": [d[3] for d in days],
        "cash": [d[2] - d[3] for d in days],
        "tickets": [d[1] for d in days],
        "films": [r[0] for r in by_film[:8]],
        "film_revenue": [r[2] for r in by_film[:8]],
        "weekdays": WEEKDAYS,
        "weekday_revenue": weekday_sum,
        "halls": [HALLS[h]["name"] for h in occupancy],
        "hall_fill": list(occupancy.values()),
        "payment": [card, revenue - card],
    }
    return templates.TemplateResponse(request, "finance.html", {
        "user": user, "period": period, "start": start, "end": end, "label": label,
        "revenue": revenue, "count": count, "orders": orders, "delta": delta, "prev_count": prev_count,
        "avg_check": revenue / orders if orders else 0, "avg_ticket": revenue / count if count else 0,
        "card": card, "occupancy": occupancy_total, "by_film": by_film, "by_cashier": by_cashier,
        "days": days, "chart": chart,
    })


@router.get("/finance/export.csv")
def export(period: str = "7", date_from: str = "", date_to: str = "",
           db: Session = Depends(get_db), user: User = Depends(finance_user)):
    """Выгрузка сводки по дням в CSV (открывается в Excel)."""
    start, end, _ = get_period(period, date_from, date_to)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Дата", "Билетов", "Выручка, руб.", "Картой, руб.", "Наличными, руб."])
    for day, count, revenue, card in daily(db, start, end):
        writer.writerow([day.strftime("%d.%m.%Y"), count, revenue, card, revenue - card])
    name = f"vyruchka_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    # BOM в начале файла нужен, чтобы Excel правильно показал кириллицу
    return StreamingResponse(iter(["﻿" + buffer.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
