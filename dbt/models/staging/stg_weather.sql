with source as (
    select * from {{ source('raw', 'weather') }}
)

select
    zone_id,
    date_trunc('hour', observed_at)  as weather_hour,
    avg(temp_c)                      as temp_c,
    avg(precip_mm)                   as precip_mm,
    avg(wind_kph)                    as wind_kph
from source
group by 1, 2