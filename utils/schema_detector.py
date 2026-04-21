import pandas as pd
import polars as pl

def detect_schema(df):
    """Works with both Pandas and Polars DataFrames"""
    
    schema = {}
    
    if isinstance(df, pl.DataFrame):
        # Polars has .schema natively
        for column, dtype in df.schema.items():
            schema[column] = str(dtype)
    
    elif isinstance(df, pd.DataFrame):
        # Pandas uses .dtypes
        for column, dtype in df.dtypes.items():
            schema[column] = str(dtype)
    
    else:
        raise TypeError(f"Unsupported DataFrame type: {type(df)}")
    
    print("Detected Schema:")
    for col, dtype in schema.items():
        print(f"  {col}: {dtype}")
    
    return schema