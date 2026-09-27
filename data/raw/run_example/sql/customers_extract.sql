-- Customer dimension - deliberately WITHOUT name and email.
-- The late-delivery KPI never needs personal data; retrieving only the
-- identifier and the delivery coordinates keeps PII out of the pipeline.
SELECT
    customer_id,
    lat,
    lon
FROM customers
ORDER BY customer_id;
