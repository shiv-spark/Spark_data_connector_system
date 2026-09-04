from reverse_etl.writers.postgres_writer import postgres_writer
from reverse_etl.writers.mysql_writer import mysql_writer
from reverse_etl.writers.webhook_writer import webhook_writer
from reverse_etl.writers.salesforce_writer import salesforce_writer
from reverse_etl.writers.hubspot_writer import hubspot_writer
from reverse_etl.writers.google_sheets_writer import google_sheets_writer
from reverse_etl.writers.snowflake_writer import snowflake_writer
from reverse_etl.writers.oracle_writer import oracle_writer
from reverse_etl.writers.mongodb_writer import mongodb_writer
from reverse_etl.writers.zoho_writer import zoho_writer
from reverse_etl.writers.s3_writer import s3_writer

WRITER_MAP = {
    "postgres":      postgres_writer,
    "mysql":         mysql_writer,
    "webhook":       webhook_writer,
    "api":           webhook_writer,   # alias — same generic REST push
    "salesforce":    salesforce_writer,
    "hubspot":       hubspot_writer,
    "google_sheets": google_sheets_writer,
    "snowflake":     snowflake_writer,
    "oracle":        oracle_writer,
    "mongodb":       mongodb_writer,
    "zoho":          zoho_writer,
    "s3":            s3_writer,
}

VALID_DESTINATIONS = set(WRITER_MAP.keys())
