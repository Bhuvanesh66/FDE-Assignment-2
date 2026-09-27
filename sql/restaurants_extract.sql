-- Restaurant dimension. Coordinates are kept so the pipeline can validate them
-- (two restaurants carry impossible lat/lon values in the client data).
SELECT
    restaurant_id,
    restaurant_name,
    cuisine,
    lat,
    lon,
    manual_status_updates
FROM restaurants
ORDER BY restaurant_id;
