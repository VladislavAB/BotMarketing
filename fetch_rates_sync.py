import os
import time
import logging
import requests
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(filename=os.getenv("LOG_FILE", "logs/errors.log"), level=logging.ERROR,
                    format="%(asctime)s %(message)s")


def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"))


def init_bases():
    conn = get_conn()
    cur = conn.cursor()

    try:
        #создаём таблицу bases (справочник валют)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bases (
                id SERIAL PRIMARY KEY,
                name VARCHAR(3) UNIQUE NOT NULL,
                description TEXT NOT NULL)""")

        # создаём таблицу rates (история курсов)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rates (
                id SERIAL PRIMARY KEY,
                base_currency INTEGER REFERENCES bases(id) ON DELETE CASCADE,
                target_currency VARCHAR(3) NOT NULL,
                rate NUMERIC(20,10) NOT NULL,
                add_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)""")

        logging.info("СОздали таблицы в БД")

        # заполняем bases всеми доступными валютами из API
        url = os.getenv("API_CURRENCIES_URL")
        r = requests.get(url, timeout=5)
        currencies = r.json()

        for currency, description in currencies.items():
            cur.execute(
                """
                INSERT INTO bases (name, description)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING""",
                (currency, description))

        conn.commit()
        logging.info("Заполнили таблицу bases данными")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        print(f"Ошибка: {e}")
    finally:
        cur.close()
        conn.close()


def collect_rates():
    conn = get_conn()
    cur = conn.cursor()

    try:
        # читаем валюты, которые хотим отслеживать на данный момент
        currencies = os.getenv("CURRENCIES").strip().split(",")
        if not currencies:
            print("CURRENCIES пустая. Ничего не собираем")
            logging.info("CURRENCIES пустая. Ничего не собираем")
            return

        for base_currency in currencies:
            # получаем id базовой валюты
            cur.execute("SELECT id FROM bases WHERE name = %s", (base_currency,))
            row = cur.fetchone()
            if not row:
                print(f"Валюта {base_currency} не найдена в bases. Пропускаем")
                logging.info(f"Валюта {base_currency} не найдена в bases. Пропускаем")
                continue
            base_id = row[0]

            # Запрашиваем курсы
            url = f"{os.getenv('API_LATEST_URL')}?base={base_currency}"
            try:
                r = requests.get(url, timeout=5)
                data = r.json()
                rates = data.get("rates", {})

                if not rates:
                    print(f"{base_currency}: нет курсов в ответе")
                    logging.info(f"{base_currency}: нет курсов в ответе")
                    continue

                now = datetime.now(timezone.utc)
                for target, rate_val in rates.items():
                    cur.execute(
                        """
                        INSERT INTO rates
                        (base_currency, target_currency, rate, add_date)
                        VALUES (%s, %s, %s, %s) """, (base_id, target, float(rate_val), now))

                conn.commit()

            except Exception as e:
                logging.error(f"{base_currency}: {e}")
                print(f"Ошибка {base_currency}: {e}")

    except Exception as e:
        logging.error(f"Общая ошибка в collect_rates: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # один раз заполняем справочник валют
    init_bases()

    minutes = int(os.getenv("CHECK_INTERVAL_MINUTES"))
    sleep_sec = minutes * 60

    print(f"Запуск. Каждые {minutes} минут собираем курсы только по валютам из CURRENCIES")

    while True:
        collect_rates()
        print(f"Ждём {minutes} минут.")
        time.sleep(sleep_sec)
