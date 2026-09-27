-- Orders extract: only the columns the late-delivery workflow needs.
-- Grain of the source table: one row per order *event of insertion* (the raw
-- table is known to contain duplicate order_id rows - deduplication happens in
-- the cleaning stage, never in SQL, so the raw extract still shows the problem).
-- Optional date window: pass :start_at / :end_at (ISO strings) or NULL for all rows.
SELECT
    order_id,
    customer_id,
    restaurant_id,
    driver_id,
    city,
    created_at,
    promised_eta,
    pickup_at,
    actual_delivery_at,
    final_status,
    distance_km_estimate,
    traffic_bucket,
    weather_bucket
FROM orders
WHERE (:start_at IS NULL OR created_at >= :start_at)
  AND (:end_at   IS NULL OR created_at <  :end_at)
ORDER BY order_id;
