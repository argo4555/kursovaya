"""Дашборд администратора и журнал продаж."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import admin_user, finance_user
from app.database import get_db
from app.halls import capacity
from app.models import Film, Screening, Ticket, User
from app.templating import templates

router = APIRouter()


@router.get("/admin")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    now = datetime.now()
    today = date.today()
    day_start, day_end = datetime.combine(today, time.min), datetime.combine(today, time.max)

    revenue, count = db.execute(select(func.coalesce(func.sum(Ticket.price), 0), func.count())
                                .where(Ticket.sold_at >= day_start)).one()
    yesterday = db.scalar(select(func.coalesce(func.sum(Ticket.price), 0))
                          .where(Ticket.sold_at.between(day_start - timedelta(days=1), now - timedelta(days=1))))

    # Сеансы сегодня с заполняемостью
    shows = db.execute(select(Screening, func.count(Ticket.id)).outerjoin(Screening.tickets)
                       .where(Screening.start_time.between(day_start, day_end))
                       .group_by(Screening.id).order_by(Screening.start_time)).all()
    today_shows = []
    for s, sold in shows:
        if s.end_time < now:
            state = "done"
        elif s.start_time <= now:
            state = "live"
        else:
            state = "soon"
        today_shows.append({"s": s, "sold": sold, "cap": capacity(s.hall),
                            "pct": round(sold / capacity(s.hall) * 100), "state": state})
    seats = sum(x["cap"] for x in today_shows)
    occupancy = round(sum(x["sold"] for x in today_shows) / seats * 100) if seats else 0

    # Выручка за 14 дней для графика
    start14 = today - timedelta(days=13)
    day = func.date(Ticket.sold_at)
    rows = dict(db.execute(select(day, func.sum(Ticket.price))
                           .where(Ticket.sold_at >= datetime.combine(start14, time.min)).group_by(day)).all())
    spark_days = [start14 + timedelta(days=i) for i in range(14)]

    top = db.execute(select(Film, func.count(Ticket.id), func.sum(Ticket.price))
                     .join(Film.screenings).join(Screening.tickets)
                     .where(Ticket.sold_at >= datetime.combine(today - timedelta(days=6), time.min))
                     .group_by(Film.id).order_by(func.sum(Ticket.price).desc()).limit(5)).all()

    recent = db.execute(select(Ticket.order_code, func.max(Ticket.sold_at), func.count(), func.sum(Ticket.price))
                        .group_by(Ticket.order_code).order_by(func.max(Ticket.sold_at).desc()).limit(8)).all()
    recent_orders = []
    for code, sold_at, cnt, total in recent:
        first = db.scalar(select(Ticket).where(Ticket.order_code == code).limit(1))
        recent_orders.append({"code": code, "at": sold_at, "count": cnt, "total": total, "t": first})

    return templates.TemplateResponse(request, "admin.html", {
        "user": user, "revenue": revenue, "count": count, "occupancy": occupancy,
        "delta": round((revenue - yesterday) / yesterday * 100) if yesterday else None,
        "shows": today_shows, "live": sum(1 for x in today_shows if x["state"] == "live"),
        "spark": {"labels": [d.strftime("%d.%m") for d in spark_days], "values": [rows.get(d, 0) for d in spark_days]},
        "top": top, "recent": recent_orders,
    })


@router.get("/sales")
def sales(request: Request, day: str = "", film: int = 0, cashier: int = 0, payment: str = "",
          db: Session = Depends(get_db), user: User = Depends(finance_user)):
    """Журнал продаж за день с отбором по фильму, кассиру и способу оплаты."""
    try:
        selected = date.fromisoformat(day) if day else date.today()
    except ValueError:
        selected = date.today()
    query = (select(Ticket).join(Ticket.screening)
             .where(Ticket.sold_at.between(datetime.combine(selected, time.min), datetime.combine(selected, time.max)))
             .order_by(Ticket.sold_at.desc()))
    if film:
        query = query.where(Screening.film_id == film)
    if cashier:
        query = query.where(Ticket.user_id == cashier)
    if payment in ("card", "cash"):
        query = query.where(Ticket.payment == payment)
    tickets = db.scalars(query).all()

    orders = {}
    for t in tickets:
        orders.setdefault(t.order_code, []).append(t)
    return templates.TemplateResponse(request, "sales.html", {
        "user": user, "orders": orders, "day": selected, "film": film, "cashier": cashier, "payment": payment,
        "films": db.scalars(select(Film).order_by(Film.title)).all(),
        "cashiers": db.scalars(select(User).where(User.role.in_(["cashier", "admin"])).order_by(User.full_name)).all(),
        "total": sum(t.price for t in tickets), "count": len(tickets), "current": datetime.now(),
        "message": "Билеты возвращены, места снова свободны" if request.query_params.get("refunded") else None,
    })


@router.post("/sales/{code}/refund")
def refund(code: str, back: str = Form("/sales"), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    """Возврат покупки: билеты удаляются, если сеанс ещё не начался."""
    first = db.scalar(select(Ticket).where(Ticket.order_code == code).limit(1))
    if first is not None and first.screening.start_time > datetime.now():
        db.execute(delete(Ticket).where(Ticket.order_code == code))
        db.commit()
    if not back.startswith("/") or back.startswith("//"):  # возврат только на страницы своего сайта
        back = "/sales"
    separator = "&" if "?" in back else "?"
    return RedirectResponse(f"{back}{separator}refunded=1", status_code=303)
