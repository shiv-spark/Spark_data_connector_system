import os
import datetime
import pandas as pd

GENERATED_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "generated"
)


def save_csv(df: pd.DataFrame, config: dict) -> str:
    """
    Saves the DataFrame as a CSV file inside generator/generated/.
    Filename: <table>_<timestamp>.csv so files never overwrite each other.

    Args:
        df:     Validated DataFrame to save
        config: Parsed config dict (needs 'table' key)

    Returns:
        Full file path of saved CSV
    """

    os.makedirs(GENERATED_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    table     = config.get("table", "output").lower()
    filename  = f"{table}_{timestamp}.csv"
    filepath  = os.path.join(GENERATED_DIR, filename)

    df.to_csv(filepath, index=False)

    print(f"[csv_writer] Saved {len(df)} rows → {filepath}")
    return filepath


if __name__ == "__main__":
    df = pd.DataFrame({
        "name":  ["Rahul", "Priya"],
        "email": ["rahul@gmail.com", "priya@gmail.com"]
    })
    config = {"table": "USERS"}
    path = save_csv(df, config)
    print(f"Saved: {path}")


