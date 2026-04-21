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
    #convert all backslash variants to forward slash
    if not path:
        return path
    return path.replace("\\\\", "/").replace("\\", "/")

def to_windows_path(path):
    n         = _normalize(path)
    n_dataset = _normalize(DATASET_BASE_CON)
    n_user    = _normalize(CONTAINER_PATH)
    # ← guard: only translate back if the Windows base is actually set
    if n_dataset and DATASET_BASE_WIN and n.startswith(n_dataset):
        return n.replace(n_dataset, DATASET_BASE_WIN).replace("/", "\\")
    if n_user and WINDOWS_PATH and n.startswith(n_user):
        return n.replace(n_user, WINDOWS_PATH).replace("/", "\\")
    # no Windows path configured — return as-is (pure container mode)
    return n



def to_container_path(path):
    if not path:
        return path
    n         = _normalize(path)
    n_dataset = _normalize(DATASET_BASE_WIN)
    n_windows = _normalize(WINDOWS_PATH)
    # ← guard: only translate if the Windows base is actually set
    if n_dataset and n.startswith(n_dataset):
        return n.replace(n_dataset, DATASET_BASE_CON)
    if n_windows and n.startswith(n_windows):
        return n.replace(n_windows, CONTAINER_PATH)
    # path is already a container path — return normalized, no translation
    return n



def _ensure_pipeline_folders():
    base = DATASET_PIPELINE_CON if CONNECTOR_TYPE in ("csv", "excel") else PIPELINE_CON_ROOT
    processed = os.path.join(base, "processed")
    failed    = os.path.join(base, "failed")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(failed,    exist_ok=True)
    print(f"Folders ready — processed: {processed} | failed: {failed}")
    return processed, failed


# ─────────────────────────────────────────────
# HASH DEDUPLICATION 
# ─────────────────────────────────────────────

def _get_file_hash(filepath):
    """File MD5 hash — same content = same hash"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_already_processed(file_hash, processed_dir):
    """
    Check if a file with the given hash has already been processed.
    """
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
    """
    check the file hash and save record in processed/ as JSON:
    to detect duplicates in future runs.
    """
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


# ─────────────────────────────────────────────

def _move_file(src, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(src))
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(dest_folder, f"{name}_{ts}{ext}")
    shutil.copy2(src, dest)
    os.remove(src)
    print(f"Moved: {src} -> {dest}")


def _url_already_handled(url, processed_dir, failed_dir):
        # only check processed/ — if it's already successfully processed, then skip
        # failed/ is not checked — to allow retries
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


def _ingest_file(container_file, endpoint):
    windows_file = to_windows_path(container_file)
    payload = {
        "file_path":          windows_file,
        "option":             OPTION,
        "table_name":         TABLE_NAME,
        "sync_mode":          SYNC_MODE,           # ← add
        "incremental_column": INCREMENTAL_COLUMN,  # ← add
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

        emoji = "OK" if status == "success" else "FAILED"
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

        # Pass dag_run_id to the surviving _collect_logs
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

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"Email sent: {status.upper()}")

    except Exception as e:
        # Print full traceback so you can see the real error in Airflow logs
        print(f"Email send failed: {e}")
        print(traceback.format_exc())


def run_connector(**context):
    print(f"Pipeline  : {PIPELINE_ID}")
    print(f"Connector : {CONNECTOR_TYPE}")
    print(f"Option    : {OPTION}")

    # Log run start
    dag_run_id = _log_run_start()

    try:
        processed_dir, failed_dir = _ensure_pipeline_folders()
        endpoint = CONNECTOR_ENDPOINT.get(CONNECTOR_TYPE)
        if not endpoint:
            raise ValueError(f"Invalid CONNECTOR_TYPE: {CONNECTOR_TYPE}")

        if CONNECTOR_TYPE in ("csv", "excel"):
            ext_filter = ".csv" if CONNECTOR_TYPE == "csv" else (".xlsx", ".xls")
            candidate_files = []

            if FOLDER_PATH:
                container_path = to_container_path(FOLDER_PATH)
                print(f"Path resolved: {container_path}")
                if not os.path.exists(container_path):
                    print(f"Path not found: {container_path} — skipping this run.")
                    _log_run_end(dag_run_id, "SKIPPED", "Path not found")
                    return
                if os.path.isfile(container_path):
                    candidate_files = [container_path]
                elif os.path.isdir(container_path):
                    files_in_dir = [f for f in os.listdir(container_path) if f.lower().endswith(ext_filter)]
                    if not files_in_dir:
                        print("No matching files found — skipping.")
                        _log_run_end(dag_run_id, "SKIPPED", "No files found in folder")
                        return
                    candidate_files = [os.path.join(container_path, f) for f in files_in_dir]
                else:
                    raise FileNotFoundError(f"Path exists but is neither file nor directory: {container_path}")

            elif FILE_PATH:
                container_file = to_container_path(FILE_PATH)
                print(f"File resolved: {container_file}")
                if not os.path.exists(container_file):
                    print(f"File not found: {container_file} — skipping.")
                    _log_run_end(dag_run_id, "SKIPPED", "File not found")
                    return
                candidate_files = [container_file]
            else:
                raise ValueError("CSV/Excel: FOLDER_PATH or FILE_PATH required.")

            # ─────────────────────────────────────────────
            #  hash check for duplicate skip
            # ─────────────────────────────────────────────
            any_failed = False
            for container_file in candidate_files:
                file_hash = _get_file_hash(container_file)

                if _hash_already_processed(file_hash, processed_dir):
                    # Same content — keep the file in place (don't move to processed/), but skip ingestion and log it as skipped
                    print(f"SKIP: {os.path.basename(container_file)} (same content, already in DB)")
                    continue

                print(f"Processing: {os.path.basename(container_file)}")
                if _ingest_file(container_file, endpoint):
                    _save_file_record(container_file, file_hash, processed_dir)  # hash JSON save
                    _move_file(container_file, processed_dir)                     # file move
                else:
                    print(f"Failed: {os.path.basename(container_file)} — moving to failed/")
                    _move_file(container_file, failed_dir)
                    any_failed = True
            # ─────────────────────────────────────────────

            if any_failed:
                raise Exception("One or more files failed during ingestion")

        elif CONNECTOR_TYPE == "google_sheets":
            if not SHEET_URL:
                raise ValueError("SHEET_URL required.")
            if _url_already_handled(SHEET_URL, processed_dir, failed_dir):
                _log_run_end(dag_run_id, "SKIPPED", "URL already processed")
                return
            payload = {"sheet_url": SHEET_URL, "option": OPTION, "table_name": TABLE_NAME,
                       "sync_mode": SYNC_MODE, "incremental_column": INCREMENTAL_COLUMN}
            res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=60)
            if res.status_code == 200 and res.json().get("status") != "FAILED":
                _save_url_record(SHEET_URL, processed_dir, prefix="sheet_processed")
            else:
                _save_url_record(SHEET_URL, failed_dir, prefix="sheet_failed")
                raise Exception(f"Google Sheets ingestion failed: {res.text}")

        elif CONNECTOR_TYPE == "api":
            if not API_URL:
                raise ValueError("API_URL required.")
            if _url_already_handled(API_URL, processed_dir, failed_dir):
                _log_run_end(dag_run_id, "SKIPPED", "URL already processed")
                return
            payload = {"url": API_URL, "option": OPTION, "table_name": TABLE_NAME,
                       "sync_mode": SYNC_MODE, "incremental_column": INCREMENTAL_COLUMN}
            res = requests.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=60)
            if res.status_code == 200 and res.json().get("status") != "FAILED":
                _save_url_record(API_URL, processed_dir, prefix="api_processed")
            else:
                _save_url_record(API_URL, failed_dir, prefix="api_failed")
                raise Exception(f"API ingestion failed: {res.text}")
        
        
        elif CONNECTOR_TYPE == "s3":
            if not S3_BUCKET or not S3_KEY:
                raise ValueError("S3_BUCKET and S3_KEY required.")

            import boto3

            s3_client = boto3.client(
                "s3",
                aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name           = os.getenv("AWS_REGION", "us-east-1"),
            )

            # ── Detect Folder or single file ────────────
            is_folder = S3_KEY.endswith("/") or "." not in S3_KEY.split("/")[-1]

            if is_folder:
                # ── Folder mode — like CSV connector  ────────
                ext      = f".{S3_FILE_TYPE.lower().strip('.')}"
                response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_KEY)
                all_keys = [
                    obj["Key"]
                    for obj in response.get("Contents", [])
                    if obj["Key"].lower().endswith(ext)
                    and not obj["Key"].endswith("/")
                ]

                if not all_keys:
                    print(f"No .{S3_FILE_TYPE} files in s3://{S3_BUCKET}/{S3_KEY} — skipping.")
                    _log_run_end(dag_run_id, "SKIPPED", "No files found in S3 folder")
                    return

                print(f"Found {len(all_keys)} file(s) in S3 folder")
                any_failed = False

                for s3_file_key in all_keys:
                    s3_url    = f"s3://{S3_BUCKET}/{s3_file_key}"
                    file_name = s3_file_key.split("/")[-1]

                    # ── Already processed check ───────────────
                    if _url_already_handled(s3_url, processed_dir, failed_dir):
                        print(f"SKIP: {file_name} (already processed)")
                        continue

                    print(f"Processing: {file_name}")
                    payload = {
                        "bucket":     S3_BUCKET,
                        "key":        s3_file_key,
                        "file_type":  S3_FILE_TYPE,
                        "option":     OPTION,
                        "table_name": TABLE_NAME,
                        "sync_mode":          SYNC_MODE,
                        "incremental_column": INCREMENTAL_COLUMN,
                    }
                    res = requests.post(
                        f"{BASE_URL}/ingest_s3",
                        json=payload,
                        timeout=120
                    )

                    if res.status_code == 200 and res.json().get("status") != "FAILED":
                        _save_url_record(
                            s3_url,
                            processed_dir,
                            prefix=f"s3_processed_{file_name}"
                        )
                        print(f"SUCCESS: {file_name} → processed/")
                    else:
                        _save_url_record(
                            s3_url,
                            failed_dir,
                            prefix=f"s3_failed_{file_name}"
                        )
                        print(f"FAILED: {file_name} → failed/")
                        any_failed = True

                if any_failed:
                    raise Exception("One or more S3 files failed during ingestion")

            else:
                # ── Single file mode ──────────────────────────
                s3_url = f"s3://{S3_BUCKET}/{S3_KEY}"

                if _url_already_handled(s3_url, processed_dir, failed_dir):
                    print(f"SKIP: {S3_KEY} (already processed)")
                    _log_run_end(dag_run_id, "SKIPPED", "S3 file already processed")
                    return

                payload = {
                    "bucket":     S3_BUCKET,
                    "key":        S3_KEY,
                    "file_type":  S3_FILE_TYPE,
                    "option":     OPTION,
                    "table_name": TABLE_NAME,
                    "sync_mode":          SYNC_MODE,
                    "incremental_column": INCREMENTAL_COLUMN,
                }
                res = requests.post(
                    f"{BASE_URL}/ingest_s3",
                    json=payload,
                    timeout=120
                )
                if res.status_code == 200 and res.json().get("status") != "FAILED":
                    _save_url_record(s3_url, processed_dir, prefix="s3_processed")
                    print(f"SUCCESS: {S3_KEY} → processed/")
                else:
                    _save_url_record(s3_url, failed_dir, prefix="s3_failed")
                    print(f"FAILED: {S3_KEY} → failed/")
                    raise Exception(f"S3 ingestion failed: {res.text}")
        
        elif CONNECTOR_TYPE == "postgres":
            if not PG_QUERY:
                raise ValueError("PG_QUERY required for postgres connector.")
            
            payload = {
                "host":       SRC_PG_HOST,
                "database":   SRC_PG_DB,
                "user":       SRC_PG_USER,
                "password":   SRC_PG_PASSWORD,
                "port":       SRC_PG_PORT,
                "query":      PG_QUERY,
                "option":     OPTION,
                "table_name": TABLE_NAME,
                "sync_mode":          SYNC_MODE,
                "incremental_column": INCREMENTAL_COLUMN,
            }
            res = requests.post(
                f"{BASE_URL}/ingest_postgres",
                json=payload,
                timeout=120
            )
            if res.status_code == 200 and res.json().get("status") != "FAILED":
                _save_url_record(PG_QUERY, processed_dir, prefix="postgres_processed")
            else:
                _save_url_record(PG_QUERY, failed_dir, prefix="postgres_failed")
                raise Exception(f"Postgres ingestion failed: {res.text}")

        if OPTION == "3" and AFTER_FIRST_RUN in ("1", "2"):
            _update_option_in_dag(AFTER_FIRST_RUN)

        # Log success
        _log_run_end(dag_run_id, "SUCCESS")
        print("Pipeline completed!")
        _send_email("success", dag_run_id=dag_run_id)

    except Exception as e:
        # Log failure
        _log_run_end(dag_run_id, "FAILED", str(e))
        _send_email("failed", error=str(e), dag_run_id=dag_run_id)
        raise   # re-raise so Airflow also marks the task as failed

def _get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


def _collect_logs(dag_run_id):
    """
    Read Airflow log file for this DAG run.
    Returns (log_content, log_file_path).
    """
    import glob

    pattern = (
        f"/opt/airflow/logs/dag_id={PIPELINE_ID}"
        f"/run_id=*/task_id=run_connector/attempt=*.log"
    )
    log_files = sorted(glob.glob(pattern))

    if not log_files:
        # fallback — try older Airflow log path format
        pattern_old = f"/opt/airflow/logs/{PIPELINE_ID}/run_connector/*.log"
        log_files = sorted(glob.glob(pattern_old))

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
    """
    Insert log content into pipeline_dag_logs table.
    """
    try:
        conn = _get_db_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO pipeline_dag_logs (
                pipeline_id, dag_run_id, task_id,
                status, log_content, log_file_path
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            PIPELINE_ID,
            dag_run_id,
            "run_connector",
            status,
            log_content,
            log_file_path,
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Log saved to DB for run: {dag_run_id}")
    except Exception as e:
        print(f"Failed to save log to DB: {e}")


def _log_run_start():
    """
    Insert a RUNNING row when DAG starts.
    Returns dag_run_id string used to update status later.
    """
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
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            PIPELINE_ID,
            dag_run_id,
            PIPELINE_ID,
            CONNECTOR_TYPE,
            FOLDER_PATH,
            FILE_PATH,
            SHEET_URL,
            API_URL,
            OPTION,
            TABLE_NAME,
            SCHEDULE,
            "RUNNING",
            datetime.now().isoformat(),
            "scheduler",
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB log: RUNNING — {dag_run_id}")
    except Exception as e:
        print(f"DB log failed (start): {e}")

    return dag_run_id


def _log_run_end(dag_run_id, status, error=""):
    """
    1. Update airflow_pipeline_runs status
    2. Collect log file
    3. Save log content to pipeline_dag_logs
    """
    # Step 1 — update run status
    try:
        conn = _get_db_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE airflow_pipeline_runs
            SET status = %s,
                error_message = %s
            WHERE dag_run_id = %s
        """, (status, error or None, dag_run_id))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB log: {status} — {dag_run_id}")
    except Exception as e:
        print(f"DB log failed (end): {e}")

    # Step 2+3 — collect logs and save to DB
    log_content, log_file_path = _collect_logs(dag_run_id)
    _save_log_to_db(dag_run_id, status, log_content, log_file_path)


