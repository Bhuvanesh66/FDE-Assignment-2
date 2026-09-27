-- SQL metric layer over the modelled warehouse (data/processed/flasheats_model.sqlite).
--
-- The same KPI metrics the pandas layer computes, written as views so an analyst can query them
-- directly and so the pipeline can prove the two implementations agree (metric check
-- "SQL metric layer == pandas"). One-to-many tables are AGGREGATED IN A CTE BEFORE THE JOIN,
-- so no join can multiply orders.

DROP VIEW IF EXISTS v_m1_late_rate;
CREATE VIEW v_m1_late_rate AS
SELECT COUNT(*)                                                        AS validated_population,
       SUM(CASE WHEN late_flag = 1 THEN 1 ELSE 0 END)                  AS late_orders,
       ROUND(100.0 * SUM(CASE WHEN late_flag = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS late_rate_pct
FROM fact_order
WHERE kpi_population = 1;

DROP VIEW IF EXISTS v_m3_pre_pickup_share;
CREATE VIEW v_m3_pre_pickup_share AS
SELECT COUNT(*) AS late_orders_with_plan,
       ROUND(100.0 * SUM(MAX(pickup_overrun_min, 0))
             / NULLIF(SUM(MAX(pickup_overrun_min, 0)) + SUM(MAX(transit_overrun_min, 0)), 0), 2) AS share_before_pickup_pct
FROM fact_order
WHERE kpi_population = 1 AND late_flag = 1
  AND pickup_overrun_min IS NOT NULL AND transit_overrun_min IS NOT NULL;

DROP VIEW IF EXISTS v_m4_support_contact;
CREATE VIEW v_m4_support_contact AS
WITH contacted AS (                                   -- one row per order: aggregate before joining
    SELECT order_id, 1 AS contacted
    FROM fact_interaction
    WHERE order_id IS NOT NULL AND interaction_type IN ('SUPPORT_OPENED', 'SUPPORT_TICKET')
    GROUP BY order_id
)
SELECT CASE WHEN f.late_flag = 1 THEN 'late' ELSE 'on_time' END AS outcome,
       COUNT(*)                                          AS orders,
       SUM(COALESCE(c.contacted, 0))                     AS orders_with_support_contact,
       ROUND(100.0 * SUM(COALESCE(c.contacted, 0)) / COUNT(*), 2) AS support_contact_rate_pct
FROM fact_order f
LEFT JOIN contacted c ON c.order_id = f.order_id
WHERE f.kpi_population = 1
GROUP BY 1;

DROP VIEW IF EXISTS v_m5_intervention;
CREATE VIEW v_m5_intervention AS
WITH iv AS (
    SELECT order_id, COUNT(*) AS interventions
    FROM fact_intervention
    GROUP BY order_id
)
SELECT CASE WHEN iv.interventions > 0 THEN 'with_intervention' ELSE 'without_intervention' END AS grp,
       COUNT(*)                                                    AS orders,
       SUM(CASE WHEN f.late_flag = 1 THEN 1 ELSE 0 END)            AS late_orders,
       ROUND(100.0 * SUM(CASE WHEN f.late_flag = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_rate_pct
FROM fact_order f
LEFT JOIN iv ON iv.order_id = f.order_id
WHERE f.kpi_population = 1
GROUP BY 1;

DROP VIEW IF EXISTS v_late_rate_by_restaurant;
CREATE VIEW v_late_rate_by_restaurant AS
SELECT COALESCE(f.restaurant_id, 'UNKNOWN') AS restaurant_id, r.cuisine,
       COUNT(*) AS orders, SUM(CASE WHEN f.late_flag = 1 THEN 1 ELSE 0 END) AS late_orders,
       ROUND(100.0 * SUM(CASE WHEN f.late_flag = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS late_rate_pct
FROM fact_order f
LEFT JOIN dim_restaurant r ON r.restaurant_id = f.restaurant_id      -- many orders -> one restaurant
WHERE f.kpi_population = 1
GROUP BY 1, 2;
