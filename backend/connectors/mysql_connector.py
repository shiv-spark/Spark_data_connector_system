import pymysql
import pandas as pd
import polars as pl


def mysql_connector(host, database, user, password, port, query):
    """Run `query` against a MySQL database and return the result as a Polars DataFrame.

    Mirrors connectors.postgres_connector.postgres_connector so it can be used
    as a drop-in `connector_func` for utils.ingest_runner.run_ingestion.
    """
    try:
        conn = pymysql.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=int(port) if port else 3306,
        )
        print(f"Connected to: {host}/{database}")

        df = pd.read_sql(query, conn)
        print(f"Query executed — {df.shape[0]} rows fetched")

        conn.close()
        return pl.from_pandas(df)

    except Exception as e:
        raise Exception(f"MySQL connection failed: {e}")
