from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.auth import HOME, ROLE_NAMES
from app.halls import HALLS, capacity

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def rub(value) -> str:
    """Сумма в рублях: 12 450 ₽"""
    return f"{int(value or 0):,}".replace(",", " ") + " ₽"


def num(value) -> str:
    """Число с пробелами между разрядами: 12 450"""
    return f"{int(value or 0):,}".replace(",", " ")


def ru_date(value) -> str:
    """Дата словами: 13 ноября"""
    return f"{value.day} {MONTHS[value.month - 1]}"


def day_label(value: date) -> str:
    """Подпись дня: Сегодня, Завтра или «пн, 16 ноября»"""
    today = date.today()
    if value == today:
        return "Сегодня"
    if value == today + timedelta(days=1):
        return "Завтра"
    return f"{WEEKDAYS[value.weekday()]}, {ru_date(value)}"


templates.env.filters.update(rub=rub, num=num, ru_date=ru_date, day_label=day_label)
templates.env.globals.update(HALLS=HALLS, capacity=capacity, ROLE_NAMES=ROLE_NAMES, HOME=HOME, now=datetime.now)
