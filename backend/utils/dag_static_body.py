
import hashlib
import json
import shutil
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import smtplib, traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}


def _normalize(path):
    """Convert all backslash variants to forward slash."""
    if not path:
        return path
    return path.replace("\\\\", "/").replace("\\", "/")


def to_container_path(path):
    """
    Translate any user-provided path → Airflow container path.

    Accepts all three formats:
      • Windows path  : D:/DATA_ENG/.../data/sales
      • Backend path  : /app/data/sales
      • Already correct: /opt/airflow/data/sales  (returned as-is)
    """
    if not path:
        return path

    n = _normalize(path)

    # 1. Windows dataset path → Airflow dataset path
    n_dataset_win = _normalize(DATASET_BASE_WIN)
    if n_dataset_win and n.startswith(n_dataset_win):
        return n.replace(n_dataset_win, DATASET_BASE_CON)

    # 2. Windows data path → Airflow data path
    n_windows = _normalize(WINDOWS_PATH)
    if n_windows and n.startswith(n_windows):
        return n.replace(n_windows, CONTAINER_PATH)

    # 3. Backend dataset path → Airflow dataset path
    if n.startswith("/app/dataset"):
        return n.replace("/app/dataset", DATASET_BASE_CON)

    # 4. Backend data path → Airflow data path
    if n.startswith("/app/data"):
        return n.replace("/app/data", CONTAINER_PATH)

    # 5. Already an Airflow container path — return as-is
    return n


def to_backend_path(path):
    """
    Translate Airflow container path → backend container path.
    Called just before sending file_path to the /ingest_* API.

      /opt/airflow/data/sales/file.csv    → /app/data/sales/file.csv
      /opt/airflow/dataset/file.xlsx      → /app/dataset/file.xlsx
    """
    if not path:
        return path

    n = _normalize(path)

    # Airflow dataset path → backend dataset path
    n_dataset_con = _normalize(DATASET_BASE_CON)
    if n_dataset_con and n.startswith(n_dataset_con):
        return n.replace(n_dataset_con, "/app/dataset")

    # Airflow data path → backend data path
    n_container = _normalize(CONTAINER_PATH)
    if n_container and n.startswith(n_container):
        return n.replace(n_container, "/app/data")

    # Already a backend path — return as-is
    return n


# Keep old name as alias so existing code referencing to_windows_path still works
to_windows_path = to_backend_path


def _ensure_pipeline_folders(connector_type=None, source_label=None):
    """
    Create (and return) the processed/ and failed/ folders used for hash-
    and URL-based dedup + file archiving.

    connector_type : which type this call is for. Falls back to the
                      module-level CONNECTOR_TYPE global for single-source
                      DAGs (backward compatible).
    source_label    : optional sub-folder name. Multi-source pipelines pass
                      something like "source_1_csv" so each source gets its
                      own processed/failed history and hash records never
                      collide across sources sharing one pipeline.
    """
    connector_type = connector_type or CONNECTOR_TYPE
    base = DATASET_PIPELINE_CON if connector_type in ("csv", "excel") else PIPELINE_CON_ROOT
    if source_label:
        base = os.path.join(base, source_label)
    processed = os.path.join(base, "processed")
    failed    = os.path.join(base, "failed")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(failed,    exist_ok=True)
    print(f"Folders ready — processed: {processed} | failed: {failed}")
    return processed, failed


# ─────────────────────────────────────────────────────────────────────────────
# HASH DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────────────

def _get_file_hash(filepath):
    """MD5 hash of file content — same content = same hash."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_already_processed(file_hash, processed_dir):
    if not os.path.exists(processed_dir):
        return False
    for fname in os.listdir(processed_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(processed_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                record = json.load(fh)
            if record.get("file_hash") == file_hash:
                print(f"Already processed (hash match): {fname} — skipping.")
                return True
        except Exception:
            continue
    return False


def _save_file_record(filepath, file_hash, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = os.path.basename(filepath)
    dest = os.path.join(dest_folder, f"{name}_{ts}.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({
            "original_filename": name,
            "file_hash":         file_hash,
            "processed_at":      ts,
            "pipeline":          PIPELINE_ID,
        }, fh, indent=2)
    print(f"Hash record saved: {dest}")


# def _move_file(src, dest_folder):
#     os.makedirs(dest_folder, exist_ok=True)
#     name, ext = os.path.splitext(os.path.basename(src))
#     ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
#     dest = os.path.join(dest_folder, f"{name}_{ts}{ext}")
#     shutil.copy2(src, dest)
#     os.remove(src)
#     print(f"Moved: {src} -> {dest}")
# def _move_file(src, dest_folder):
#     os.makedirs(dest_folder, exist_ok=True)
#     name, ext = os.path.splitext(os.path.basename(src))
#     ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
#     dest = os.path.join(dest_folder, f"{name}_{ts}{ext}")
#     try:
#         shutil.copy2(src, dest)
#         os.remove(src)
#         print(f"Moved: {src} -> {dest}")
#     except PermissionError as e:
#         # Data was already successfully ingested at this point — a failure
#         # to move/delete the source file (e.g. cross-container ownership
#         # mismatch) should not fail the whole pipeline run. Log and continue;
#         # the hash record already saved will prevent this file from being
#         # reprocessed on the next run anyway.
#         print(f"WARNING: Could not move/delete {src} due to permissions: {e}. "
#               f"File will remain in place, but hash-based dedup will prevent reprocessing.")
def _move_file(src, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(src))
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(dest_folder, f"{name}_{ts}{ext}")
    try:
        shutil.copy2(src, dest)
        os.remove(src)
        print(f"Moved: {src} -> {dest}")
    except PermissionError as e:
        # Data was already successfully ingested at this point — a failure
        # to move/delete the source file (e.g. cross-container ownership
        # mismatch) should not fail the whole pipeline run. Log and continue;
        # the hash record already saved will prevent this file from being
        # reprocessed on the next run anyway.
        print(f"WARNING: Could not move/delete {src} due to permissions: {e}. "
              f"File will remain in place, but hash-based dedup will prevent reprocessing.")

def _url_already_handled(url, processed_dir, failed_dir):
    """Only check processed/ — failed/ is not checked to allow retries."""
    if not os.path.exists(processed_dir):
        return False
    for fname in os.listdir(processed_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(processed_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                record = json.load(fh)
            if record.get("url") == url:
                print(f"URL already successfully processed — skipping: {url}")
                return True
        except Exception:
            continue
    return False


def _save_url_record(url, dest_folder, prefix="url"):
    os.makedirs(dest_folder, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(dest_folder, f"{prefix}_{ts}.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"url": url, "timestamp": ts, "pipeline": PIPELINE_ID}, fh, indent=2)
    print(f"URL record saved: {dest}")

def _log_skip_metrics(table_name, connector_type, file_name=None, reason=""):
    """
    Directly logs a SKIPPED entry to pipeline_metrics for hash/URL dedup
    skips and path-not-found skips — these never call the backend
    /ingest_* API, so load_to_db()'s own log_pipeline_metrics() never
    runs for them. Without this, dashboard's pipeline_metrics-based
    charts never show these skips even though airflow_pipeline_runs does.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO pipeline_metrics (
                pipeline_id, table_name, rows_inserted, rows_skipped,
                rows_failed, duration_sec, evolved_columns, match_pct,
                file_name, connector_type, option, status, error_message
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            PIPELINE_ID, table_name, 0, 1, 0, 0.0, [], 100.0,
            file_name, connector_type, None, "SKIPPED", reason,
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Skip metrics logged — {file_name or 'source'} | {reason}")
    except Exception as e:
        print(f"Skip metrics log failed: {e}")


def _ingest_file(container_file, endpoint, option, table_name, sync_mode, incremental_column,
                  quality_payload_fields=None):
    """
    Send file to backend /ingest_* API.
    container_file is the Airflow path — translate to backend path before sending.

    option/table_name/sync_mode/incremental_column are now explicit params
    (rather than module globals) so this works for both single-source DAGs
    and multi-source DAGs where each source can carry its own option.

    quality_payload_fields carries the optional pre-ingest (dataframe-level)
    and post-load (DB-level) quality gate settings — see
    _process_one_source() for where these come from.
    """
    backend_file = to_backend_path(container_file)
    print(f"Airflow path : {container_file}")
    print(f"Backend path : {backend_file}")
    payload = {
        "file_path":          backend_file,   # ✅ backend-readable path
        "option":             option,
        "table_name":         table_name,
        "sync_mode":          sync_mode,
        "incremental_column": incremental_column,
        "pipeline_id": PIPELINE_ID,
        **(quality_payload_fields or {}),
    }
    res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=60)
    print(f"Status: {res.status_code} | Response: {res.text}")
    return res.status_code == 200 and res.json().get("status") == "SUCCESS"


def _update_option_in_dag(new_option):
    import re as _re
    with open(__file__, "r", encoding="utf-8") as fh:
        content = fh.read()
    content = _re.sub(r'OPTION\s*=\s*"3"', f'OPTION = "{new_option}"', content)
    with open(__file__, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"OPTION updated to {new_option}")


def _send_email(status, error="", dag_run_id=None):
    EMAIL_SENDER   = os.getenv("EMAIL_SENDER",   "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
    SMTP_HOST      = os.getenv("SMTP_HOST",      "smtp.gmail.com")
    SMTP_PORT      = int(os.getenv("SMTP_PORT",  "587"))

    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("Email config missing — skipping email alert.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER
        msg["Subject"] = f"Pipeline {status.upper()}: {PIPELINE_ID}"

        emoji      = "OK" if status == "success" else "FAILED"
        error_line = f"Error    : {error}" if error else ""
        body = (
            f"Pipeline {status.upper()} Alert\n"
            f"{emoji} Pipeline : {PIPELINE_ID}\n"
            f"   Connector: {CONNECTOR_TYPE}\n"
            f"   Table    : {TABLE_NAME}\n"
            f"   Status   : {status.upper()}\n"
            f"   {error_line}\n"
            f"Airflow UI: http://localhost:8081\n\n"
            f"Full logs attached."
        )
        msg.attach(MIMEText(body, "plain"))

        log_content, _ = _collect_logs(dag_run_id) if dag_run_id else ("No run ID provided.", None)
        log_bytes = log_content.encode("utf-8")

        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(log_bytes)
        encoders.encode_base64(attachment)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        attachment.add_header(
            "Content-Disposition",
            f"attachment; filename={PIPELINE_ID}_{status}_{ts}.log"
        )
        msg.attach(attachment)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"Email sent: {status.upper()}")

    except Exception as e:
        print(f"Email send failed: {e}")
        print(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# CORE PER-SOURCE PROCESSING
# Shared by single-source run_connector() AND multi-source run_multi_source().
# All the hash dedup / URL dedup / folder listing / file moving / path
# translation logic lives here exactly once.
# ─────────────────────────────────────────────────────────────────────────────

def _process_one_source(cfg, source_label=None):
    """
    Process exactly one source described by `cfg` (a dict with uppercase
    keys — CONNECTOR_TYPE, OPTION, TABLE_NAME, SYNC_MODE, INCREMENTAL_COLUMN,
    plus whichever of FOLDER_PATH/FILE_PATH/SHEET_URL/API_URL/S3_*/SRC_PG_*/
    SF_* apply to that connector type).

    source_label is used to namespace the processed/failed folders (so
    multiple sources in one multi-source pipeline never share hash/URL
    dedup history) and for clearer log lines. It's None for single-source
    pipelines, which keeps their processed/failed folder layout unchanged.

    Returns "SUCCESS" or "SKIPPED". Raises Exception on failure.
    """
    connector_type      = cfg["CONNECTOR_TYPE"]
    option              = cfg["OPTION"]
    table_name          = cfg["TABLE_NAME"]
    sync_mode           = cfg.get("SYNC_MODE", "full")
    incremental_column  = cfg.get("INCREMENTAL_COLUMN")

    folder_path  = cfg.get("FOLDER_PATH")
    file_path    = cfg.get("FILE_PATH")
    sheet_url    = cfg.get("SHEET_URL")
    api_url      = cfg.get("API_URL")
    api_config   = cfg.get("API_CONFIG") or {}

    s3_bucket    = cfg.get("S3_BUCKET")
    s3_key       = cfg.get("S3_KEY")
    s3_file_type = cfg.get("S3_FILE_TYPE", "csv")
    s3_access_key  = cfg.get("S3_ACCESS_KEY")
    s3_secret_key  = cfg.get("S3_SECRET_KEY")

    src_pg_host     = cfg.get("SRC_PG_HOST")
    src_pg_db       = cfg.get("SRC_PG_DB")
    src_pg_user     = cfg.get("SRC_PG_USER")
    src_pg_password = cfg.get("SRC_PG_PASSWORD")
    src_pg_port     = cfg.get("SRC_PG_PORT", "5432")
    pg_query        = cfg.get("PG_QUERY")

    src_my_host     = cfg.get("SRC_MY_HOST")
    src_my_db       = cfg.get("SRC_MY_DB")
    src_my_user     = cfg.get("SRC_MY_USER")
    src_my_password = cfg.get("SRC_MY_PASSWORD")
    src_my_port     = cfg.get("SRC_MY_PORT", "3306")
    my_query        = cfg.get("MY_QUERY")

    src_ora_host     = cfg.get("SRC_ORA_HOST")
    src_ora_db       = cfg.get("SRC_ORA_DB")
    src_ora_user     = cfg.get("SRC_ORA_USER")
    src_ora_password = cfg.get("SRC_ORA_PASSWORD")
    src_ora_port     = cfg.get("SRC_ORA_PORT", "1521")
    ora_query        = cfg.get("ORA_QUERY")

    src_mongo_host             = cfg.get("SRC_MONGO_HOST")
    src_mongo_db               = cfg.get("SRC_MONGO_DB")
    src_mongo_user             = cfg.get("SRC_MONGO_USER")
    src_mongo_password         = cfg.get("SRC_MONGO_PASSWORD")
    src_mongo_port             = cfg.get("SRC_MONGO_PORT", "27017")
    src_mongo_connection_string = cfg.get("SRC_MONGO_CONNECTION_STRING")
    mongo_collection            = cfg.get("MONGO_COLLECTION")
    mongo_query                 = cfg.get("MONGO_QUERY")

    sf_account   = cfg.get("SF_ACCOUNT")
    sf_user      = cfg.get("SF_USER")
    sf_password  = cfg.get("SF_PASSWORD")
    sf_warehouse = cfg.get("SF_WAREHOUSE")
    sf_database  = cfg.get("SF_DATABASE")
    sf_schema    = cfg.get("SF_SCHEMA", "PUBLIC")
    sf_role      = cfg.get("SF_ROLE")
    sf_query     = cfg.get("SF_QUERY")

    sf_crm_access_token   = cfg.get("SF_CRM_ACCESS_TOKEN")
    sf_crm_instance_url   = cfg.get("SF_CRM_INSTANCE_URL")
    sf_crm_login_url      = cfg.get("SF_CRM_LOGIN_URL", "https://login.salesforce.com")
    sf_crm_client_id      = cfg.get("SF_CRM_CLIENT_ID")
    sf_crm_client_secret  = cfg.get("SF_CRM_CLIENT_SECRET")
    sf_crm_username       = cfg.get("SF_CRM_USERNAME")
    sf_crm_password       = cfg.get("SF_CRM_PASSWORD")
    sf_crm_security_token = cfg.get("SF_CRM_SECURITY_TOKEN")
    sf_crm_object_name    = cfg.get("SF_CRM_OBJECT_NAME")
    sf_crm_fields         = cfg.get("SF_CRM_FIELDS")
    sf_crm_soql_query     = cfg.get("SF_CRM_SOQL_QUERY")

    hs_access_token = cfg.get("HS_ACCESS_TOKEN")
    hs_object_type  = cfg.get("HS_OBJECT_TYPE", "contacts")
    hs_properties   = cfg.get("HS_PROPERTIES")

    zoho_access_token  = cfg.get("ZOHO_ACCESS_TOKEN")
    zoho_refresh_token = cfg.get("ZOHO_REFRESH_TOKEN")
    zoho_client_id     = cfg.get("ZOHO_CLIENT_ID")
    zoho_client_secret = cfg.get("ZOHO_CLIENT_SECRET")
    zoho_accounts_url  = cfg.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com")
    zoho_api_domain    = cfg.get("ZOHO_API_DOMAIN", "https://www.zohoapis.com")
    zoho_module        = cfg.get("ZOHO_MODULE")
    zoho_fields        = cfg.get("ZOHO_FIELDS")
    zoho_criteria      = cfg.get("ZOHO_CRITERIA")

    # ── Optional quality gates — same shape as Direct Ingest's /ingest_* API.
    # DF-level gate runs BEFORE the DB write (real "block" is possible);
    # DB-level gate runs AFTER, against the just-loaded table (see
    # utils/ingest_runner.py for the on_fail semantics of each).
    # CUSTOM_SCHEMA (optional): {"column": "integer|float|boolean|date|timestamp|text|json"}
    # — a user-defined schema override, enforced instead of the auto-detected
    # dtypes for whichever columns are listed. Folded into the same dict so it
    # rides along with every payload below via **quality_payload_fields.
    quality_payload_fields = {
        "quality_connection_id": cfg.get("QUALITY_CONNECTION_ID"),
        "quality_config":        cfg.get("QUALITY_CONFIG"),
        "quality_on_fail":       cfg.get("QUALITY_ON_FAIL") or "warn",
        "df_quality_config":     cfg.get("DF_QUALITY_CONFIG"),
        "df_quality_on_fail":    cfg.get("DF_QUALITY_ON_FAIL") or "warn",
        "custom_schema":         cfg.get("CUSTOM_SCHEMA"),
    }

    # ── Destination (where the loaded data gets WRITTEN to) — see
    # backend/destinations/. Pipeline-level, not per-source (a
    # multi-source pipeline still loads into ONE table/destination), so
    # every source's payload gets the same three fields. Defaults to
    # postgres when not set, matching every /ingest_* endpoint's default —
    # a DAG generated before this feature existed just keeps working.
    destination_payload_fields = {
        "destination_type":          cfg.get("DESTINATION_TYPE") or "postgres",
        "destination_connection_id": cfg.get("DESTINATION_CONNECTION_ID"),
        "destination_config":        cfg.get("DESTINATION_CONFIG"),
    }

    label = source_label or PIPELINE_ID
    print(f"\n{'='*60}\nProcessing: {label} ({connector_type})\n{'='*60}")

    processed_dir, failed_dir = _ensure_pipeline_folders(connector_type, source_label)
    endpoint = CONNECTOR_ENDPOINT.get(connector_type)
    if not endpoint:
        raise ValueError(f"[{label}] Invalid CONNECTOR_TYPE: {connector_type}")

    # ── CSV / Excel ───────────────────────────────────────────────────────
    if connector_type in ("csv", "excel"):
        ext_filter = ".csv" if connector_type == "csv" else (".xlsx", ".xls")
        candidate_files = []

        if folder_path:
            container_path = to_container_path(folder_path)
            print(f"Path resolved: {container_path}")
            if not os.path.exists(container_path):
                print(f"Path not found: {container_path} — skipping.")
                _log_skip_metrics(table_name, connector_type, container_path, "Path not found")
                return "SKIPPED"
            if os.path.isfile(container_path):
                candidate_files = [container_path]
            elif os.path.isdir(container_path):
                files_in_dir = [
                    f for f in os.listdir(container_path)
                    if f.lower().endswith(ext_filter)
                ]
                if not files_in_dir:
                    print("No matching files found — skipping.")
                    _log_skip_metrics(table_name, connector_type, container_path, "No matching files found in folder")
                    return "SKIPPED"
                candidate_files = [os.path.join(container_path, f) for f in files_in_dir]
            else:
                raise FileNotFoundError(
                    f"[{label}] Path exists but is neither file nor directory: {container_path}"
                )

        elif file_path:
            container_file = to_container_path(file_path)
            print(f"File resolved: {container_file}")
            if not os.path.exists(container_file):
                print(f"File not found: {container_file} — skipping.")
                _log_skip_metrics(table_name, connector_type, container_file, "File not found")
                return "SKIPPED"
            candidate_files = [container_file]
        else:
            raise ValueError(f"[{label}] CSV/Excel: FOLDER_PATH or FILE_PATH required.")

        any_failed    = False
        any_processed = False
        for container_file in candidate_files:
            file_hash = _get_file_hash(container_file)

            if _hash_already_processed(file_hash, processed_dir):
                print(f"SKIP: {os.path.basename(container_file)} (same content, already in DB)")
                _log_skip_metrics(table_name, connector_type, os.path.basename(container_file), "Already processed (hash match)")
                continue

            print(f"Processing: {os.path.basename(container_file)}")
            if _ingest_file(container_file, endpoint, option, table_name, sync_mode, incremental_column,
                             quality_payload_fields=quality_payload_fields):
                _save_file_record(container_file, file_hash, processed_dir)
                _move_file(container_file, processed_dir)
                any_processed = True
            else:
                print(f"Failed: {os.path.basename(container_file)} — moving to failed/")
                _move_file(container_file, failed_dir)
                any_failed = True

        if any_failed:
            raise Exception(f"[{label}] One or more files failed during ingestion")
        return "SUCCESS" if any_processed else "SKIPPED"

    # ── Google Sheets ─────────────────────────────────────────────────────
    elif connector_type == "google_sheets":
        if not sheet_url:
            raise ValueError(f"[{label}] SHEET_URL required.")
        if _url_already_handled(sheet_url, processed_dir, failed_dir):
            _log_skip_metrics(table_name, connector_type, sheet_url[:50], "URL already processed")
            return "SKIPPED"
        payload = {
            "sheet_url":          sheet_url,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=60)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(sheet_url, processed_dir, prefix="sheet_processed")
        else:
            _save_url_record(sheet_url, failed_dir, prefix="sheet_failed")
            raise Exception(f"[{label}] Google Sheets ingestion failed: {res.text}")
        return "SUCCESS"

    # ── API ───────────────────────────────────────────────────────────────
    elif connector_type == "api":
        if not api_url:
            raise ValueError(f"[{label}] API_URL required.")
        if _url_already_handled(api_url, processed_dir, failed_dir):
            _log_skip_metrics(table_name, connector_type, api_url[:50], "URL already processed")
            return "SKIPPED"

        payload = {
            "url":                api_url,
            **api_config,           # ← body, auth_type, header_name, pagination_type, custom_fields, etc.
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(api_url, processed_dir, prefix="api_processed")
        else:
            _save_url_record(api_url, failed_dir, prefix="api_failed")
            raise Exception(f"[{label}] API ingestion failed: {res.text}")
        return "SUCCESS"
    # elif connector_type == "api":
    #     if not api_url:
    #         raise ValueError(f"[{label}] API_URL required.")
    #     if _url_already_handled(api_url, processed_dir, failed_dir):
    #         return "SKIPPED"
    #     payload = {
    #         "url":                api_url,
    #         "option":             option,
    #         "table_name":         table_name,
    #         "sync_mode":          sync_mode,
    #         "incremental_column": incremental_column,
    #     }
    #     res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=60)
    #     if res.status_code == 200 and res.json().get("status") != "FAILED":
    #         _save_url_record(api_url, processed_dir, prefix="api_processed")
    #     else:
    #         _save_url_record(api_url, failed_dir, prefix="api_failed")
    #         raise Exception(f"[{label}] API ingestion failed: {res.text}")
    #     return "SUCCESS"

    # ── S3 ────────────────────────────────────────────────────────────────
    elif connector_type == "s3":
        if not s3_bucket or not s3_key:
            raise ValueError(f"[{label}] S3_BUCKET and S3_KEY required.")

        import boto3
        s3_client = boto3.client(
            "s3",
            aws_access_key_id     = s3_access_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key = s3_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name           = os.getenv("AWS_REGION", "us-east-1"),
        )

        is_folder = s3_key.endswith("/") or "." not in s3_key.split("/")[-1]

        if is_folder:
            ext      = f".{s3_file_type.lower().strip('.')}"
            response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_key)
            all_keys = [
                obj["Key"]
                for obj in response.get("Contents", [])
                if obj["Key"].lower().endswith(ext)
                and not obj["Key"].endswith("/")
            ]

            if not all_keys:
                print(f"No .{s3_file_type} files in s3://{s3_bucket}/{s3_key} — skipping.")
                _log_skip_metrics(table_name, connector_type, s3_key, "No matching files found")
                return "SKIPPED"

            print(f"Found {len(all_keys)} file(s) in S3 folder")
            any_failed = False

            for s3_file_key in all_keys:
                s3_url    = f"s3://{s3_bucket}/{s3_file_key}"
                file_name = s3_file_key.split("/")[-1]

                if _url_already_handled(s3_url, processed_dir, failed_dir):
                    _log_skip_metrics(table_name, connector_type, file_name, "URL already processed")
                    print(f"SKIP: {file_name} (already processed)")
                    continue

                print(f"Processing: {file_name}")
                payload = {
                    "bucket":             s3_bucket,
                    "key":                s3_file_key,
                    "file_type":          s3_file_type,
                    "access_key":     s3_access_key,  
                    "secret_key":     s3_secret_key,
                    "option":             option,
                    "table_name":         table_name,
                    "sync_mode":          sync_mode,
                    "incremental_column": incremental_column,
                    "pipeline_id": PIPELINE_ID,
                    **quality_payload_fields,
                    **destination_payload_fields,
                }
                res = requests.post(f"{BASE_URL}/ingest_s3", json=payload, timeout=120)

                if res.status_code == 200 and res.json().get("status") != "FAILED":
                    _save_url_record(s3_url, processed_dir, prefix=f"s3_processed_{file_name}")
                    print(f"SUCCESS: {file_name} → processed/")
                else:
                    _save_url_record(s3_url, failed_dir, prefix=f"s3_failed_{file_name}")
                    print(f"FAILED: {file_name} → failed/ | Reason: {res.text[:500]}") 
                    any_failed = True

            if any_failed:
                raise Exception(f"[{label}] One or more S3 files failed during ingestion")
            return "SUCCESS"

        else:
            s3_url = f"s3://{s3_bucket}/{s3_key}"
            if _url_already_handled(s3_url, processed_dir, failed_dir):
                print(f"SKIP: {s3_key} (already processed)")
                _log_skip_metrics(table_name, connector_type, s3_key, "Already processed")
                return "SKIPPED"

            payload = {
                "bucket":             s3_bucket,
                "key":                s3_key,
                "file_type":          s3_file_type,
                "access_key":     s3_access_key,  
                "secret_key":     s3_secret_key,
                "option":             option,
                "table_name":         table_name,
                "sync_mode":          sync_mode,
                "incremental_column": incremental_column,
                "pipeline_id": PIPELINE_ID,
                **quality_payload_fields,
                **destination_payload_fields,
            }
            res = requests.post(f"{BASE_URL}/ingest_s3", json=payload, timeout=120)
            if res.status_code == 200 and res.json().get("status") != "FAILED":
                _save_url_record(s3_url, processed_dir, prefix="s3_processed")
                print(f"SUCCESS: {s3_key} → processed/")
            else:
                _save_url_record(s3_url, failed_dir, prefix="s3_failed")
                print(f"FAILED: {s3_key} → failed/ | Reason: {res.text[:500]}")
                raise Exception(f"[{label}] S3 ingestion failed: {res.text}")
            return "SUCCESS"

    # ── Postgres ──────────────────────────────────────────────────────────
    elif connector_type == "postgres":
        if not pg_query:
            raise ValueError(f"[{label}] PG_QUERY required for postgres connector.")
        payload = {
            "host":               src_pg_host,
            "database":           src_pg_db,
            "user":               src_pg_user,
            "password":           src_pg_password,
            "port":               src_pg_port,
            "query":              pg_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_postgres", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(pg_query, processed_dir, prefix="postgres_processed")
        else:
            _save_url_record(pg_query, failed_dir, prefix="postgres_failed")
            raise Exception(f"[{label}] Postgres ingestion failed: {res.text}")
        return "SUCCESS"

    # ── MySQL ─────────────────────────────────────────────────────────────
    elif connector_type == "mysql":
        if not my_query:
            raise ValueError(f"[{label}] MY_QUERY required for mysql connector.")
        payload = {
            "host":               src_my_host,
            "database":           src_my_db,
            "user":               src_my_user,
            "password":           src_my_password,
            "port":               src_my_port,
            "query":              my_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_mysql", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(my_query, processed_dir, prefix="mysql_processed")
        else:
            _save_url_record(my_query, failed_dir, prefix="mysql_failed")
            raise Exception(f"[{label}] MySQL ingestion failed: {res.text}")
        return "SUCCESS"

    # ── Oracle ────────────────────────────────────────────────────────────
    elif connector_type == "oracle":
        if not ora_query:
            raise ValueError(f"[{label}] ORA_QUERY required for oracle connector.")
        payload = {
            "host":               src_ora_host,
            "database":           src_ora_db,
            "user":               src_ora_user,
            "password":           src_ora_password,
            "port":               src_ora_port,
            "query":              ora_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_oracle", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(ora_query, processed_dir, prefix="oracle_processed")
        else:
            _save_url_record(ora_query, failed_dir, prefix="oracle_failed")
            raise Exception(f"[{label}] Oracle ingestion failed: {res.text}")
        return "SUCCESS"

    # ── MongoDB ───────────────────────────────────────────────────────────
    elif connector_type == "mongodb":
        if not mongo_collection:
            raise ValueError(f"[{label}] MONGO_COLLECTION required for mongodb connector.")
        mongo_dedup_key = f"{src_mongo_host or src_mongo_connection_string}/{src_mongo_db}.{mongo_collection}"
        payload = {
            "host":               src_mongo_host,
            "database":           src_mongo_db,
            "user":               src_mongo_user,
            "password":           src_mongo_password,
            "port":               src_mongo_port,
            "connection_string":  src_mongo_connection_string,
            "collection":         mongo_collection,
            "query":              mongo_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_mongodb", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(mongo_dedup_key, processed_dir, prefix="mongodb_processed")
        else:
            _save_url_record(mongo_dedup_key, failed_dir, prefix="mongodb_failed")
            raise Exception(f"[{label}] MongoDB ingestion failed: {res.text}")
        return "SUCCESS"

    # ── Snowflake ─────────────────────────────────────────────────────────
    elif connector_type == "snowflake":
        if not sf_query:
            raise ValueError(f"[{label}] SF_QUERY required for snowflake connector.")
        payload = {
            "account":            sf_account,
            "user":               sf_user,
            "password":           sf_password,
            "warehouse":          sf_warehouse,
            "database":           sf_database,
            "schema":             sf_schema,
            "role":               sf_role,
            "query":              sf_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_snowflake", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(sf_query, processed_dir, prefix="snowflake_processed")
        else:
            _save_url_record(sf_query, failed_dir, prefix="snowflake_failed")
            raise Exception(f"[{label}] Snowflake ingestion failed: {res.text}")
        return "SUCCESS"

    # ── Salesforce CRM ───────────────────────────────────────────────────
    elif connector_type == "salesforce":
        if not sf_crm_object_name and not sf_crm_soql_query:
            raise ValueError(f"[{label}] SF_CRM_OBJECT_NAME or SF_CRM_SOQL_QUERY required for salesforce connector.")
        sf_crm_dedup_key = sf_crm_soql_query or f"{sf_crm_instance_url or sf_crm_login_url}/{sf_crm_object_name}"
        payload = {
            "access_token":    sf_crm_access_token,
            "instance_url":    sf_crm_instance_url,
            "login_url":       sf_crm_login_url,
            "client_id":       sf_crm_client_id,
            "client_secret":   sf_crm_client_secret,
            "username":        sf_crm_username,
            "password":        sf_crm_password,
            "security_token":  sf_crm_security_token,
            "object_name":     sf_crm_object_name,
            "fields":          sf_crm_fields,
            "soql_query":      sf_crm_soql_query,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_salesforce", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(sf_crm_dedup_key, processed_dir, prefix="salesforce_processed")
        else:
            _save_url_record(sf_crm_dedup_key, failed_dir, prefix="salesforce_failed")
            raise Exception(f"[{label}] Salesforce ingestion failed: {res.text}")
        return "SUCCESS"

    # ── HubSpot ───────────────────────────────────────────────────────────
    elif connector_type == "hubspot":
        if not hs_access_token:
            raise ValueError(f"[{label}] HS_ACCESS_TOKEN required for hubspot connector.")
        hs_dedup_key = f"hubspot/{hs_object_type}"
        payload = {
            "access_token": hs_access_token,
            "object_type":  hs_object_type,
            "properties":   hs_properties,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_hubspot", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(hs_dedup_key, processed_dir, prefix="hubspot_processed")
        else:
            _save_url_record(hs_dedup_key, failed_dir, prefix="hubspot_failed")
            raise Exception(f"[{label}] HubSpot ingestion failed: {res.text}")
        return "SUCCESS"

    # ── Zoho CRM ──────────────────────────────────────────────────────────
    elif connector_type == "zoho":
        if not zoho_module:
            raise ValueError(f"[{label}] ZOHO_MODULE required for zoho connector.")
        zoho_dedup_key = f"{zoho_api_domain}/{zoho_module}"
        payload = {
            "access_token":   zoho_access_token,
            "refresh_token":  zoho_refresh_token,
            "client_id":      zoho_client_id,
            "client_secret":  zoho_client_secret,
            "accounts_url":   zoho_accounts_url,
            "api_domain":     zoho_api_domain,
            "module":         zoho_module,
            "fields":         zoho_fields,
            "criteria":       zoho_criteria,
            "option":             option,
            "table_name":         table_name,
            "sync_mode":          sync_mode,
            "incremental_column": incremental_column,
            "pipeline_id": PIPELINE_ID,
            **quality_payload_fields,
            **destination_payload_fields,
        }
        res = requests.post(f"{BASE_URL}/ingest_zoho", json=payload, timeout=120)
        if res.status_code == 200 and res.json().get("status") != "FAILED":
            _save_url_record(zoho_dedup_key, processed_dir, prefix="zoho_processed")
        else:
            _save_url_record(zoho_dedup_key, failed_dir, prefix="zoho_failed")
            raise Exception(f"[{label}] Zoho ingestion failed: {res.text}")
        return "SUCCESS"

    else:
        raise ValueError(f"[{label}] Unsupported connector_type: {connector_type}")


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-SOURCE ENTRYPOINT — unchanged behavior, now backed by _process_one_source
# ─────────────────────────────────────────────────────────────────────────────

def run_connector(**context):
    print(f"Pipeline  : {PIPELINE_ID}")
    print(f"Connector : {CONNECTOR_TYPE}")
    print(f"Option    : {OPTION}")

    dag_run_id = _log_run_start()

    try:
        cfg = {
            "CONNECTOR_TYPE":     CONNECTOR_TYPE,
            "OPTION":             OPTION,
            "TABLE_NAME":         TABLE_NAME,
            "SYNC_MODE":          SYNC_MODE,
            "INCREMENTAL_COLUMN": INCREMENTAL_COLUMN,
            "FOLDER_PATH":        FOLDER_PATH,
            "FILE_PATH":          FILE_PATH,
            "SHEET_URL":          SHEET_URL,
            "API_URL":            API_URL,
            "API_CONFIG":         API_CONFIG,
            "S3_BUCKET":          S3_BUCKET,
            "S3_KEY":             S3_KEY,
            "S3_FILE_TYPE":       S3_FILE_TYPE,
            "S3_ACCESS_KEY":      S3_ACCESS_KEY,
            "S3_SECRET_KEY":      S3_SECRET_KEY,
            "SRC_PG_HOST":        SRC_PG_HOST,
            "SRC_PG_DB":          SRC_PG_DB,
            "SRC_PG_USER":        SRC_PG_USER,
            "SRC_PG_PASSWORD":    SRC_PG_PASSWORD,
            "SRC_PG_PORT":        SRC_PG_PORT,
            "PG_QUERY":           PG_QUERY,
            "SRC_MY_HOST":        SRC_MY_HOST,
            "SRC_MY_DB":          SRC_MY_DB,
            "SRC_MY_USER":        SRC_MY_USER,
            "SRC_MY_PASSWORD":    SRC_MY_PASSWORD,
            "SRC_MY_PORT":        SRC_MY_PORT,
            "MY_QUERY":           MY_QUERY,
            "SRC_ORA_HOST":       SRC_ORA_HOST,
            "SRC_ORA_DB":         SRC_ORA_DB,
            "SRC_ORA_USER":       SRC_ORA_USER,
            "SRC_ORA_PASSWORD":   SRC_ORA_PASSWORD,
            "SRC_ORA_PORT":       SRC_ORA_PORT,
            "ORA_QUERY":          ORA_QUERY,
            "SRC_MONGO_HOST":              SRC_MONGO_HOST,
            "SRC_MONGO_DB":                SRC_MONGO_DB,
            "SRC_MONGO_USER":              SRC_MONGO_USER,
            "SRC_MONGO_PASSWORD":          SRC_MONGO_PASSWORD,
            "SRC_MONGO_PORT":              SRC_MONGO_PORT,
            "SRC_MONGO_CONNECTION_STRING": SRC_MONGO_CONNECTION_STRING,
            "MONGO_COLLECTION":            MONGO_COLLECTION,
            "MONGO_QUERY":                 MONGO_QUERY,
            "SF_ACCOUNT":         SF_ACCOUNT,
            "SF_USER":            SF_USER,
            "SF_PASSWORD":        SF_PASSWORD,
            "SF_WAREHOUSE":       SF_WAREHOUSE,
            "SF_DATABASE":        SF_DATABASE,
            "SF_SCHEMA":          SF_SCHEMA,
            "SF_ROLE":            SF_ROLE,
            "SF_QUERY":           SF_QUERY,
            "QUALITY_CONNECTION_ID": QUALITY_CONNECTION_ID,
            "QUALITY_CONFIG":        QUALITY_CONFIG,
            "QUALITY_ON_FAIL":       QUALITY_ON_FAIL,
            "DF_QUALITY_CONFIG":     DF_QUALITY_CONFIG,
            "DF_QUALITY_ON_FAIL":    DF_QUALITY_ON_FAIL,
            # BUGFIX: this key was missing, so _process_one_source()'s
            # cfg.get("CUSTOM_SCHEMA") always returned None here even though
            # CUSTOM_SCHEMA is written into the generated DAG file correctly
            # (see dag_generator.py) — Create Pipeline runs silently ignored
            # the user's custom schema and fell back to auto-detected dtypes.
            "CUSTOM_SCHEMA":         CUSTOM_SCHEMA,
            # Destination (where the loaded data gets WRITTEN to) — see
            # backend/destinations/. Written into the generated DAG file by
            # utils/dag_generator.py; _process_one_source() (shared with
            # multi-source DAGs) reads it the same way either way.
            "DESTINATION_TYPE":            DESTINATION_TYPE,
            "DESTINATION_CONNECTION_ID":   DESTINATION_CONNECTION_ID,
            "DESTINATION_CONFIG":          DESTINATION_CONFIG,
        }

        result_status = _process_one_source(cfg)

        if OPTION == "3" and AFTER_FIRST_RUN in ("1", "2"):
            _update_option_in_dag(AFTER_FIRST_RUN)

        # _log_run_end(dag_run_id, "SUCCESS")
        _log_run_end(dag_run_id, result_status)
        print("Pipeline completed!")
        _send_email("success", dag_run_id=dag_run_id)

    except Exception as e:
        _log_run_end(dag_run_id, "FAILED", str(e))
        _send_email("failed", error=str(e), dag_run_id=dag_run_id)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


def _collect_logs(dag_run_id):
    import glob
    pattern = (
        f"/opt/airflow/logs/dag_id={PIPELINE_ID}"
        f"/run_id=*/task_id=run_connector/attempt=*.log"
    )
    log_files = sorted(glob.glob(pattern))
    if not log_files:
        pattern_old = f"/opt/airflow/logs/{PIPELINE_ID}/run_connector/*.log"
        log_files   = sorted(glob.glob(pattern_old))
    if not log_files:
        print(f"No log files found for pattern: {pattern}")
        return "No log file found.", None
    latest = log_files[-1]
    try:
        with open(latest, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        print(f"Log file read: {latest} ({len(content)} chars)")
        return content, latest
    except Exception as e:
        return f"Could not read log file: {e}", latest


def _save_log_to_db(dag_run_id, status, log_content, log_file_path):
    try:
        conn = _get_db_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO pipeline_dag_logs (
                pipeline_id, dag_run_id, task_id,
                status, log_content, log_file_path
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (PIPELINE_ID, dag_run_id, "run_connector", status, log_content, log_file_path))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Log saved to DB for run: {dag_run_id}")
    except Exception as e:
        print(f"Failed to save log to DB: {e}")


def _log_run_start():
    dag_run_id = f"run__{PIPELINE_ID}__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        conn = _get_db_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO airflow_pipeline_runs (
                dag_id, dag_run_id, pipeline_name,
                connector_type, folder_path, file_path,
                sheet_url, api_url, operation, table_name,
                schedule, status, execution_date, triggered_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            PIPELINE_ID, dag_run_id, PIPELINE_ID,
            CONNECTOR_TYPE, FOLDER_PATH, FILE_PATH,
            SHEET_URL, API_URL, OPTION, TABLE_NAME,
            SCHEDULE, "RUNNING", datetime.now().isoformat(), "scheduler",
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB log: RUNNING — {dag_run_id}")
    except Exception as e:
        print(f"DB log failed (start): {e}")
    return dag_run_id


def _log_run_end(dag_run_id, status, error=""):
    try:
        conn = _get_db_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE airflow_pipeline_runs
            SET status = %s, error_message = %s
            WHERE dag_run_id = %s
        """, (status, error or None, dag_run_id))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB log: {status} — {dag_run_id}")
    except Exception as e:
        print(f"DB log failed (end): {e}")

    log_content, log_file_path = _collect_logs(dag_run_id)
    _save_log_to_db(dag_run_id, status, log_content, log_file_path)