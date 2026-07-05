# import polars as pl

# def csv_connector(file_path):
#     df = pl.read_csv(file_path)
#     return df


import polars as pl

def csv_connector(file_path):
    """Read CSV with automatic error recovery"""
    try:
        return pl.read_csv(file_path, ignore_errors=True, try_parse_dates=True)
    except:
        # Fallback: read as strings, then try to convert
        df = pl.read_csv(file_path, infer_schema_length=0, ignore_errors=True)
        for col in df.columns:
            try:
                df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
            except:
                pass
        return df
# import polars as pl
# from pathlib import Path
# import chardet

# def csv_connector(file_path):
#     """
#     Handles: encoding, delimiters, headers, quotes, escape chars, multiline, nulls, dates, mixed types
#     """
#     file_path = Path(file_path)
    
#     # 1. Auto-detect encoding
#     with open(file_path, 'rb') as f:
#         raw_data = f.read(10000)
#         encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
    
#     # 2. Try multiple strategies sequentially
#     strategies = [
#         # Strategy 1: Full auto-detection (best for clean CSVs)
#         lambda: pl.read_csv(
#             file_path,
#             encoding=encoding,
#             try_parse_dates=True,
#             infer_schema_length=100000,
#             null_values=['', 'null', 'NULL', 'None', 'NA', 'N/A', 'nan', 'NaN'],
#             ignore_errors=False,  # Don't skip anything initially
#         ),
        
#         # Strategy 2: With error recovery (skip problematic rows but keep rest)
#         lambda: pl.read_csv(
#             file_path,
#             encoding=encoding,
#             try_parse_dates=True,
#             infer_schema_length=100000,
#             null_values=['', 'null', 'NULL', 'None', 'NA', 'N/A', 'nan', 'NaN'],
#             ignore_errors=True,  # Skip bad rows
#             truncate_ragged_lines=True,  # Handle inconsistent columns
#         ),
        
#         # Strategy 3: Read everything as string (preserve ALL data)
#         lambda: pl.read_csv(
#             file_path,
#             encoding=encoding,
#             infer_schema_length=0,  # No inference
#             ignore_errors=True,
#             truncate_ragged_lines=True,
#             null_values=[],
#             has_header=True,
#         ).with_columns([
#             pl.all().cast(pl.Utf8, strict=False)  # Everything as string
#         ]),
        
#         # Strategy 4: Without header (if header detection fails)
#         lambda: pl.read_csv(
#             file_path,
#             encoding=encoding,
#             has_header=False,
#             ignore_errors=True,
#             truncate_ragged_lines=True,
#             null_values=['', 'null', 'NULL', 'None', 'NA', 'N/A'],
#         ),
        
#         # Strategy 5: Auto-detect delimiter and try again
#         lambda: detect_delimiter_and_read(file_path, encoding),
#     ]
    
#     # Try each strategy
#     for i, strategy in enumerate(strategies):
#         try:
#             df = strategy()
            
#             # Verify we got data
#             if df.height > 0:
#                 print(f"✓ Success: Strategy {i+1} loaded {df.height} rows, {df.width} columns")
                
#                 # If all columns are string type, try to cast numeric/dates automatically (without losing data)
#                 if all(dtype == pl.Utf8 for dtype in df.dtypes):
#                     df = auto_cast_columns(df)
                
#                 return df
#         except Exception as e:
#             print(f"✗ Strategy {i+1} failed: {str(e)[:100]}")
#             continue
    
#     # If all strategies fail, read raw line by line (guaranteed to get data)
#     print("⚠ All strategies failed, reading raw...")
#     return read_raw_csv(file_path)


# def detect_delimiter_and_read(file_path, encoding):
#     """Auto-detect delimiter and read CSV"""
#     import csv
    
#     with open(file_path, 'r', encoding=encoding) as f:
#         sample = f.read(1024)
#         sniffer = csv.Sniffer()
#         delimiter = sniffer.sniff(sample).delimiter
    
#     return pl.read_csv(
#         file_path,
#         encoding=encoding,
#         separator=delimiter,
#         ignore_errors=True,
#         truncate_ragged_lines=True,
#     )


# def auto_cast_columns(df):
#     """Automatically cast string columns to appropriate types without losing data"""
#     for col in df.columns:
#         # Try integer
#         try:
#             df = df.with_columns(pl.col(col).cast(pl.Int64, strict=False))
#             if df[col].null_count() < df.height * 0.1:  # If less than 10% nulls
#                 continue
#         except:
#             pass
        
#         # Try float
#         try:
#             df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
#             if df[col].null_count() < df.height * 0.1:
#                 continue
#         except:
#             pass
        
#         # Try date
#         try:
#             df = df.with_columns(pl.col(col).str.strptime(pl.Date, "%Y-%m-%d", strict=False))
#             if df[col].null_count() < df.height * 0.1:
#                 continue
#         except:
#             pass
        
#         # Try datetime
#         try:
#             df = df.with_columns(pl.col(col).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False))
#             if df[col].null_count() < df.height * 0.1:
#                 continue
#         except:
#             pass
    
#     return df


# def read_raw_csv(file_path):
#     """Last resort: Read raw CSV line by line (100% data preservation)"""
#     import csv
    
#     rows = []
#     with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
#         reader = csv.reader(f)
#         for row in reader:
#             rows.append(row)
    
#     if not rows:
#         raise ValueError("File is empty or unreadable")
    
#     # Find max columns
#     max_cols = max(len(row) for row in rows)
    
#     # Pad rows to equal length
#     for row in rows:
#         while len(row) < max_cols:
#             row.append('')
    
#     # Convert to DataFrame
#     df = pl.DataFrame(rows[1:] if rows else [], schema=[f'col_{i}' for i in range(max_cols)])
    
#     # If header exists, use it
#     if rows:
#         header = [f'col_{i}' if not h else h for i, h in enumerate(rows[0])]
#         df.columns = header
    
#     print(f"✓ Raw read: {df.height} rows, {df.width} columns")
#     return df



# df = csv_connector('D:\MyProject\Spark_data_connector_system\Dataset\dairy_dataset.csv')
# print(df.head())
# print(f"Shape: {df.shape}")

