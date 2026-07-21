-- Central fact. Clustered on pickup date to prune the multi-terabyte scan surface
-- (see docs/performance.md for before/after query timings).

{{ config(
    materialized='table',
    cluster_by=['cast(pickup_at as date)', 'pu_location_id']
) }}

with trips as (
    select * from {{ ref('int_trips_unioned') }}
),

weather as (
    select * from {{ ref('stg_weather') }}
),

enriched as (
    select
        t.trip_key,
        t.vendor_id,
        t.pu_location_id,
        t.do_location_id,
        date_part('epoch_second', date_trunc('hour', t.pickup_at))::number
                                                    as pickup_datetime_key,
        t.pickup_at,
        t.dropoff_at,
        t.trip_seconds,
        t.passenger_count,
        t.trip_distance,
        t.fare_amount,
        t.tip_amount,
        t.total_amount,
        t.payment_type,
        t.ingest_source,
        w.temp_c,
        w.precip_mm,
        w.wind_kph
    from trips t
    left join weather w
        on t.pu_location_id = w.zone_id
       and date_trunc('hour', t.pickup_at) = w.weather_hour
)

select * from enriched