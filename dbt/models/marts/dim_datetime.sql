-- Hourly datetime spine covering the trip date range. Supports time-of-day and
-- seasonality analysis and joins to weather at the zone-hour grain.

with spine as (
    {{ dbt_utils.date_spine(
        datepart="hour",
        start_date="cast('2019-01-01' as date)",
        end_date="cast('2025-12-31' as date)"
    ) }}
)

select
    date_part('epoch_second', date_hour)::number  as datetime_key,
    date_hour,
    cast(date_hour as date)                        as calendar_date,
    extract(hour   from date_hour)                 as hour_of_day,
    extract(dow    from date_hour)                 as day_of_week,
    extract(month  from date_hour)                 as month_of_year,
    extract(year   from date_hour)                 as year_number,
    case when extract(dow from date_hour) in (0, 6)
         then true else false end                  as is_weekend
from spine