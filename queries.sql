-- все курсы за указанный диапазон дат
SELECT
    b.name          AS base_currency,
    b.description   AS base_description,
    r.target_currency,
    r.rate,
    r.add_date
FROM bases b
JOIN rates r ON b.id = r.base_currency
WHERE r.add_date >= '2026-02-20 00:00:00+02'
  AND r.add_date  <= '2026-02-21 23:59:59+02'
ORDER BY
    r.add_date DESC,
    b.name,
    r.target_currency;


-- история курсов только по USD и EUR за всё время
SELECT
    b.name          AS base_currency,
    b.description   AS base_description,
    r.target_currency,
    r.rate,
    r.add_date
FROM bases b
JOIN rates r ON b.id = r.base_currency
WHERE b.name IN ('USD', 'EUR')
ORDER BY
    r.add_date DESC,
    b.name,
    r.target_currency;