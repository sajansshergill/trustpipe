-- Conformed zone dimension, seeded from the TLC taxi-zone lookup.
-- Load the lookup CSV as a dbt seed (seeds/taxi_zone_lookup.csv).

with zones as (
    select
        locationid   as zone_id,
        borough,
        zone         as zone_name,
        service_zone
    from {{ ref('taxi_zone_lookup') }}
)

select
    zone_id,
    borough,
    zone_name,
    service_zone
from zones