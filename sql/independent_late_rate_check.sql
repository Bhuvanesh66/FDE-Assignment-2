-- Independent SQL re-computation of the headline KPI, used ONLY to cross-check
-- the pandas pipeline (Phase 18 "independent metric validation").
-- It applies the same population definition as the pipeline's
-- "validated" late-delivery rate:
--   * one row per order (duplicate order_id rows collapsed to the first row by rowid)
--   * final_status normalised (trim + lower) == 'delivered'
--   * promised_eta and actual_delivery_at present
--   * promised_eta >= created_at              (rule TS-01)
--   * actual_delivery_at >= pickup_at         (rule TS-02)
-- SQLite compares ISO-8601 strings lexicographically, which is valid here
-- because every timestamp uses the same YYYY-MM-DDTHH:MM:SS[.ffffff] layout.
WITH first_rows AS (
    SELECT MIN(rowid) AS rid
    FROM orders
    GROUP BY order_id
),
dedup AS (
    SELECT o.*
    FROM orders o
    JOIN first_rows f ON f.rid = o.rowid
),
population AS (
    SELECT
        order_id,
        (julianday(actual_delivery_at) - julianday(promised_eta)) * 24 * 60 AS delay_min
    FROM dedup
    WHERE lower(trim(final_status)) = 'delivered'
      AND promised_eta IS NOT NULL AND trim(promised_eta) <> ''
      AND actual_delivery_at IS NOT NULL AND trim(actual_delivery_at) <> ''
      AND promised_eta >= created_at
      AND (pickup_at IS NULL OR actual_delivery_at >= pickup_at)
)
SELECT
    COUNT(*)                                                   AS valid_delivered,
    SUM(CASE WHEN delay_min > 0 THEN 1 ELSE 0 END)             AS late_orders,
    ROUND(100.0 * SUM(CASE WHEN delay_min > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS late_rate_pct,
    SUM(CASE WHEN delay_min > 10 THEN 1 ELSE 0 END)            AS late_over_10_orders
FROM population;
