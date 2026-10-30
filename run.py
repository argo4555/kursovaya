"""Запуск приложения: python run.py

При первом запуске (пустая база данных) создаёт таблицы и тестовые данные.
"""
import os

import uvicorn
from sqlalchemy import inspect

import init_db
from app.database import engine

if __name__ == "__main__":
    init_db.create_database()
    if not inspect(engine).has_table("users"):
        init_db.create_tables()
        init_db.fill_data()

    # Хостинг передаёт номер порта в переменной PORT, локально — 8000
    port = int(os.getenv("PORT", 8000))
    print(f"Откройте в браузере: http://127.0.0.1:{port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
