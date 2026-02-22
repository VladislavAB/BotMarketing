# АСИНХРОННАЯ ВЕРСИЯ

import asyncio
import os
import logging
from datetime import datetime, timezone

import aiohttp
import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(filename=os.getenv("LOG_FILE", "logs/errors.log"), level=logging.ERROR,
                    format="%(asctime)s %(message)s")


async def get_pool():
    return await asyncpg.create_pool(
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"))


async def init_bases():
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bases (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(3) UNIQUE NOT NULL,
                    description TEXT NOT NULL)""")

            await conn.execute("""
                                CREATE TABLE IF NOT EXISTS rates (
                                id SERIAL PRIMARY KEY,
                                base_currency INTEGER REFERENCES bases(id) ON DELETE CASCADE,
                                target_currency VARCHAR(3) NOT NULL,
                                rate NUMERIC(20,10) NOT NULL,
                                add_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)""")

            logging.info("Создали таблицы")

            url = os.getenv("API_CURRENCIES_URL")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status != 200:
                        logging.error(f"По API_CURRENCIES_URL: {resp.status}")
                        return

                    currencies = await resp.json()

            for currency, description in currencies.items():
                await conn.execute(
                    """
                    INSERT INTO bases (name, description)
                    VALUES ($1, $2)
                    ON CONFLICT (name) DO NOTHING
                    """, currency, description)

    except Exception as e:
        logging.error(f"Ошибка init_bases: {e}")
        print(f"Ошибка init_bases: {e}")
    finally:
        await pool.close()


async def fetch_one_currency(session, pool, base_currency: str):
    """ Запрашивает курсы для одной валюты и сохраняет их """

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM bases WHERE name = $1", base_currency)
            if not row:
                print(f"{base_currency} не найдена в bases")
                return 0

            base_id = row["id"]

        url = f"{os.getenv('API_LATEST_URL')}?base={base_currency}"

        async with session.get(url, timeout=5) as resp:
            if resp.status != 200:
                logging.error(f"Для {base_currency}: {resp.status}")
                return 0

            data = await resp.json()
            rates = data.get("rates", {})

            if not rates:
                print(f"{base_currency}: нет курсов")
                return 0

            now = datetime.now(timezone.utc)
            inserted = 0

            async with pool.acquire() as conn:
                for target, rate_val in rates.items():
                    await conn.execute(
                        """
                        INSERT INTO rates
                        (base_currency, target_currency, rate, add_date)
                        VALUES ($1, $2, $3, $4)
                        """,
                        base_id, target, float(rate_val), now
                    )
                    inserted += 1

            print(f"В {base_currency} добавлено {inserted} курсов")
            return inserted

    except Exception as e:
        logging.error(f"{base_currency}: {e}")
        print(f"Ошибка {base_currency}: {e}")
        return 0


async def collect_rates():
    pool = await get_pool()
    try:
        currencies = os.getenv("CURRENCIES").strip().split(",")
        if not currencies:
            print("CURRENCIES пустая. ничего не собираем")
            return

        async with aiohttp.ClientSession() as session:
            # запускаем все запросы параллельно
            tasks = [fetch_one_currency(session, pool, base_currency) for base_currency in currencies]
            await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Ошибка сбора курсов: {e}")
        print(f"Ошибка сбора курсов: {e}")
    finally:
        await pool.close()


async def main():
    await init_bases()

    minutes = int(os.getenv("CHECK_INTERVAL_MINUTES"))
    sleep_sec = minutes * 60
    print(f"Асинхронный запуск. Каждые {minutes} мин собираем параллельно")

    while True:
        await collect_rates()
        await asyncio.sleep(sleep_sec)


if __name__ == "__main__":
    asyncio.run(main())
