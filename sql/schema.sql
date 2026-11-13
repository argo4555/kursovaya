-- Структура базы данных kino (PostgreSQL)

DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS screenings;
DROP TABLE IF EXISTS films;
DROP TABLE IF EXISTS users;

-- Сотрудники кинотеатра: администратор, кассиры, бухгалтер
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    login         VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'cashier', 'accountant'))
);

-- Фильмы
CREATE TABLE films (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(150) NOT NULL,
    genre       VARCHAR(50)  NOT NULL,
    year        INTEGER      NOT NULL CHECK (year BETWEEN 1900 AND 2100),
    duration    INTEGER      NOT NULL CHECK (duration BETWEEN 30 AND 300),
    age_limit   VARCHAR(5)   NOT NULL,
    description TEXT         NOT NULL DEFAULT '',
    poster_url  VARCHAR(300)
);

-- Сеансы
CREATE TABLE screenings (
    id         SERIAL PRIMARY KEY,
    film_id    INTEGER   NOT NULL REFERENCES films(id),
    hall       INTEGER   NOT NULL CHECK (hall BETWEEN 1 AND 3),
    start_time TIMESTAMP NOT NULL,
    price      INTEGER   NOT NULL CHECK (price > 0)
);

-- Билеты. Одно место на сеанс можно продать только один раз
CREATE TABLE tickets (
    id           SERIAL PRIMARY KEY,
    screening_id INTEGER     NOT NULL REFERENCES screenings(id),
    user_id      INTEGER     NOT NULL REFERENCES users(id),
    row_num      INTEGER     NOT NULL CHECK (row_num >= 1),
    seat_num     INTEGER     NOT NULL CHECK (seat_num >= 1),
    price        INTEGER     NOT NULL CHECK (price > 0),
    payment      VARCHAR(10) NOT NULL CHECK (payment IN ('cash', 'card')),
    order_code   VARCHAR(12) NOT NULL,
    sold_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (screening_id, row_num, seat_num)
);

CREATE INDEX tickets_sold_at ON tickets (sold_at);
CREATE INDEX tickets_order ON tickets (order_code);
