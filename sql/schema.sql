-- Структура базы данных kino (PostgreSQL)

DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS screenings;
DROP TABLE IF EXISTS films;
DROP TABLE IF EXISTS users;

-- Сотрудники кинотеатра (администратор и кассиры)
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    login         VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'cashier'))
);

-- Фильмы
CREATE TABLE films (
    id        SERIAL PRIMARY KEY,
    title     VARCHAR(150) NOT NULL,
    genre     VARCHAR(50)  NOT NULL,
    duration  INTEGER      NOT NULL CHECK (duration > 0),
    age_limit VARCHAR(5)   NOT NULL
);

-- Сеансы
CREATE TABLE screenings (
    id         SERIAL PRIMARY KEY,
    film_id    INTEGER   NOT NULL REFERENCES films(id),
    hall       INTEGER   NOT NULL CHECK (hall BETWEEN 1 AND 3),
    start_time TIMESTAMP NOT NULL,
    price      INTEGER   NOT NULL CHECK (price > 0)
);

-- Билеты
CREATE TABLE tickets (
    id           SERIAL PRIMARY KEY,
    screening_id INTEGER   NOT NULL REFERENCES screenings(id),
    user_id      INTEGER   NOT NULL REFERENCES users(id),
    row_num      INTEGER   NOT NULL CHECK (row_num BETWEEN 1 AND 10),
    seat_num     INTEGER   NOT NULL CHECK (seat_num BETWEEN 1 AND 12),
    sold_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (screening_id, row_num, seat_num)
);
