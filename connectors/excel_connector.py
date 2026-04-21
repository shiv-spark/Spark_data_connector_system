import polars as pl
def excel_connector(file_path):
    df = pl.read_excel(file_path)
    return df       