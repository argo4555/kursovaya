"""Залы кинотеатра: название, число рядов и мест в ряду, наценка."""

HALLS = {
    1: {"name": "Зал 1 · Большой", "rows": 10, "seats": 14, "factor": 1.0},
    2: {"name": "Зал 2 · Комфорт", "rows": 8, "seats": 12, "factor": 1.0},
    3: {"name": "Зал 3 · VIP", "rows": 5, "seats": 8, "factor": 1.6},
}

# Время на уборку зала между сеансами, минут
CLEANING_MINUTES = 15


def capacity(hall: int) -> int:
    """Количество мест в зале."""
    return HALLS[hall]["rows"] * HALLS[hall]["seats"]
