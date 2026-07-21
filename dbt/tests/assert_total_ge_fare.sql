-- Business rule: total_amount should never be less than fare_amount for batch
-- trips (total includes fare plus tips/surcharges). Any row that violates this
-- is returned; a non-empty result fails the test and blocks the build.

select
    trip_key,
    fare_amount,
    total_amount
from {{ ref('fact_trips') }}
where ingest_source = 'batch'
  and total_amount < fare_amount - 0.01   -- tolerance for float rounding