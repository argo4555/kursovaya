from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import NotLoggedIn
from app.routers import films, login, screenings, tickets

app = FastAPI(title="Кинотеатр")

# Сессия хранится в подписанной cookie
app.add_middleware(SessionMiddleware, secret_key="kino-course-project-secret")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(login.router)
app.include_router(tickets.router)
app.include_router(films.router)
app.include_router(screenings.router)


@app.exception_handler(NotLoggedIn)
def redirect_to_login(request: Request, exc: NotLoggedIn):
    """Без входа любая закрытая страница ведёт на страницу входа."""
    return RedirectResponse("/login", status_code=303)
