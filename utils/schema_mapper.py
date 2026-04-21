import polars as pl

def map_dtype(dtype):

    if dtype == pl.Int64:
        return "INTEGER"

    elif dtype == pl.Float64:
        return "FLOAT"

    elif dtype == pl.Boolean:
        return "BOOLEAN"

    elif dtype == pl.Date:
        return "DATE"

    else:
        return "TEXT"