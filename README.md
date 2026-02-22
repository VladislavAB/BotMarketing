Сервис каждые N минут запрашивает курсы валют с API Frankfurter и сохраняет историю в PostgreSQL.
Отслеживает только те валюты, которые указаны в .env в строке CURRENCIES.

1. .env
   Основной файл настроек.
   Здесь указывается:
   - подключение к базе данных (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
   - ссылки на API (API_CURRENCIES_URL и API_LATEST_URL)
   - список валют, которые нужно отслеживать (CURRENCIES=USD,EUR,GBP,RUB,PLN)
   - интервал сбора в минутах (CHECK_INTERVAL_MINUTES)
   - путь к файлу логов ошибок (LOG_FILE)

   Скрипт читает эти переменные при запуске. Чтобы изменить валюты - редактировать строку CURRENCIES и перезапустить контейнер.

2. docker-compose.yml
   Файл, который запускает два контейнера:
   - db: PostgreSQL база данных
   - fetcher: контейнер со скриптом

   docker compose up -d --build поднимает

3. Dockerfile
   образ для скрипта.
   - берёт python 3.11
   - устанавливает зависимости из requirements.txt
   - копирует все файлы проекта
   - запускает fetch_rates_sync (или fetch_rates_async)

4. fetch_rates_async.py
   Асинхронная версия скрипта
   - при запуске создаёт таблицы и заполняет справочник валют (bases) из API
   - каждые N минут параллельно запрашивает курсы по всем валютам из CURRENCIES
   - сохраняет историю в таблицу rates

5. fetch_rates_sync.py
   Синхронная версия скрипта
   Делает то же самое, но запросы идут по очереди.

6. queries.sql
   примеры SQL-запросов
   - первый: все курсы за указанный диапазон дат
   - второй: история по конкретным валютам (USD и EUR) за всё время

7. requirements.txt
   список библиотек, которые нужны скрипту.
   - aiohttp и asyncpg: для асинхронной версии
   - requests и psycopg2-binary: для синхронной версии
   - python-dotenv: чтобы читать env


Запустить
docker compose up -d --build
можно в Dockerfile поменять на асинхронный скрпит и опять запустить

Перезапуск после изменения валют
docker compose restart fetcher

Зайти в базу
docker compose exec db psql -U postgres -d curr