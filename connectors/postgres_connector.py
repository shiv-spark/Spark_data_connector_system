import psycopg2
import pandas as pd
import polars as pl

def postgres_connector(host, database, user, password, port, query):
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port
        )
        print(f"Connected to: {host}/{database}")
        
        df = pd.read_sql(query, conn)
        print(f"Query executed — {df.shape[0]} rows fetched")
        
        conn.close()
        return pl.from_pandas(df)
    
    except Exception as e:
        raise Exception(f"PostgreSQL connection failed: {e}")