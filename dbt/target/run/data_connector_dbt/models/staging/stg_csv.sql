
  create view "airflow"."raw"."stg_csv__dbt_tmp"
    
    
  as (
    -- models/staging/stg_orders.sql

select *
from "airflow"."raw"."tbl_user_csv"
  );