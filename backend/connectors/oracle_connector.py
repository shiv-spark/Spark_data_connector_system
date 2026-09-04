import oracledb
import pandas as pd
import polars as pl


def oracle_connector(host, database, user, password, port, query):
    """Run `query` against an Oracle database and return the result as a Polars DataFrame.

    `database` is the service name (or SID) used to build the DSN. Uses
    python-oracledb in "thin" mode, so no Oracle Instant Client install is
    required. Mirrors connectors.postgres_connector.postgres_connector so it
    can be used as a drop-in `connector_func` for utils.ingest_runner.run_ingestion.
    """
    try:
        dsn = oracledb.makedsn(host, int(port) if port else 1521, service_name=database)
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
        print(f"Connected to: {host}/{database}")

        df = pd.read_sql(query, conn)
        print(f"Query executed — {df.shape[0]} rows fetched")

        conn.close()
        return pl.from_pandas(df)

    except Exception as e:
        raise Exception(f"Oracle connection failed: {e}")
