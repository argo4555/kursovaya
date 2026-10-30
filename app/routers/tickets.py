from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import admin_user, current_user
from app.database import get_db
from app.models import Screening, Ticket, User
from app.templating import templates

router = APIRouter()

# Размер зала: количество рядов и мест в ряду
HALL_ROWS = 10
HALL_SEATS = 12


def all_screenings(db: Session):
    return db.scalars(select(Screening).order_by(Screening.start_time)).all()


def check_ticket(db: Session, screening_id: str, row_num: str, seat_num: str, ticket_id=None):
    """Проверяет данные билета. Возвращает текст ошибки или None."""
    if screening_id == "" or row_num.strip() == "" or seat_num.strip() == "":
        return "Заполните все поля: сеанс, ряд и место"
    if not row_num.strip().isdigit() or not seat_num.strip().isdigit():
        return "Ряд и место должны быть числами"
    row, seat = int(row_num), int(seat_num)
    if not 1 <= row <= HALL_ROWS:
        return f"Ряд должен быть от 1 до {HALL_ROWS}"
    if not 1 <= seat <= HALL_SEATS:
        return f"Место должно быть от 1 до {HALL_SEATS}"

    # Место не должно быть уже продано на этот сеанс
    query = select(Ticket).where(
        Ticket.screening_id == int(screening_id),
        Ticket.row_num == row,
        Ticket.seat_num == seat,
    )
    if ticket_id is not None:
        query = query.where(Ticket.id != ticket_id)
    if db.scalar(query):
        return "Это место на выбранный сеанс уже продано"
    return None


@router.get("/")
def ticket_list(
    request: Request,
    screening_id: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = select(Ticket).order_by(Ticket.sold_at.desc())
    if screening_id:
        query = query.where(Ticket.screening_id == int(screening_id))
    tickets = db.scalars(query).all()
    total = sum(ticket.screening.price for ticket in tickets)
    return templates.TemplateResponse(request, "tickets.html", {
        "user": user,
        "tickets": tickets,
        "total": total,
        "screenings": all_screenings(db),
        "selected": screening_id,
    })


@router.get("/tickets/add")
def add_ticket_page(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return templates.TemplateResponse(request, "ticket_form.html", {
        "user": user,
        "title": "Продажа билета",
        "screenings": all_screenings(db),
        "form": {"screening_id": "", "row_num": "", "seat_num": ""},
        "error": None,
    })


@router.post("/tickets/add")
def add_ticket(
    request: Request,
    screening_id: str = Form(""),
    row_num: str = Form(""),
    seat_num: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    error = check_ticket(db, screening_id, row_num, seat_num)
    if error:
        # Возвращаем форму с сообщением и ранее введёнными значениями
        return templates.TemplateResponse(request, "ticket_form.html", {
            "user": user,
            "title": "Продажа билета",
            "screenings": all_screenings(db),
            "form": {"screening_id": screening_id, "row_num": row_num, "seat_num": seat_num},
            "error": error,
        })
    ticket = Ticket(
        screening_id=int(screening_id),
        row_num=int(row_num),
        seat_num=int(seat_num),
        user_id=user.id,
    )
    db.add(ticket)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/tickets/{ticket_id}/edit")
def edit_ticket_page(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Билет не найден")
    return templates.TemplateResponse(request, "ticket_form.html", {
        "user": user,
        "title": f"Изменение билета № {ticket.id}",
        "screenings": all_screenings(db),
        "form": {
            "screening_id": str(ticket.screening_id),
            "row_num": ticket.row_num,
            "seat_num": ticket.seat_num,
        },
        "error": None,
    })


@router.post("/tickets/{ticket_id}/edit")
def edit_ticket(
    request: Request,
    ticket_id: int,
    screening_id: str = Form(""),
    row_num: str = Form(""),
    seat_num: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Билет не найден")
    error = check_ticket(db, screening_id, row_num, seat_num, ticket_id)
    if error:
        return templates.TemplateResponse(request, "ticket_form.html", {
            "user": user,
            "title": f"Изменение билета № {ticket.id}",
            "screenings": all_screenings(db),
            "form": {"screening_id": screening_id, "row_num": row_num, "seat_num": seat_num},
            "error": error,
        })
    ticket.screening_id = int(screening_id)
    ticket.row_num = int(row_num)
    ticket.seat_num = int(seat_num)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.post("/tickets/{ticket_id}/delete")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is not None:
        db.delete(ticket)
        db.commit()
    return RedirectResponse("/", status_code=303)
