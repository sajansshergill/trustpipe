-- Small conformed vendor dimension. TLC documents vendor_id codes; unknown codes
-- surface as 'Unknown' rather than being dropped, so the fact never loses rows.

with vendors as (
    select 1 as vendor_id, 'Creative Mobile Technologies'  as vendor_name union all
    select 2, 'Curb Mobility / VeriFone'                                  union all
    select 6, 'Myle Technologies'                                         union all
    select 7, 'Helix'
)

select
    v.vendor_id,
    coalesce(v.vendor_name, 'Unknown') as vendor_name
from vendors v