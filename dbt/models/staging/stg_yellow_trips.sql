with source as (
    select * from {{ source('raw', 'yellow_trips') }}
),

cleaned as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'vendor_id', 'tpep_pickup_datetime', 'tpep_dropoff_datetime'
        ]) }}                                     as trip_key,
        vendor_id,
        tpep_pickup_datetime                      as pickup_at,
        tpep_dropoff_datetime                     as dropoff_at,
        datediff('second', tpep_pickup_datetime,
                 tpep_dropoff_datetime)           as trip_seconds,
        passenger_count,
        trip_distance,
        pu_location_id,
        do_location_id,
        fare_amount,
        tip_amount,
        total_amount,
        payment_type,
        'batch'                                   as ingest_source
    from source
    -- guardrails against physically impossible trips slipping past the contract
    where tpep_dropoff_datetime > tpep_pickup_datetime
      and trip_distance >= 0
)

select * from cleaned