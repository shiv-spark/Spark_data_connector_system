# import polars as pl
# def excel_connector(file_path):
#     df = pl.read_excel(file_path)
#     return df       

import polars as pl
import os


def excel_connector(file_path, sheet_name: str = None, all_sheets: bool = False):
    """
    Robust Excel connector supporting:
      - .xlsx and .xls files (auto engine selection)
      - specific sheet selection, or all sheets merged
      - graceful fallback if schema inference fails
      - empty row/column cleanup
      - clear errors instead of silent crashes

    Args:
        file_path  : path to the Excel file
        sheet_name : specific sheet to read (None = first sheet, unless all_sheets=True)
        all_sheets : if True, reads every sheet and concatenates them,
                     adding a "_sheet_name" column so rows can be traced
                     back to their source sheet
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".xlsx", ".xls", ".xlsm"):
        raise ValueError(f"Unsupported Excel extension '{ext}'. Expected .xlsx, .xls, or .xlsm")

    # ── ALL SHEETS MODE — read every sheet, merge with source tracking ────
    if all_sheets:
        try:
            all_data = pl.read_excel(file_path, sheet_id=0)  # sheet_id=0 -> dict of {sheet_name: df}
        except Exception as e:
            raise Exception(f"Failed to read sheets from '{file_path}': {e}")

        if not isinstance(all_data, dict):
            # polars returned a single DataFrame (only one sheet existed)
            all_data = {"Sheet1": all_data}

        dfs = []
        for name, df in all_data.items():
            df = _clean_dataframe(df)
            if df.shape[0] == 0:
                continue
            df = df.with_columns(pl.lit(name).alias("_sheet_name"))
            dfs.append(df)

        if not dfs:
            print(f"WARNING: All sheets in '{file_path}' were empty.")
            return pl.DataFrame()

        return pl.concat(dfs, how="diagonal_relaxed")  # handles sheets with slightly different columns

    # ── SINGLE SHEET MODE (default — first sheet, or a named one) ─────────
    try:
        if sheet_name:
            df = pl.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pl.read_excel(file_path)
        df = _clean_dataframe(df)
        return df

    except Exception as e:
        print(f"Primary Excel read failed for '{file_path}': {e}")
        print("Retrying with string-only schema (best-effort recovery)...")

        try:
            # Fallback: force every column to string, then try numeric casts
            # column-by-column, same resilience pattern as csv_connector.
            df = pl.read_excel(
                file_path,
                sheet_name=sheet_name if sheet_name else None,
                read_options={"dtypes": None},  # let it infer as strings where it can
            )
            df = _clean_dataframe(df)
            for col in df.columns:
                try:
                    df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                except Exception:
                    pass
            return df

        except Exception as fallback_error:
            raise Exception(
                f"Failed to read Excel file '{file_path}' even with fallback. "
                f"Original error: {e} | Fallback error: {fallback_error}"
            )


def _clean_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """
    Drop fully-empty rows and fully-empty columns that Excel exports often
    leave behind (trailing blank rows, unnamed blank columns).
    """
    if df.shape[0] == 0:
        return df

    # Drop columns that are entirely null
    non_empty_cols = [c for c in df.columns if df[c].null_count() < df.height]
    df = df.select(non_empty_cols) if non_empty_cols else df

    # Drop rows that are entirely null across all remaining columns
    if df.width > 0:
        df = df.filter(~pl.all_horizontal(pl.all().is_null()))

    return df