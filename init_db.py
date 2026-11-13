"""Создаёт базу данных kino, таблицы и заполняет их тестовыми данными.

Запуск: python init_db.py
Внимание: существующие таблицы удаляются и создаются заново.
"""
import random
import string
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.auth import hash_password
from app.database import DATABASE_URL, SessionLocal, engine
from app.halls import HALLS
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


def order_code(rnd):
    return "".join(rnd.choices(string.ascii_uppercase + string.digits, k=6))


FILMS = [
    ("Интерстеллар", "Фантастика", 2014, 169, "12+",
     "Команда исследователей отправляется через червоточину в поисках нового дома для человечества."),
    ("Брат", "Драма", 1997, 100, "18+",
     "Демобилизованный Данила приезжает в Петербург к старшему брату и оказывается втянут в его дела."),
    ("Чебурашка", "Семейный", 2023, 113, "6+",
     "Загадочный ушастый зверёк появляется в приморском городке и меняет жизнь угрюмого садовника."),
    ("Дюна", "Фантастика", 2021, 155, "12+",
     "Наследник знатного рода оказывается на пустынной планете, от которой зависит судьба галактики."),
    ("Холоп", "Комедия", 2019, 109, "16+",
     "Избалованного мажора перевоспитывают, убедив, что он очутился в XIX веке крепостным."),
    ("Король Лев", "Мультфильм", 1994, 88, "0+",
     "Львёнок Симба должен пройти долгий путь, чтобы занять своё место в круге жизни."),
    ("Начало", "Триллер", 2010, 148, "12+",
     "Профессиональный вор проникает в сны, чтобы не украсть, а внедрить идею."),
    ("Движение вверх", "Спорт", 2017, 133, "6+",
     "История легендарной победы сборной СССР по баскетболу на Олимпиаде 1972 года."),
    ("Москва слезам не верит", "Мелодрама", 1979, 150, "12+",
     "Три подруги приезжают покорять столицу, и у каждой своя дорога к счастью."),
    ("Аватар", "Фантастика", 2009, 162, "12+",
     "Бывший морпех попадает на Пандору и встаёт перед выбором между двумя мирами."),
]

# Расписание залов: время начала сеансов
SLOTS = {1: ["10:00", "13:30", "17:00", "20:30"], 2: ["11:00", "14:30", "18:00", "21:30"], 3: ["12:00", "16:00", "19:30"]}
BASE_PRICE = {"10:00": 250, "11:00": 250, "12:00": 300, "13:30": 300, "14:30": 300, "16:00": 350,
              "17:00": 400, "18:00": 400, "19:30": 450, "20:30": 450, "21:30": 400}


def fill_data():
    rnd = random.Random(2026)
    db = SessionLocal()

    admin = User(login="admin", password_hash=hash_password("1234"),
                 full_name="Смирнова Ольга Петровна", role="admin")
    cashier1 = User(login="kassir1", password_hash=hash_password("1111"),
                    full_name="Иванов Алексей Сергеевич", role="cashier")
    cashier2 = User(login="kassir2", password_hash=hash_password("2222"),
                    full_name="Петрова Мария Андреевна", role="cashier")
    accountant = User(login="buh", password_hash=hash_password("3333"),
                      full_name="Ковалёва Наталья Игоревна", role="accountant")
    db.add_all([admin, cashier1, cashier2, accountant])
    cashiers = [cashier1, cashier2]

    films = [Film(title=t, genre=g, year=y, duration=d, age_limit=a, description=s) for t, g, y, d, a, s in FILMS]
    db.add_all(films)

    # Сеансы: две недели назад, сегодня и два дня вперёд
    today = date.today()
    now = datetime.now()
    popularity = [0.9, 0.55, 0.7, 0.85, 0.65, 0.5, 0.75, 0.6, 0.45, 0.8]
    for day in range(-14, 3):
        for hall, slots in SLOTS.items():
            for i, slot in enumerate(slots):
                film_index = (day * 3 + hall * 2 + i) % len(films)
                start = datetime.combine(today + timedelta(days=day), time.fromisoformat(slot))
                price = round(BASE_PRICE[slot] * HALLS[hall]["factor"] / 10) * 10
                screening = Screening(film=films[film_index], hall=hall, start_time=start, price=price)
                db.add(screening)

                # Заполняемость: выше вечером, в выходные и у популярных фильмов
                weekend = start.weekday() >= 4
                evening = slot >= "17:00"
                fill = popularity[film_index] * rnd.uniform(0.35, 0.8) + 0.12 * weekend + 0.1 * evening
                if start > now:  # на будущие сеансы продана только часть билетов
                    fill *= 0.35 if day > 0 else 0.55
                rows, seats = HALLS[hall]["rows"], HALLS[hall]["seats"]
                target = int(rows * seats * min(fill, 0.95))

                # Билеты покупают группами по 1–4 соседних места
                taken = set()
                attempts = 0
                while len(taken) < target and attempts < 2000:
                    attempts += 1
                    size = rnd.choice([1, 2, 2, 2, 3, 4])
                    row = rnd.randint(1, rows)
                    first = rnd.randint(1, seats - size + 1)
                    group = [(row, s) for s in range(first, first + size)]
                    if any(place in taken for place in group):
                        continue
                    taken.update(group)
                    code = order_code(rnd)
                    cashier = rnd.choice(cashiers)
                    payment = "card" if rnd.random() < 0.68 else "cash"
                    if start > now:  # билеты на будущие сеансы купили заранее, за последние дни
                        sold_at = now - timedelta(minutes=rnd.randint(30, 3 * 24 * 60))
                    else:
                        sold_at = start - timedelta(minutes=rnd.randint(5, 600))
                    for row_num, seat_num in group:
                        db.add(Ticket(screening=screening, row_num=row_num, seat_num=seat_num, price=price,
                                      payment=payment, order_code=code, cashier=cashier, sold_at=sold_at))

    db.commit()
    db.close()
    print("Тестовые данные добавлены")


if __name__ == "__main__":
    create_database()
    create_tables()
    fill_data()
