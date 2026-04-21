import polars as pl

def csv_connector(file_path):
    df = pl.read_csv(file_path)
    return df