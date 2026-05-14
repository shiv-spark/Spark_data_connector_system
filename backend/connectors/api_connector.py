import requests
import polars as pl
import time

def api_connector(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return pl.DataFrame(response.json())
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise Exception(f"API failed after {retries} attempts")

