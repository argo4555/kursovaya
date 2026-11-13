from datetime import datetime, timedelta

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Сотрудник кинотеатра."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # admin, cashier или accountant

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="cashier")


class Film(Base):
    """Фильм."""
    __tablename__ = "films"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    genre: Mapped[str] = mapped_column(String(50))
    year: Mapped[int]
    duration: Mapped[int]  # длительность в минутах
    age_limit: Mapped[str] = mapped_column(String(5))
    description: Mapped[str] = mapped_column(Text, default="")
    poster_url: Mapped[str | None] = mapped_column(String(300))  # своя картинка; если нет — постер рисуется

    screenings: Mapped[list["Screening"]] = relationship(back_populates="film")

    @property
    def poster(self) -> str:
        """Адрес постера: своя картинка или постер, нарисованный приложением."""
        return self.poster_url or f"/posters/{self.id}.svg"

    @property
    def backdrop(self) -> str:
        """Фон для плиток: постер без надписей (название выводится поверх)."""
        return self.poster_url or f"/posters/{self.id}.svg?bare=1"


class Screening(Base):
    """Сеанс: показ фильма в зале в определённое время."""
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id"))
    hall: Mapped[int]
    start_time: Mapped[datetime]
    price: Mapped[int]  # базовая цена билета в рублях

    film: Mapped[Film] = relationship(back_populates="screenings")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="screening")

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(minutes=self.film.duration)


class Ticket(Base):
    """Проданный билет. Билеты одной покупки имеют общий код заказа."""
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    row_num: Mapped[int]
    seat_num: Mapped[int]
    price: Mapped[int]  # цена на момент продажи
    payment: Mapped[str] = mapped_column(String(10))  # cash или card
    order_code: Mapped[str] = mapped_column(String(12))
    sold_at: Mapped[datetime] = mapped_column(default=datetime.now)

    screening: Mapped[Screening] = relationship(back_populates="tickets")
    cashier: Mapped[User] = relationship(back_populates="tickets")
