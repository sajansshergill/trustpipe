-- Unifies the batch (historical parquet) and stream (Kafka) trip sources into a
-- single grain before they flow into the fact table. The ingest_source column is
-- preserved so downstream consumers can slice by pipeline path.

{{ dbt_utils.union_relations(
    relations=[
        ref('stg_yellow_trips'),
        ref('stg_ride_stream'),
    ]
) }}