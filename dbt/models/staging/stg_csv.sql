-- models/staging/stg_orders.sql

select *
from {{ source('raw', 'tbl_user_csv') }}