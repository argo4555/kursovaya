"""Картинки фильмов.

/media/{id}/poster и /media/{id}/backdrop — постер и кадр из базы TMDB. Сервер скачивает картинку
один раз, хранит в памяти и отдаёт браузеру сам: так она открывается, даже если у посетителя
сайт TMDB недоступен. Если скачать не удалось, отдаётся постер, нарисованный приложением.

/posters/{id}.svg — постер, нарисованный приложением, в цветах жанра.
"""
import urllib.request
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Film

router = APIRouter()

# Цвета градиента и акцента для каждого жанра
PALETTES = {
    "Фантастика": ("#0b1d3a", "#1d4e89", "#5ad1ff"),
    "Драма": ("#2b1331", "#7a2048", "#ff9a8b"),
    "Семейный": ("#ff8a00", "#e52e71", "#ffe259"),
    "Комедия": ("#f83600", "#f9d423", "#ffffff"),
    "Мультфильм": ("#0f9b8e", "#5be37a", "#fff59d"),
    "Триллер": ("#0d0d0d", "#3a0b0b", "#ff3b3b"),
    "Спорт": ("#7b0d1e", "#1c1c3c", "#ffc93c"),
    "Мелодрама": ("#a1145c", "#4b1d6b", "#ffc1d9"),
}
DEFAULT_PALETTE = ("#1c1f2b", "#3b4466", "#ffc145")


def wrap(title: str, width: int = 11) -> list[str]:
    """Разбивает название на строки примерно по width символов."""
    lines, line = [], ""
    for word in title.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    return lines


def poster_svg(film: Film, bare: bool = False) -> str:
    """SVG-постер. bare=True — без надписей, для фона плиток."""
    c1, c2, accent = PALETTES.get(film.genre, DEFAULT_PALETTE)
    lines = wrap(film.title.upper())
    size = 52 if max(len(x) for x in lines) <= 8 else 42
    first_y = 520 - (len(lines) - 1) * (size + 6)
    title = "".join(
        f'<text x="32" y="{first_y + i * (size + 6)}" font-size="{size}" font-weight="800" fill="#fff" '
        f'letter-spacing="1">{escape(line)}</text>' for i, line in enumerate(lines))
    seed = film.id * 37
    texts = "" if bare else f"""<g font-family="Manrope, Segoe UI, Arial, sans-serif">
  <text x="32" y="56" font-size="15" font-weight="700" fill="{accent}" letter-spacing="4">{escape(film.genre.upper())}</text>
  <rect x="318" y="30" width="54" height="32" rx="8" fill="none" stroke="#fff" stroke-opacity="0.8" stroke-width="2"/>
  <text x="345" y="52" font-size="15" font-weight="800" fill="#fff" text-anchor="middle">{escape(film.age_limit)}</text>
  {title}
  <rect x="32" y="548" width="44" height="4" rx="2" fill="{accent}"/>
  <text x="88" y="555" font-size="15" font-weight="600" fill="#fff" fill-opacity="0.8">{film.year} · {film.duration} мин</text>
</g>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>
  <radialGradient id="glow" cx="0.7" cy="0.3" r="0.6"><stop offset="0" stop-color="{accent}" stop-opacity="0.55"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0.45" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.75"/></linearGradient>
</defs>
<rect width="400" height="600" fill="url(#bg)"/>
<rect width="400" height="600" fill="url(#glow)"/>
<circle cx="{280 + seed % 60}" cy="{170 + seed % 80}" r="120" fill="none" stroke="{accent}" stroke-opacity="0.35" stroke-width="2"/>
<circle cx="{280 + seed % 60}" cy="{170 + seed % 80}" r="80" fill="{accent}" fill-opacity="0.12"/>
<circle cx="{60 + seed % 90}" cy="{330 + seed % 50}" r="46" fill="none" stroke="#fff" stroke-opacity="0.15" stroke-width="1.5"/>
<path d="M-20 {380 + seed % 40} L420 {250 + seed % 60} L420 {280 + seed % 60} L-20 {410 + seed % 40} Z" fill="#fff" fill-opacity="0.06"/>
<rect width="400" height="600" fill="url(#shade)"/>
{texts}
</svg>"""


@router.get("/posters/{film_id}.svg")
def poster(film_id: int, bare: int = 0, db: Session = Depends(get_db)):
    film = db.get(Film, film_id)
    if film is None:
        raise HTTPException(status_code=404)
    return Response(poster_svg(film, bool(bare)), media_type="image/svg+xml", headers={"Cache-Control": "max-age=3600"})


# Сервер сам скачивает картинки только с этих сайтов; ссылки на другие сайты браузер открывает напрямую
PROXY_HOSTS = {"image.tmdb.org"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
_cache: dict[str, tuple[bytes, str]] = {}


def download(url: str) -> tuple[bytes, str] | None:
    """Скачивает картинку (не больше 5 МБ). Возвращает (данные, тип) или None при ошибке."""
    if url in _cache:
        return _cache[url]
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "kino-course-project"})
        with urllib.request.urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_IMAGE_SIZE + 1)
        if not content_type.startswith("image/") or len(data) > MAX_IMAGE_SIZE:
            return None
    except OSError:
        return None
    _cache[url] = (data, content_type)
    return data, content_type


@router.get("/media/{film_id}/{kind}")
def media(film_id: int, kind: str, db: Session = Depends(get_db)):
    film = db.get(Film, film_id)
    if film is None or kind not in ("poster", "backdrop"):
        raise HTTPException(status_code=404)
    url = film.poster_url if kind == "poster" else (film.backdrop_url or film.poster_url)
    bare = kind == "backdrop"
    if url and urlparse(url).hostname not in PROXY_HOSTS:
        return RedirectResponse(url)
    image = download(url) if url else None
    if image is None:  # нет ссылки или сайт недоступен — нарисованный постер
        return Response(poster_svg(film, bare), media_type="image/svg+xml", headers={"Cache-Control": "max-age=300"})
    return Response(image[0], media_type=image[1], headers={"Cache-Control": "max-age=86400"})
