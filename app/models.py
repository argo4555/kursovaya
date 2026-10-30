from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Сотрудник кинотеатра."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # admin или cashier


class Film(Base):
    """Фильм."""
    __tablename__ = "films"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    genre: Mapped[str] = mapped_column(String(50))
    duration: Mapped[int]  # длительность в минутах
    age_limit: Mapped[str] = mapped_column(String(5))

    screenings: Mapped[list["Screening"]] = relationship(back_populates="film")


class Screening(Base):
    """Сеанс: показ фильма в зале в определённое время."""
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id"))
    hall: Mapped[int]
    start_time: Mapped[datetime]
    price: Mapped[int]  # цена билета в рублях

    film: Mapped[Film] = relationship(back_populates="screenings")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="screening")


class Ticket(Base):
    """Проданный билет."""
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    row_num: Mapped[int]
    seat_num: Mapped[int]
    sold_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    screening: Mapped[Screening] = relationship(back_populates="tickets")
    cashier: Mapped[User] = relationship()
