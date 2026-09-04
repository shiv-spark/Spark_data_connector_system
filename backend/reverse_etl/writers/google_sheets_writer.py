"""
Writes rows OUT to a Google Sheet (append, or overwrite-then-write).
Uses the same google-api-python-client already in requirements.txt
(pulled in for connectors/google_sheets_connector.py's read side).

config keys:
  service_account_json  (dict — the service-account credentials JSON)
  spreadsheet_id
  sheet_name             (default "Sheet1")
"""

import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service(config: dict):
    creds_raw = config.get("service_account_json")
    if isinstance(creds_raw, str):
        creds_raw = json.loads(creds_raw)
    if not creds_raw:
        raise ValueError("google_sheets destination requires service_account_json")
    creds = service_account.Credentials.from_service_account_info(creds_raw, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def google_sheets_writer(records: list, config: dict, object_name: str,
                          upsert_key: str | None, write_mode: str, batch_size: int = 1000) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    spreadsheet_id = config.get("spreadsheet_id")
    sheet_name = object_name or config.get("sheet_name", "Sheet1")
    if not spreadsheet_id:
        raise ValueError("google_sheets destination requires spreadsheet_id")

    service = _get_service(config)
    columns = list(records[0].keys())
    values = [columns] + [[str(r.get(c, "")) for c in columns] for r in records]

    try:
        if write_mode == "insert" or write_mode == "upsert":
            # Upsert-by-key isn't a native Sheets concept — treat as append,
            # since a Sheet has no unique-constraint enforcement of its own.
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values[1:]},
            ).execute()
        else:  # "update"/overwrite
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:ZZ"
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1",
                valueInputOption="RAW", body={"values": values},
            ).execute()
        return {"success": len(records), "failed": 0, "errors": []}
    except Exception as e:
        return {"success": 0, "failed": len(records), "errors": [str(e)]}
