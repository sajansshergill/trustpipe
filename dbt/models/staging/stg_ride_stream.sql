with source as (
    select * from {{ source('raw', 'ride_stream') }}
),

shaped as (
    select
        {{ dbt_utils.generate_surrogate_key(['event_id']) }}  as trip_key,
        vendor_id,
        pickup_ts                                             as pickup_at,
        cast(null as timestamp)                               as dropoff_at,
        cast(null as number)                                  as trip_seconds,
        cast(null as number)                                  as passenger_count,
        cast(null as float)                                   as trip_distance,
        pu_location_id,
        do_location_id,
        fare_amount,
        cast(null as float)                                   as tip_amount,
        fare_amount                                           as total_amount,
        cast(null as number)                                  as payment_type,
        'stream'                                              as ingest_source
    from source
    -- de-duplicate on event_id so replays never double-count into the fact
    qualify row_number() over (partition by event_id order by pickup_ts) = 1
)

select * from shaped