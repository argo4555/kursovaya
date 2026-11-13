"""Запуск приложения: python run.py

При первом запуске (или если структура базы устарела) создаёт таблицы и тестовые данные.
"""
import os
import time

# Время приложения — московское (на хостинге по умолчанию UTC)
os.environ.setdefault("TZ", "Europe/Moscow")
if hasattr(time, "tzset"):
    time.tzset()

import uvicorn  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

import init_db  # noqa: E402
from app.database import engine  # noqa: E402


def schema_is_current():
    """Таблицы есть и соответствуют текущей версии (у билетов есть код заказа)."""
    inspector = inspect(engine)
    if not inspector.has_table("tickets"):
        return False
    columns = {column["name"] for column in inspector.get_columns("tickets")}
    return "order_code" in columns


if __name__ == "__main__":
    init_db.create_database()
    if not schema_is_current():
        init_db.create_tables()
        init_db.fill_data()

    # Хостинг передаёт номер порта в переменной PORT, локально — 8000
    port = int(os.getenv("PORT", 8000))
    print(f"Откройте в браузере: http://127.0.0.1:{port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
