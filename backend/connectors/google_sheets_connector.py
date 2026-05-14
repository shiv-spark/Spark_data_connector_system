import pandas as pd
import polars as pl
import requests
from io import StringIO
import re
import json
import os


# ─────────────────────────────────────────────
# EXISTING FUNCTIONS (unchanged)
# ─────────────────────────────────────────────

def convert_to_export_url(sheet_url: str, gid: str = "0") -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        raise ValueError(f"Invalid Google Sheets URL: {sheet_url}")
    sheet_id = match.group(1)
    gid_match = re.search(r"gid=(\d+)", sheet_url)
    if gid_match:
        gid = gid_match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def clean_columns(df, engine: str = "pandas"):
    cols   = list(df.columns)
    cleaned = []
    seen    = {}
    for i, col in enumerate(cols):
        col = str(col).strip()
        if col == "" or col == "nan" or col == "None":
            col = f"col_{i}"
        col = re.sub(r"[^a-zA-Z0-9_]", "_", col)
        if re.match(r"^\d", col):
            col = f"col_{col}"
        col = col.lower()
        if col in seen:
            seen[col] += 1
            col = f"{col}_{seen[col]}"
        else:
            seen[col] = 0
        cleaned.append(col)
    if engine == "pandas":
        df.columns = cleaned
    else:
        df = df.rename(dict(zip(df.columns, cleaned)))
    return df


def find_header_row(response_text: str) -> int:
    lines = response_text.splitlines()
    for i, line in enumerate(lines):
        values    = [v.strip() for v in line.split(",")]
        non_empty = [v for v in values if v != ""]
        if len(non_empty) >= 2:
            return i
    return 0


def google_sheet_connector(sheet_url: str, engine: str = "pandas"):
    """From Single Google Sheet URL fetch data."""
    export_url   = convert_to_export_url(sheet_url)
    response     = requests.get(export_url)
    content_type = response.headers.get("Content-Type", "")

    if response.status_code != 200:
        raise ConnectionError(f"Failed to fetch sheet. Status: {response.status_code} | URL: {sheet_url}")

    if "text/html" in content_type:
        raise PermissionError(
            f"Google returned HTML instead of CSV for: {sheet_url}\n"
            "Make sheet public: Share → Anyone with the link → Viewer"
        )

    header_row = find_header_row(response.text)
    print(f"Header detected at row index: {header_row} | URL: {sheet_url}")

    if engine == "pandas":
        df = pd.read_csv(StringIO(response.text), header=header_row, skip_blank_lines=False)
        df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
        df = clean_columns(df, engine="pandas")
    elif engine == "polars":
        lines          = response.text.splitlines()
        csv_from_header = "\n".join(lines[header_row:])
        df = pl.read_csv(StringIO(csv_from_header), infer_schema_length=10000, ignore_errors=True)
        df = df[[col for col in df.columns if df[col].null_count() < len(df)]]
        df = clean_columns(df, engine="polars")
    else:
        raise ValueError(f"Unsupported engine '{engine}'. Use 'pandas' or 'polars'.")

    print(f"Loaded {df.shape[0]} rows x {df.shape[1]} cols from: {sheet_url}")
    return df


# ─────────────────────────────────────────────
# NEW — URL FILE READERS
# ─────────────────────────────────────────────

def _is_valid_sheet_url(url: str) -> bool:
    """Please check if the URL is a valid Google Sheets URL."""
    url = url.strip()
    return (
        url.startswith("http")
        and "docs.google.com/spreadsheets" in url
        and not url.startswith("#")   # comments skip
    )


def _read_urls_from_txt(file_path: str) -> list:
    """
    .txt file se URLs nikalo.
    every line one URL — empty lines and # comments skip.

    Format:
        https://docs.google.com/spreadsheets/d/abc123
        # ye comment hai — skip hoga
        https://docs.google.com/spreadsheets/d/xyz789
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    urls = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if _is_valid_sheet_url(line):
            urls.append(line)
        else:
            print(f"Skipping invalid URL: {line!r}")
    return urls


def _read_urls_from_csv(file_path: str) -> list:
    """
    Read URLs from a .csv file.
    Look for a column named 'url' or 'sheet_url'.
    If not found, use the first column.

    Format (with header):
        url,name
        https://docs.google.com/...,Sales Sheet
        https://docs.google.com/...,HR Sheet

    Format (no header — just URLs):
        https://docs.google.com/...
        https://docs.google.com/...
    """
    df = pd.read_csv(file_path)

    # URL column dhundho
    url_col = None
    for col in df.columns:
        if col.strip().lower() in ("url", "sheet_url", "link", "google_sheet"):
            url_col = col
            break

    if url_col is None:
        # Pehla column use karo
        url_col = df.columns[0]
        print(f"No 'url' column found — using first column: '{url_col}'")

    urls = []
    for val in df[url_col].dropna():
        val = str(val).strip()
        if _is_valid_sheet_url(val):
            urls.append(val)
        else:
            print(f"Skipping invalid URL: {val!r}")
    return urls


def _read_urls_from_json(file_path: str) -> list:
    """
    Read URLs from a .json file.

    Format 1 — simple array:
        ["https://docs.google.com/...", "https://docs.google.com/..."]

    Format 2 — array of objects:
        [
            {"url": "https://docs.google.com/...", "name": "Sales"},
            {"url": "https://docs.google.com/...", "name": "HR"}
        ]

    Format 3 — object with urls key:
        {
            "urls": ["https://docs.google.com/...", "https://docs.google.com/..."]
        }
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_urls = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                # Format 1 — plain string
                raw_urls.append(item)
            elif isinstance(item, dict):
                # Format 2 — object, url field dhundho
                for key in ("url", "sheet_url", "link", "google_sheet"):
                    if key in item:
                        raw_urls.append(item[key])
                        break
                else:
                    # Pehli string value use karo
                    for v in item.values():
                        if isinstance(v, str) and v.startswith("http"):
                            raw_urls.append(v)
                            break

    elif isinstance(data, dict):
        # Format 3 — urls key dhundho
        for key in ("urls", "sheet_urls", "links", "sheets"):
            if key in data and isinstance(data[key], list):
                raw_urls.extend(data[key])
                break
        else:
            # Koi bhi string values jo URLs hain
            for v in data.values():
                if isinstance(v, str) and v.startswith("http"):
                    raw_urls.append(v)

    urls = []
    for url in raw_urls:
        url = str(url).strip()
        if _is_valid_sheet_url(url):
            urls.append(url)
        else:
            print(f"Skipping invalid URL: {url!r}")

    return urls


def _read_urls_from_xlsx(file_path: str) -> list:
    """
    Read URLs from a .xlsx file.
    Look for a column named 'url' or 'sheet_url'.
    If not found, use the first column.

    Format:
        | url                              | name       |
        | https://docs.google.com/...      | Sales      |
        | https://docs.google.com/...      | HR         |
    """
    df = pd.read_excel(file_path)

    url_col = None
    for col in df.columns:
        if col.strip().lower() in ("url", "sheet_url", "link", "google_sheet"):
            url_col = col
            break

    if url_col is None:
        url_col = df.columns[0]
        print(f"No 'url' column found — using first column: '{url_col}'")

    urls = []
    for val in df[url_col].dropna():
        val = str(val).strip()
        if _is_valid_sheet_url(val):
            urls.append(val)
        else:
            print(f"Skipping invalid URL: {val!r}")
    return urls


# ─────────────────────────────────────────────
# NEW — MAIN MULTI-URL CONNECTOR
# ─────────────────────────────────────────────

def google_sheets_multi_connector(
    file_path:  str,
    engine:     str = "pandas",
    merge:      bool = True,
) -> pd.DataFrame | list:
    """
    Reads multiple Google Sheet URLs from a file (txt/csv/json/xlsx),
    fetches data from each, and optionally merges the results.

    Args:
        file_path : Path to the file containing URLs
        engine    : 'pandas' or 'polars'
        merge     : True  → merge all sheets into a single DataFrame
                    False → return a list of (url, DataFrame) tuples

    Returns:
        merge=True  → single merged DataFrame
        merge=False → [(url1, df1), (url2, df2), ...]
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"URL file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # ── Read URL file  ───────────────────────────────────────────
    reader_map = {
        ".txt":  _read_urls_from_txt,
        ".csv":  _read_urls_from_csv,
        ".json": _read_urls_from_json,
        ".xlsx": _read_urls_from_xlsx,
        ".xls":  _read_urls_from_xlsx,
    }

    reader = reader_map.get(ext)
    if not reader:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported: {list(reader_map.keys())}"
        )

    urls = reader(file_path)

    if not urls:
        raise ValueError(f"No valid Google Sheets URLs found in: {file_path}")

    print(f"Found {len(urls)} valid URL(s) in {os.path.basename(file_path)}")

    # ── Fetch data from each URL ────────────────────────────────
    results  = []
    failed   = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Fetching: {url[:80]}...")
        try:
            df = google_sheet_connector(url, engine=engine)
            # add source URL column for traceability
            if engine == "pandas":
                df["_source_url"]   = url
                df["_source_index"] = i
            else:
                df = df.with_columns([
                    pl.lit(url).alias("_source_url"),
                    pl.lit(i).alias("_source_index"),
                ])

            results.append((url, df))
            print(f"OK — {df.shape[0]} rows x {df.shape[1]} cols")

        except Exception as e:
            print(f"FAILED [{i}]: {e}")
            failed.append({"url": url, "error": str(e)})

    if not results:
        raise Exception(
            f"All {len(urls)} URLs failed to fetch.\n"
            f"Errors: {failed}"
        )

    if failed:
        print(f"\nWarning: {len(failed)}/{len(urls)} URLs failed:")
        for f in failed:
            print(f"  {f['url'][:60]}... → {f['error']}")

    # ── return merge or list ─────────────────────────────────
    if not merge:
        return results   # [(url, df), ...]

    print(f"\nMerging {len(results)} sheet(s)...")

    if engine == "pandas":
        # Column alignment — missing columns fill with NaN
        all_dfs = [df for _, df in results]
        merged  = pd.concat(all_dfs, ignore_index=True, sort=False)
        print(f"Merged: {merged.shape[0]} total rows x {merged.shape[1]} cols")
        return merged

    else:  # polars
        all_dfs = [df for _, df in results]
        # Polars strict schema match — merge only common columns 
        all_cols = set(all_dfs[0].columns)
        for df in all_dfs[1:]:
            all_cols &= set(df.columns)
        common = list(all_cols)
        merged = pl.concat([df.select(common) for df in all_dfs])
        print(f"Merged: {merged.shape[0]} total rows x {merged.shape[1]} cols")
        return merged

