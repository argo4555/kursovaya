"""Создаёт базу данных kino, таблицы и заполняет их тестовыми данными.

Запуск: python init_db.py
Внимание: существующие таблицы удаляются и создаются заново.
"""
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.auth import hash_password
from app.database import DATABASE_URL, SessionLocal, engine
from app.models import Film, Screening, Ticket, User


def create_database():
    """Создаёт базу данных, если её ещё нет."""
    url = make_url(DATABASE_URL)
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
            print(f"База данных {url.database} создана")
    server.dispose()


def create_tables():
    """Выполняет SQL-скрипт sql/schema.sql."""
    sql = (Path(__file__).parent / "sql" / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
    print("Таблицы созданы")


def fill_data():
    db = SessionLocal()

    admin = User(login="admin", password_hash=hash_password("1234"),
                 full_name="Смирнова Ольга Петровна", role="admin")
    cashier1 = User(login="kassir1", password_hash=hash_password("1111"),
                    full_name="Иванов Алексей Сергеевич", role="cashier")
    cashier2 = User(login="kassir2", password_hash=hash_password("2222"),
                    full_name="Петрова Мария Андреевна", role="cashier")
    db.add_all([admin, cashier1, cashier2])

    films = [
        Film(title="Интерстеллар", genre="Фантастика", duration=169, age_limit="12+"),
        Film(title="Брат", genre="Драма", duration=100, age_limit="18+"),
        Film(title="Чебурашка", genre="Семейный", duration=113, age_limit="6+"),
        Film(title="Дюна", genre="Фантастика", duration=155, age_limit="12+"),
        Film(title="Холоп", genre="Комедия", duration=109, age_limit="16+"),
        Film(title="Король Лев", genre="Мультфильм", duration=88, age_limit="0+"),
        Film(title="Начало", genre="Триллер", duration=148, age_limit="12+"),
        Film(title="Движение вверх", genre="Спорт", duration=133, age_limit="6+"),
        Film(title="Москва слезам не верит", genre="Мелодрама", duration=150, age_limit="12+"),
        Film(title="Аватар", genre="Фантастика", duration=162, age_limit="12+"),
    ]
    db.add_all(films)

    # Сеансы на ближайшие три дня: (день, зал, время, номер фильма, цена)
    today = date.today()
    plan = [
        (0, 1, "10:00", 5, 250), (0, 1, "14:30", 0, 400), (0, 2, "18:00", 3, 450),
        (0, 3, "21:00", 1, 350), (1, 1, "11:00", 2, 250), (1, 2, "16:00", 6, 400),
        (1, 3, "19:30", 4, 450), (2, 1, "12:00", 7, 300), (2, 2, "17:00", 8, 350),
        (2, 3, "20:00", 9, 500),
    ]
    screenings = []
    for day, hall, start, film_index, price in plan:
        start_time = datetime.combine(today + timedelta(days=day), time.fromisoformat(start))
        screenings.append(Screening(film=films[film_index], hall=hall, start_time=start_time, price=price))
    db.add_all(screenings)

    # Проданные билеты: (номер сеанса, ряд, место, кассир)
    sold = [
        (0, 5, 6, cashier1), (0, 5, 7, cashier1), (1, 3, 1, cashier2), (1, 3, 2, cashier2),
        (1, 7, 10, cashier1), (2, 6, 5, cashier1), (2, 6, 6, cashier1), (2, 6, 7, cashier2),
        (3, 9, 12, cashier2), (4, 2, 4, cashier1), (5, 4, 4, cashier2), (5, 4, 5, cashier2),
        (6, 8, 8, cashier1), (7, 1, 1, cashier2), (8, 10, 3, cashier1), (9, 5, 5, cashier2),
    ]
    sold_at = datetime.now() - timedelta(hours=len(sold))
    for screening_index, row, seat, cashier in sold:
        sold_at += timedelta(minutes=50)
        db.add(Ticket(screening=screenings[screening_index], row_num=row, seat_num=seat,
                      cashier=cashier, sold_at=sold_at))

    db.commit()
    db.close()
    print("Тестовые данные добавлены")


if __name__ == "__main__":
    create_database()
    create_tables()
    fill_data()
