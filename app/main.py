from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import NotLoggedIn
from app.routers import admin, cashier, films, finance, login, posters, screenings, users
from app.templating import templates

app = FastAPI(title="Кинотеатр «Звезда»")

# Сессия хранится в подписанной cookie
app.add_middleware(SessionMiddleware, secret_key="kino-course-project-secret")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

for module in (login, cashier, admin, films, screenings, users, finance, posters):
    app.include_router(module.router)


@app.exception_handler(NotLoggedIn)
def redirect_to_login(request: Request, exc: NotLoggedIn):
    """Без входа любая закрытая страница ведёт на страницу входа."""
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(HTTPException)
def error_page(request: Request, exc: HTTPException):
    """Понятная страница ошибки вместо JSON (нет прав, не найдено)."""
    return templates.TemplateResponse(request, "error.html", {"code": exc.status_code, "detail": exc.detail},
                                      status_code=exc.status_code)
