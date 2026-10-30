# Кинотеатр «Звезда» — продажа билетов

Курсовой проект по МДК.09.01. Стек: Python, FastAPI, Jinja2, SQLAlchemy, PostgreSQL, Bootstrap 5.

## Структура

```
kino/
├── app/
│   ├── main.py          — создание приложения, подключение маршрутов
│   ├── database.py      — подключение к БД
│   ├── models.py        — таблицы БД в виде классов
│   ├── auth.py          — хеширование паролей, проверка входа и роли
│   ├── templating.py    — настройка Jinja2
│   ├── routers/         — обработчики страниц (вход, билеты, сеансы, фильмы)
│   ├── templates/       — HTML-шаблоны
│   └── static/style.css
├── sql/schema.sql       — SQL-скрипт создания таблиц
├── init_db.py           — пересоздаёт таблицы и заполняет тестовыми данными
├── run.py               — запуск приложения
├── requirements.txt     — зависимости
├── railway.json         — команда запуска для Railway
└── .env                 — адрес локальной БД (в Git не попадает)
```

## Запуск на своём компьютере

1. В файле `.env` указать адрес своей БД:
   `DATABASE_URL=postgresql://postgres:ПАРОЛЬ@localhost:5432/kino_db`
2. Установить зависимости (в активированном виртуальном окружении):
   `pip install -r requirements.txt`
3. Запустить из папки `kino`:
   `python run.py`
4. Открыть http://127.0.0.1:8000

При первом запуске база данных, таблицы и тестовые данные создаются автоматически.
Чтобы вернуть тестовые данные к исходным: `python init_db.py`.

## Публикация на Railway

1. Залить папку `kino` в репозиторий на GitHub (файлы `.env` и `.venv` не попадут — они в `.gitignore`).
2. На railway.com: **New Project → Deploy from GitHub repo** → выбрать репозиторий.
3. В том же проекте: **+ Create → Database → PostgreSQL**.
4. В сервисе приложения: **Variables → New Variable**:
   `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
5. **Settings → Networking → Generate Domain** — появится адрес вида `https://....up.railway.app`.

Команда запуска (`python run.py`) берётся из `railway.json`, таблицы и тестовые данные создадутся при первом запуске.

## Пользователи

| Логин   | Пароль | Роль          |
|---------|--------|---------------|
| admin   | 1234   | администратор |
| kassir1 | 1111   | кассир        |
| kassir2 | 2222   | кассир        |
