
import os
import re
import ast
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
# Where DAG .py files are written inside the backend container.
# Must match the dags_volume mount → /app/dags
DAGS_FOLDER = os.path.normpath(os.getenv("DAGS_FOLDER", "/app/dags"))

# What the USER types in the frontend (Windows path prefix).
# e.g.  D:/DATA_ENG/Spark_data_connector_system/data
WINDOWS_DATA_PATH    = os.getenv("WINDOWS_DATA_PATH",    "").replace("\\", "/")
WINDOWS_DATASET_PATH = os.getenv("WINDOWS_DATASET_PATH", "").replace("\\", "/")

# Where Airflow container sees the same folders.
# Matches docker-compose.yml:  ./data:/opt/airflow/data
CONTAINER_DATA_PATH    = os.getenv("CONTAINER_DATA_PATH",    "/opt/airflow/data")
CONTAINER_DATASET_PATH = os.getenv("CONTAINER_DATASET_PATH", "/opt/airflow/dataset")

VALID_CONNECTORS = {"csv", "excel", "google_sheets", "api", "postgres", "mysql", "oracle", "mongodb", "s3", "snowflake", "salesforce", "hubspot", "zoho"}
VALID_OPTIONS    = {"1", "2", "3"}


def _safe_id(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "pipeline"


def _clean(val):
    if not val or str(val).strip().lower() in ("string", "null", "none", ""):
        return None
    return val


def _fix_path(val):
    """Normalize path — strip quotes, convert backslashes to forward slashes."""
    if val is None:
        return None
    val = val.strip().strip('"').strip("'")
    return val.replace("\\", "/")

# def _validate_query_shape(connector_type: str, query) -> str | None:

#     if not query or not str(query).strip():
#         return f"{connector_type}: query is empty."

#     q = str(query).strip()
#     match = re.match(r'(?is)^select\s+.+\s+from\s+(.+?)\s*;?\s*$', q)
#     if not match:
#         return f"{connector_type}: query does not look like a valid 'SELECT ... FROM <table>' statement: {q!r}"

#     target = match.group(1).strip()

#     if not re.match(r'^("[^"]+"|\'[^\']+\'|[A-Za-z_][\w$]*(\.[A-Za-z_][\w$]*){0,2})$', target):
#         return f"{connector_type}: query's FROM target is not a valid table reference: {target!r}"

#     return None
def _validate_query_shape(connector_type: str, query) -> str | None:
    if not query or not str(query).strip():
        return f"{connector_type}: query is empty."
    return None

def validate_pipeline_config(config: dict) -> list:
    config["folder_path"]     = _clean(config.get("folder_path"))
    config["file_path"]       = _clean(config.get("file_path"))
    config["api_url"]         = _clean(config.get("api_url"))
    config["api_config"]      = config.get("api_config") or {}
    config["sheet_url"]       = _clean(config.get("sheet_url"))
    config["after_first_run"] = _clean(config.get("after_first_run"))

    errors = []
    if not config.get("pipeline_name"):
        errors.append("pipeline_name required.")

    ct = config.get("connector_type", "")
    if ct not in VALID_CONNECTORS:
        errors.append(f"connector_type '{ct}' invalid. Valid: {VALID_CONNECTORS}")

    if ct in ("csv", "excel"):
        if not config.get("folder_path") and not config.get("file_path"):
            errors.append("csv/excel: folder_path or file_path required.")

    if ct == "google_sheets" and not config.get("sheet_url"):
        errors.append("google_sheets: sheet_url required.")

    if ct == "api" and not config.get("api_url"):
        errors.append("api: api_url required.")

    sync_mode = config.get("sync_mode", "full")
    if sync_mode not in ("full", "incremental"):
        errors.append("sync_mode must be 'full' or 'incremental'.")
    if sync_mode == "incremental" and not config.get("incremental_column"):
        errors.append("incremental: incremental_column required — e.g. 'updated_at' or 'id'")

    if ct == "postgres":
        for field in ("src_pg_host", "src_pg_db", "src_pg_user", "src_pg_password"):
            if not config.get(field):
                errors.append(f"postgres: {field} required.")
        query_error = _validate_query_shape("postgres", config.get("pg_query"))
        if query_error:
            errors.append(query_error)

    if ct == "mysql":
        for field in ("src_my_host", "src_my_db", "src_my_user", "src_my_password"):
            if not config.get(field):
                errors.append(f"mysql: {field} required.")
        query_error = _validate_query_shape("mysql", config.get("my_query"))
        if query_error:
            errors.append(query_error)

    if ct == "oracle":
        for field in ("src_ora_host", "src_ora_db", "src_ora_user", "src_ora_password"):
            if not config.get(field):
                errors.append(f"oracle: {field} required.")
        query_error = _validate_query_shape("oracle", config.get("ora_query"))
        if query_error:
            errors.append(query_error)

    if ct == "mongodb":
        if not config.get("src_mongo_connection_string"):
            for field in ("src_mongo_host", "src_mongo_db"):
                if not config.get(field):
                    errors.append(f"mongodb: {field} required.")
        elif not config.get("src_mongo_db"):
            errors.append("mongodb: src_mongo_db required.")
        if not config.get("mongo_collection"):
            errors.append("mongodb: mongo_collection required.")

    if ct == "s3":
        if not config.get("s3_bucket"):
            errors.append("s3: s3_bucket required.")
        if not config.get("s3_key"):
            errors.append("s3: s3_key required.")

    if ct == "snowflake":
        for field in ("sf_account", "sf_user", "sf_password", "sf_warehouse", "sf_database"):
            if not config.get(field):
                errors.append(f"snowflake: {field} required.")
        query_error = _validate_query_shape("snowflake", config.get("sf_query"))
        if query_error:
            errors.append(query_error)

    if ct == "salesforce":
        if not config.get("sf_crm_access_token") and not (
            config.get("sf_crm_client_id") and config.get("sf_crm_client_secret")
            and config.get("sf_crm_username") and config.get("sf_crm_password")
        ):
            errors.append(
                "salesforce: provide sf_crm_access_token (+ sf_crm_instance_url), "
                "or sf_crm_client_id/sf_crm_client_secret/sf_crm_username/sf_crm_password."
            )
        if not config.get("sf_crm_object_name") and not config.get("sf_crm_soql_query"):
            errors.append("salesforce: sf_crm_object_name or sf_crm_soql_query required.")

    if ct == "hubspot":
        if not config.get("hs_access_token"):
            errors.append("hubspot: hs_access_token required.")

    if ct == "zoho":
        if not config.get("zoho_access_token") and not (
            config.get("zoho_refresh_token") and config.get("zoho_client_id") and config.get("zoho_client_secret")
        ):
            errors.append(
                "zoho: provide zoho_access_token, or zoho_refresh_token/zoho_client_id/zoho_client_secret."
            )
        if not config.get("zoho_module"):
            errors.append("zoho: zoho_module required.")

    if config.get("option", "1") not in VALID_OPTIONS:
        errors.append("option '1' (append), '2' (overwrite), or '3' (create new) required.")

    afr = config.get("after_first_run")
    if afr and afr not in ("1", "2"):
        errors.append("after_first_run '1' or '2' required.")
    if config.get("option") == "3" and not afr:
        errors.append("option '3': after_first_run required — '1' or '2'.")

    if not config.get("table_name"):
        errors.append("table_name required.")

    return errors


def _render_template(cfg: dict) -> str:
    pipeline_id     = _safe_id(cfg["pipeline_name"])
    connector_type  = cfg["connector_type"]
    option          = cfg.get("option", "1")
    after_first_run = cfg.get("after_first_run") or None
    table_name      = cfg["table_name"]
    schedule        = cfg.get("schedule", "*/5 * * * *")
    timezone        = cfg.get("timezone") or "Asia/Kolkata"
    folder_path     = _fix_path(cfg.get("folder_path") or None)
    file_path       = _fix_path(cfg.get("file_path") or None)
    sheet_url       = cfg.get("sheet_url") or None
    api_url         = cfg.get("api_url") or None
    api_config      = cfg.get("api_config") or {}
    sync_mode          = cfg.get("sync_mode")          or "full"
    incremental_column = cfg.get("incremental_column") or None

    src_pg_host     = cfg.get("src_pg_host")     or None
    src_pg_db       = cfg.get("src_pg_db")       or None
    src_pg_user     = cfg.get("src_pg_user")     or None
    src_pg_password = cfg.get("src_pg_password") or None
    src_pg_port     = cfg.get("src_pg_port")     or "5432"
    pg_query        = cfg.get("pg_query")        or None

    src_my_host     = cfg.get("src_my_host")     or None
    src_my_db       = cfg.get("src_my_db")       or None
    src_my_user     = cfg.get("src_my_user")     or None
    src_my_password = cfg.get("src_my_password") or None
    src_my_port     = cfg.get("src_my_port")     or "3306"
    my_query        = cfg.get("my_query")        or None

    src_ora_host     = cfg.get("src_ora_host")     or None
    src_ora_db       = cfg.get("src_ora_db")       or None
    src_ora_user     = cfg.get("src_ora_user")     or None
    src_ora_password = cfg.get("src_ora_password") or None
    src_ora_port     = cfg.get("src_ora_port")     or "1521"
    ora_query        = cfg.get("ora_query")        or None

    src_mongo_host              = cfg.get("src_mongo_host")              or None
    src_mongo_db                = cfg.get("src_mongo_db")                or None
    src_mongo_user               = cfg.get("src_mongo_user")             or None
    src_mongo_password           = cfg.get("src_mongo_password")         or None
    src_mongo_port               = cfg.get("src_mongo_port")             or "27017"
    src_mongo_connection_string  = cfg.get("src_mongo_connection_string") or None
    mongo_collection             = cfg.get("mongo_collection")            or None
    mongo_query                  = cfg.get("mongo_query")                 or None

    s3_bucket    = cfg.get("s3_bucket")    or None
    s3_key       = cfg.get("s3_key")       or None
    s3_file_type = cfg.get("s3_file_type") or "csv"
    s3_access_key  = cfg.get("s3_access_key") or None
    s3_secret_key  = cfg.get("s3_secret_key") or None

    sf_account   = cfg.get("sf_account")   or None
    sf_user      = cfg.get("sf_user")      or None
    sf_password  = cfg.get("sf_password")  or None
    sf_warehouse = cfg.get("sf_warehouse") or None
    sf_database  = cfg.get("sf_database")  or None
    sf_schema    = cfg.get("sf_schema")    or "PUBLIC"
    sf_role      = cfg.get("sf_role")      or None
    sf_query     = cfg.get("sf_query")     or None

    sf_crm_access_token   = cfg.get("sf_crm_access_token")   or None
    sf_crm_instance_url   = cfg.get("sf_crm_instance_url")   or None
    sf_crm_login_url      = cfg.get("sf_crm_login_url")      or "https://login.salesforce.com"
    sf_crm_client_id      = cfg.get("sf_crm_client_id")      or None
    sf_crm_client_secret  = cfg.get("sf_crm_client_secret")  or None
    sf_crm_username       = cfg.get("sf_crm_username")       or None
    sf_crm_password       = cfg.get("sf_crm_password")       or None
    sf_crm_security_token = cfg.get("sf_crm_security_token") or None
    sf_crm_object_name    = cfg.get("sf_crm_object_name")    or None
    sf_crm_fields         = cfg.get("sf_crm_fields")         or None
    sf_crm_soql_query     = cfg.get("sf_crm_soql_query")     or None

    hs_access_token = cfg.get("hs_access_token") or None
    hs_object_type  = cfg.get("hs_object_type")  or "contacts"
    hs_properties   = cfg.get("hs_properties")   or None

    zoho_access_token  = cfg.get("zoho_access_token")  or None
    zoho_refresh_token = cfg.get("zoho_refresh_token") or None
    zoho_client_id     = cfg.get("zoho_client_id")     or None
    zoho_client_secret = cfg.get("zoho_client_secret") or None
    zoho_accounts_url  = cfg.get("zoho_accounts_url")  or "https://accounts.zoho.com"
    zoho_api_domain    = cfg.get("zoho_api_domain")    or "https://www.zohoapis.com"
    zoho_module        = cfg.get("zoho_module")        or None
    zoho_fields        = cfg.get("zoho_fields")        or None
    zoho_criteria      = cfg.get("zoho_criteria")       or None

    quality_connection_id = cfg.get("quality_connection_id") or None
    quality_config         = cfg.get("quality_config") or None
    quality_on_fail        = cfg.get("quality_on_fail") or "warn"
    df_quality_config      = cfg.get("df_quality_config") or None
    df_quality_on_fail     = cfg.get("df_quality_on_fail") or "warn"
    # User-defined schema override — {"column": "integer|float|boolean|date|timestamp|text|json"}.
    # When set, columns listed here get their SQL type/coercion enforced instead
    # of the auto-detected dtype. See utils/schema_applier.py.
    custom_schema           = cfg.get("custom_schema") or None

    def q(val):
        if val is None:
            return "None"
        safe = str(val).replace("\\", "/").replace('"', '\\"')
        return f'"{safe}"'

    header_lines = [
        "from airflow import DAG",
        "from airflow.operators.python import PythonOperator",
        "import pendulum",
        "import os, json, requests, shutil",
        "",
        f"# AUTO-GENERATED — pipeline: {pipeline_id}",
        f"# Do not manually edit. Use /create_pipeline endpoint to regenerate.",
        "",
        f'PIPELINE_ID     = "pipeline_{pipeline_id}"',
        f'CONNECTOR_TYPE  = "{connector_type}"',
        f"FOLDER_PATH     = {q(folder_path)}",
        f"FILE_PATH       = {q(file_path)}",
        f"SHEET_URL       = {q(sheet_url)}",
        f"API_URL         = {q(api_url)}",
        f"API_CONFIG      = {api_config!r}",
        f'SYNC_MODE          = "{sync_mode}"',
        f"INCREMENTAL_COLUMN = {q(incremental_column)}",
        f"SRC_PG_HOST     = {q(src_pg_host)}",
        f"SRC_PG_DB       = {q(src_pg_db)}",
        f"SRC_PG_USER     = {q(src_pg_user)}",
        f"SRC_PG_PASSWORD = {q(src_pg_password)}",
        f'SRC_PG_PORT     = "{src_pg_port}"',
        f"PG_QUERY        = {q(pg_query)}",
        f"SRC_MY_HOST     = {q(src_my_host)}",
        f"SRC_MY_DB       = {q(src_my_db)}",
        f"SRC_MY_USER     = {q(src_my_user)}",
        f"SRC_MY_PASSWORD = {q(src_my_password)}",
        f'SRC_MY_PORT     = "{src_my_port}"',
        f"MY_QUERY        = {q(my_query)}",
        f"SRC_ORA_HOST     = {q(src_ora_host)}",
        f"SRC_ORA_DB       = {q(src_ora_db)}",
        f"SRC_ORA_USER     = {q(src_ora_user)}",
        f"SRC_ORA_PASSWORD = {q(src_ora_password)}",
        f'SRC_ORA_PORT     = "{src_ora_port}"',
        f"ORA_QUERY        = {q(ora_query)}",
        f"SRC_MONGO_HOST              = {q(src_mongo_host)}",
        f"SRC_MONGO_DB                = {q(src_mongo_db)}",
        f"SRC_MONGO_USER              = {q(src_mongo_user)}",
        f"SRC_MONGO_PASSWORD          = {q(src_mongo_password)}",
        f'SRC_MONGO_PORT              = "{src_mongo_port}"',
        f"SRC_MONGO_CONNECTION_STRING = {q(src_mongo_connection_string)}",
        f"MONGO_COLLECTION            = {q(mongo_collection)}",
        f"MONGO_QUERY                 = {q(mongo_query)}",
        f"S3_BUCKET       = {q(s3_bucket)}",
        f"S3_KEY          = {q(s3_key)}",
        f'S3_FILE_TYPE    = "{s3_file_type}"',
        f"S3_ACCESS_KEY   = {q(s3_access_key)}",
        f"S3_SECRET_KEY   = {q(s3_secret_key)}",
        f"SF_ACCOUNT      = {q(sf_account)}",
        f"SF_USER         = {q(sf_user)}",
        f"SF_PASSWORD     = {q(sf_password)}",
        f"SF_WAREHOUSE    = {q(sf_warehouse)}",
        f"SF_DATABASE     = {q(sf_database)}",
        f'SF_SCHEMA       = "{sf_schema}"',
        f"SF_ROLE         = {q(sf_role)}",
        f"SF_QUERY        = {q(sf_query)}",
        f"SF_CRM_ACCESS_TOKEN   = {q(sf_crm_access_token)}",
        f"SF_CRM_INSTANCE_URL   = {q(sf_crm_instance_url)}",
        f'SF_CRM_LOGIN_URL      = "{sf_crm_login_url}"',
        f"SF_CRM_CLIENT_ID      = {q(sf_crm_client_id)}",
        f"SF_CRM_CLIENT_SECRET  = {q(sf_crm_client_secret)}",
        f"SF_CRM_USERNAME       = {q(sf_crm_username)}",
        f"SF_CRM_PASSWORD       = {q(sf_crm_password)}",
        f"SF_CRM_SECURITY_TOKEN = {q(sf_crm_security_token)}",
        f"SF_CRM_OBJECT_NAME    = {q(sf_crm_object_name)}",
        f"SF_CRM_FIELDS         = {sf_crm_fields!r}",
        f"SF_CRM_SOQL_QUERY     = {q(sf_crm_soql_query)}",
        f"HS_ACCESS_TOKEN = {q(hs_access_token)}",
        f'HS_OBJECT_TYPE  = "{hs_object_type}"',
        f"HS_PROPERTIES   = {hs_properties!r}",
        f"ZOHO_ACCESS_TOKEN  = {q(zoho_access_token)}",
        f"ZOHO_REFRESH_TOKEN = {q(zoho_refresh_token)}",
        f"ZOHO_CLIENT_ID     = {q(zoho_client_id)}",
        f"ZOHO_CLIENT_SECRET = {q(zoho_client_secret)}",
        f'ZOHO_ACCOUNTS_URL  = "{zoho_accounts_url}"',
        f'ZOHO_API_DOMAIN    = "{zoho_api_domain}"',
        f"ZOHO_MODULE        = {q(zoho_module)}",
        f"ZOHO_FIELDS        = {zoho_fields!r}",
        f"ZOHO_CRITERIA      = {q(zoho_criteria)}",
        f'OPTION          = "{option}"',
        f"AFTER_FIRST_RUN = {q(after_first_run)}",
        f'TABLE_NAME      = "{table_name}"',
        f'SCHEDULE        = "{schedule}"',
        f'TIMEZONE        = "{timezone}"',
        "",
        # ── Optional quality gates ──────────────────────────────────────────
        # DF_QUALITY_* runs BEFORE load_to_db() (pre-ingest, in-memory);
        # QUALITY_* runs AFTER, against the just-loaded table.
        # See quality/dataframe_checks.py and quality/router.py respectively.
        f"QUALITY_CONNECTION_ID = {quality_connection_id!r}",
        f"QUALITY_CONFIG        = {quality_config!r}",
        f'QUALITY_ON_FAIL        = "{quality_on_fail}"',
        f"DF_QUALITY_CONFIG      = {df_quality_config!r}",
        f'DF_QUALITY_ON_FAIL     = "{df_quality_on_fail}"',
        "",
        # ── Optional user-defined schema override ────────────────────────────
        f"CUSTOM_SCHEMA          = {custom_schema!r}",
        "",
        # ── Path translation variables injected into every generated DAG ──────
        #
        # BASE_URL     : backend service on the Docker network
        # CONTAINER_PATH / DATASET_BASE_CON : Airflow container paths (for finding files)
        # WINDOWS_PATH / DATASET_BASE_WIN   : what the user typed (Windows or /app/... paths)
        #
        # to_container_path() uses WINDOWS_PATH → CONTAINER_PATH to resolve the file.
        # to_backend_path()   uses CONTAINER_PATH → /app/data   to call the ingest API.
        'BASE_URL              = "http://backend:8000"',
        f'CONTAINER_PATH        = "{CONTAINER_DATA_PATH}"',
        f'DATASET_BASE_CON      = "{CONTAINER_DATASET_PATH}"',
        f'WINDOWS_PATH          = "{WINDOWS_DATA_PATH}"',
        f'DATASET_BASE_WIN      = "{WINDOWS_DATASET_PATH}"',
        f'DATASET_PIPELINE_CON  = "{CONTAINER_DATASET_PATH}/pipeline_{pipeline_id}"',
        f'PIPELINE_CON_ROOT     = "{CONTAINER_DATA_PATH}/pipeline_{pipeline_id}"',
        "",
        "CONNECTOR_ENDPOINT = {",
        '    "csv":           "ingest_csv",',
        '    "excel":         "ingest_excel",',
        '    "google_sheets": "ingest_google_sheet",',
        '    "api":           "ingest_api",',
        '    "postgres":      "ingest_postgres",',
        '    "mysql":         "ingest_mysql",',
        '    "oracle":        "ingest_oracle",',
        '    "mongodb":       "ingest_mongodb",',
        '    "s3":            "ingest_s3",',
        '    "snowflake":     "ingest_snowflake",',
        '    "salesforce":    "ingest_salesforce",',
        '    "hubspot":       "ingest_hubspot",',
        '    "zoho":          "ingest_zoho",',
        "}",
    ]

    static_body = open(
        os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
        encoding="utf-8"
    ).read()

    dag_block = """

with DAG(
    dag_id            = PIPELINE_ID,
    start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
    schedule_interval = SCHEDULE,
    catchup           = False,
    max_active_runs   = 1,
    # tags              = ["connector", CONNECTOR_TYPE],
) as dag:
    PythonOperator(
        task_id         = "run_connector",
        python_callable = run_connector,
    )
"""
    return "\n".join(header_lines) + "\n" + static_body + dag_block


def create_dag_file(config: dict) -> dict:
    errors = validate_pipeline_config(config)
    if errors:
        return {"status": "FAILED", "errors": errors}

    pipeline_id = _safe_id(config["pipeline_name"])
    filename    = f"pipeline_{pipeline_id}.py"
    file_path   = os.path.join(DAGS_FOLDER, filename)

    if os.path.exists(file_path):
        return {
            "status": "FAILED",
            "error":  f"Pipeline '{pipeline_id}' already exists. Delete it first or rename."
        }

    content = _render_template({**config, "pipeline_name": pipeline_id})
    os.makedirs(DAGS_FOLDER, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":    "SUCCESS",
        "dag_id":    f"pipeline_{pipeline_id}",
        "file_path": file_path,
        "message":   "DAG file created. Airflow will pick it up in ~30 sec."
    }


def delete_dag_file(pipeline_name: str) -> dict:
    pipeline_id = _safe_id(pipeline_name)
    file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Pipeline '{pipeline_id}' not found."}
    os.remove(file_path)
    return {"status": "SUCCESS", "message": f"pipeline_{pipeline_id}.py deleted."}



# def list_dag_files() -> list:
#     if not os.path.exists(DAGS_FOLDER):
#         return []
def list_dag_files() -> list:
    if not os.path.exists(DAGS_FOLDER):
        return []

    def read_var(content: str, name: str, default=None):
        # Matches:  NAME   = "value"   or   NAME = None
        # The value can itself contain `\"` (an escaped quote — e.g. a
        # pg_query like SELECT * FROM \"tbl_lineage\"), so the capture
        # group has to stop at the first *unescaped* quote, not the first
        # quote at all — otherwise values with embedded quotes get
        # silently truncated. Mirrors q()'s escaping in _render_template.
        match = re.search(rf'^{name}\s*=\s*"((?:\\.|[^"\\])*)"', content, re.MULTILINE)
        if match:
            return match.group(1).replace('\\"', '"')
        none_match = re.search(rf'^{name}\s*=\s*None\s*$', content, re.MULTILINE)
        if none_match:
            return None
        return default

    def read_dict_var(content: str, name: str, default=None):     # ← NEW
        match = re.search(rf'^{name}\s*=\s*(\{{.*\}})\s*$', content, re.MULTILINE)
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                return default
        return default

    def read_int_var(content: str, name: str, default=None):
        # Matches: NAME = 5   or   NAME = None   (unquoted — see q() in _render_template)
        match = re.search(rf'^{name}\s*=\s*(-?\d+|None)\s*$', content, re.MULTILINE)
        if match:
            return None if match.group(1) == "None" else int(match.group(1))
        return default

    def read_list_var(content: str, name: str, default=None):
        # Matches: NAME = ['a', 'b']  or  NAME = None — for list-valued
        # fields like SF_CRM_FIELDS / HS_PROPERTIES / ZOHO_FIELDS.
        match = re.search(rf'^{name}\s*=\s*(\[.*\])\s*$', content, re.MULTILINE)
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                return default
        return default

    def read_var(content: str, name: str, default=None):
        # Matches:  NAME   = "value"   or   NAME = None
        # See the note on the first read_var above — same escaped-quote fix.
        match = re.search(rf'^{name}\s*=\s*"((?:\\.|[^"\\])*)"', content, re.MULTILINE)
        if match:
            return match.group(1).replace('\\"', '"')
        none_match = re.search(rf'^{name}\s*=\s*None\s*$', content, re.MULTILINE)
        if none_match:
            return None
        return default

    result = []
    for fname in sorted(os.listdir(DAGS_FOLDER)):
        if fname.startswith("pipeline_") and fname.endswith(".py"):
            fpath = os.path.join(DAGS_FOLDER, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                content = ""

            result.append({
                "dag_id":    fname.replace(".py", ""),
                "file_name": fname,
                "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
                "schedule":  read_var(content, "SCHEDULE", "*/5 * * * *"),
                "timezone":  read_var(content, "TIMEZONE", "Asia/Kolkata"),

                # ── Core load config ─────────────────────────────────────────
                "connector_type":  read_var(content, "CONNECTOR_TYPE"),
                "table_name":      read_var(content, "TABLE_NAME"),
                "option":          read_var(content, "OPTION", "1"),
                "after_first_run": read_var(content, "AFTER_FIRST_RUN"),
                "sync_mode":           read_var(content, "SYNC_MODE", "full"),
                "incremental_column":  read_var(content, "INCREMENTAL_COLUMN"),

                # ── CSV / Excel ───────────────────────────────────────────────
                "folder_path": read_var(content, "FOLDER_PATH"),
                "file_path":   read_var(content, "FILE_PATH"),

                # ── Google Sheets / API ──────────────────────────────────────
                "sheet_url": read_var(content, "SHEET_URL"),
                "api_url":   read_var(content, "API_URL"),
                "api_config": read_dict_var(content, "API_CONFIG", {}),

                # ── Postgres ──────────────────────────────────────────────────
                "src_pg_host":     read_var(content, "SRC_PG_HOST"),
                "src_pg_db":       read_var(content, "SRC_PG_DB"),
                "src_pg_user":     read_var(content, "SRC_PG_USER"),
                # NOTE: password intentionally NOT returned — see note below
                "src_pg_port":     read_var(content, "SRC_PG_PORT", "5432"),
                "pg_query":        read_var(content, "PG_QUERY"),

                # ── MySQL ─────────────────────────────────────────────────────
                "src_my_host":     read_var(content, "SRC_MY_HOST"),
                "src_my_db":       read_var(content, "SRC_MY_DB"),
                "src_my_user":     read_var(content, "SRC_MY_USER"),
                "src_my_port":     read_var(content, "SRC_MY_PORT", "3306"),
                "my_query":        read_var(content, "MY_QUERY"),

                # ── Oracle ────────────────────────────────────────────────────
                "src_ora_host":    read_var(content, "SRC_ORA_HOST"),
                "src_ora_db":      read_var(content, "SRC_ORA_DB"),
                "src_ora_user":    read_var(content, "SRC_ORA_USER"),
                "src_ora_port":    read_var(content, "SRC_ORA_PORT", "1521"),
                "ora_query":       read_var(content, "ORA_QUERY"),

                # ── MongoDB ───────────────────────────────────────────────────
                "src_mongo_host":              read_var(content, "SRC_MONGO_HOST"),
                "src_mongo_db":                read_var(content, "SRC_MONGO_DB"),
                "src_mongo_user":              read_var(content, "SRC_MONGO_USER"),
                "src_mongo_port":              read_var(content, "SRC_MONGO_PORT", "27017"),
                "src_mongo_connection_string": read_var(content, "SRC_MONGO_CONNECTION_STRING"),
                "mongo_collection":            read_var(content, "MONGO_COLLECTION"),
                "mongo_query":                 read_var(content, "MONGO_QUERY"),

                # ── S3 ────────────────────────────────────────────────────────
                "s3_bucket":    read_var(content, "S3_BUCKET"),
                "s3_key":       read_var(content, "S3_KEY"),
                "s3_file_type": read_var(content, "S3_FILE_TYPE", "csv"),
                "s3_access_key": read_var(content, "S3_ACCESS_KEY"),

                # ── Snowflake ─────────────────────────────────────────────────
                "sf_account":   read_var(content, "SF_ACCOUNT"),
                "sf_user":      read_var(content, "SF_USER"),
                # NOTE: password intentionally NOT returned — see note below
                "sf_warehouse": read_var(content, "SF_WAREHOUSE"),
                "sf_database":  read_var(content, "SF_DATABASE"),
                "sf_schema":    read_var(content, "SF_SCHEMA", "PUBLIC"),
                "sf_role":      read_var(content, "SF_ROLE"),
                "sf_query":     read_var(content, "SF_QUERY"),

                # ── Salesforce CRM ────────────────────────────────────────────
                "sf_crm_instance_url": read_var(content, "SF_CRM_INSTANCE_URL"),
                "sf_crm_login_url":    read_var(content, "SF_CRM_LOGIN_URL", "https://login.salesforce.com"),
                "sf_crm_client_id":    read_var(content, "SF_CRM_CLIENT_ID"),
                "sf_crm_username":     read_var(content, "SF_CRM_USERNAME"),
                "sf_crm_object_name":  read_var(content, "SF_CRM_OBJECT_NAME"),
                "sf_crm_fields":       read_list_var(content, "SF_CRM_FIELDS"),
                "sf_crm_soql_query":   read_var(content, "SF_CRM_SOQL_QUERY"),

                # ── HubSpot ───────────────────────────────────────────────────
                "hs_object_type": read_var(content, "HS_OBJECT_TYPE", "contacts"),
                "hs_properties":  read_list_var(content, "HS_PROPERTIES"),

                # ── Zoho CRM ──────────────────────────────────────────────────
                "zoho_accounts_url": read_var(content, "ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com"),
                "zoho_api_domain":   read_var(content, "ZOHO_API_DOMAIN", "https://www.zohoapis.com"),
                "zoho_client_id":    read_var(content, "ZOHO_CLIENT_ID"),
                "zoho_module":       read_var(content, "ZOHO_MODULE"),
                "zoho_fields":       read_list_var(content, "ZOHO_FIELDS"),
                "zoho_criteria":     read_var(content, "ZOHO_CRITERIA"),

                # ── Password / secret presence flags ─────────────────────────
                # Frontend shows "(unchanged)" placeholder instead of leaking
                # the real secret back to the browser.
                "has_src_pg_password":       read_var(content, "SRC_PG_PASSWORD") is not None,
                "has_sf_password":           read_var(content, "SF_PASSWORD") is not None,
                "has_s3_secret_key":         read_var(content, "S3_SECRET_KEY") is not None,
                "has_src_my_password":       read_var(content, "SRC_MY_PASSWORD") is not None,
                "has_src_ora_password":      read_var(content, "SRC_ORA_PASSWORD") is not None,
                "has_src_mongo_password":    read_var(content, "SRC_MONGO_PASSWORD") is not None,
                "has_sf_crm_access_token":   read_var(content, "SF_CRM_ACCESS_TOKEN") is not None,
                "has_sf_crm_client_secret":  read_var(content, "SF_CRM_CLIENT_SECRET") is not None,
                "has_sf_crm_password":       read_var(content, "SF_CRM_PASSWORD") is not None,
                "has_sf_crm_security_token": read_var(content, "SF_CRM_SECURITY_TOKEN") is not None,
                "has_hs_access_token":       read_var(content, "HS_ACCESS_TOKEN") is not None,
                "has_zoho_access_token":     read_var(content, "ZOHO_ACCESS_TOKEN") is not None,
                "has_zoho_refresh_token":    read_var(content, "ZOHO_REFRESH_TOKEN") is not None,
                "has_zoho_client_secret":    read_var(content, "ZOHO_CLIENT_SECRET") is not None,

                # ── Quality gates ─────────────────────────────────────────────
                "quality_connection_id": read_int_var(content, "QUALITY_CONNECTION_ID"),
                "quality_config":        read_dict_var(content, "QUALITY_CONFIG"),
                "quality_on_fail":       read_var(content, "QUALITY_ON_FAIL", "warn"),
                "df_quality_config":     read_dict_var(content, "DF_QUALITY_CONFIG"),
                "df_quality_on_fail":    read_var(content, "DF_QUALITY_ON_FAIL", "warn"),

                # ── User-defined schema override ─────────────────────────────
                "custom_schema":         read_dict_var(content, "CUSTOM_SCHEMA"),
            })
    return result
# def list_dag_files() -> list:
#     if not os.path.exists(DAGS_FOLDER):
#         return []

#     def read_var(content: str, name: str, default=None):
#         match = re.search(rf'^{name}\s*=\s*"([^"]*)"', content, re.MULTILINE)
#         return match.group(1) if match else default

#     result = []
#     for fname in sorted(os.listdir(DAGS_FOLDER)):
#         if fname.startswith("pipeline_") and fname.endswith(".py"):
#             fpath = os.path.join(DAGS_FOLDER, fname)
#             try:
#                 with open(fpath, "r", encoding="utf-8") as f:
#                     content = f.read()
#             except OSError:
#                 content = ""
#             result.append({
#                 "dag_id":    fname.replace(".py", ""),
#                 "file_name": fname,
#                 "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
#                 "schedule":  read_var(content, "SCHEDULE", "*/5 * * * *"),
#                 "timezone":  read_var(content, "TIMEZONE", "Asia/Kolkata"),
#             })
#     return result


def get_dag_config(pipeline_name: str) -> dict | None:
    """
    Parse the CURRENT full config out of a live DAG file — same field set and
    same regex readers as list_dag_files(), just for one pipeline instead of
    all of them. Used to snapshot "what this pipeline looked like right
    before this edit" for entity_history, since edit_dag_file() only ever
    receives a partial `updates` dict and never sees the pre-edit whole.

    NOTE: like list_dag_files(), this intentionally does NOT return password
    fields (SRC_PG_PASSWORD, SF_PASSWORD, S3_SECRET_KEY, etc.) — only
    presence flags. A restore based on this config alone would blank out
    credentials. That's why pipeline history snapshots also carry the raw
    file text (see get_dag_raw_content) and restore rewrites the file
    verbatim instead of regenerating it from this config.
    """
    pipeline_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def read_var(name, default=None):
        # Value may contain an escaped quote (e.g. pg_query built from
        # "Pick a table": SELECT * FROM \"tbl_lineage\") — stop the capture
        # at the first *unescaped* quote, then unescape \" back to " so the
        # UI (and parseTableFromSimpleSelect) see the real query, not a
        # truncated one.
        match = re.search(rf'^{name}\s*=\s*"((?:\\.|[^"\\])*)"', content, re.MULTILINE)
        if match:
            return match.group(1).replace('\\"', '"')
        if re.search(rf'^{name}\s*=\s*None\s*$', content, re.MULTILINE):
            return None
        return default

    def read_dict_var(name, default=None):
        match = re.search(rf'^{name}\s*=\s*(\{{.*\}})\s*$', content, re.MULTILINE)
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                return default
        return default

    def read_int_var(name, default=None):
        match = re.search(rf'^{name}\s*=\s*(-?\d+|None)\s*$', content, re.MULTILINE)
        if match:
            return None if match.group(1) == "None" else int(match.group(1))
        return default

    def read_list_var(name, default=None):
        match = re.search(rf'^{name}\s*=\s*(\[.*\])\s*$', content, re.MULTILINE)
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):
                return default
        return default

    return {
        "dag_id": f"pipeline_{pipeline_id}",
        "schedule": read_var("SCHEDULE", "*/5 * * * *"),
        "timezone": read_var("TIMEZONE", "Asia/Kolkata"),
        "connector_type": read_var("CONNECTOR_TYPE"),
        "table_name": read_var("TABLE_NAME"),
        "option": read_var("OPTION", "1"),
        "after_first_run": read_var("AFTER_FIRST_RUN"),
        "sync_mode": read_var("SYNC_MODE", "full"),
        "incremental_column": read_var("INCREMENTAL_COLUMN"),
        "folder_path": read_var("FOLDER_PATH"),
        "file_path": read_var("FILE_PATH"),
        "sheet_url": read_var("SHEET_URL"),
        "api_url": read_var("API_URL"),
        "api_config": read_dict_var("API_CONFIG", {}),
        "src_pg_host": read_var("SRC_PG_HOST"),
        "src_pg_db": read_var("SRC_PG_DB"),
        "src_pg_user": read_var("SRC_PG_USER"),
        "src_pg_port": read_var("SRC_PG_PORT", "5432"),
        "pg_query": read_var("PG_QUERY"),
        "src_my_host": read_var("SRC_MY_HOST"),
        "src_my_db": read_var("SRC_MY_DB"),
        "src_my_user": read_var("SRC_MY_USER"),
        "src_my_port": read_var("SRC_MY_PORT", "3306"),
        "my_query": read_var("MY_QUERY"),
        "src_ora_host": read_var("SRC_ORA_HOST"),
        "src_ora_db": read_var("SRC_ORA_DB"),
        "src_ora_user": read_var("SRC_ORA_USER"),
        "src_ora_port": read_var("SRC_ORA_PORT", "1521"),
        "ora_query": read_var("ORA_QUERY"),
        "src_mongo_host": read_var("SRC_MONGO_HOST"),
        "src_mongo_db": read_var("SRC_MONGO_DB"),
        "src_mongo_user": read_var("SRC_MONGO_USER"),
        "src_mongo_port": read_var("SRC_MONGO_PORT", "27017"),
        "src_mongo_connection_string": read_var("SRC_MONGO_CONNECTION_STRING"),
        "mongo_collection": read_var("MONGO_COLLECTION"),
        "mongo_query": read_var("MONGO_QUERY"),
        "s3_bucket": read_var("S3_BUCKET"),
        "s3_key": read_var("S3_KEY"),
        "s3_file_type": read_var("S3_FILE_TYPE", "csv"),
        "sf_account": read_var("SF_ACCOUNT"),
        "sf_user": read_var("SF_USER"),
        "sf_warehouse": read_var("SF_WAREHOUSE"),
        "sf_database": read_var("SF_DATABASE"),
        "sf_schema": read_var("SF_SCHEMA", "PUBLIC"),
        "sf_role": read_var("SF_ROLE"),
        "sf_query": read_var("SF_QUERY"),
        "sf_crm_instance_url": read_var("SF_CRM_INSTANCE_URL"),
        "sf_crm_login_url": read_var("SF_CRM_LOGIN_URL", "https://login.salesforce.com"),
        "sf_crm_client_id": read_var("SF_CRM_CLIENT_ID"),
        "sf_crm_username": read_var("SF_CRM_USERNAME"),
        "sf_crm_object_name": read_var("SF_CRM_OBJECT_NAME"),
        "sf_crm_fields": read_list_var("SF_CRM_FIELDS"),
        "sf_crm_soql_query": read_var("SF_CRM_SOQL_QUERY"),
        "hs_object_type": read_var("HS_OBJECT_TYPE", "contacts"),
        "hs_properties": read_list_var("HS_PROPERTIES"),
        "zoho_accounts_url": read_var("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com"),
        "zoho_api_domain": read_var("ZOHO_API_DOMAIN", "https://www.zohoapis.com"),
        "zoho_client_id": read_var("ZOHO_CLIENT_ID"),
        "zoho_module": read_var("ZOHO_MODULE"),
        "zoho_fields": read_list_var("ZOHO_FIELDS"),
        "zoho_criteria": read_var("ZOHO_CRITERIA"),
        "has_src_pg_password": read_var("SRC_PG_PASSWORD") is not None,
        "has_sf_password": read_var("SF_PASSWORD") is not None,
        "has_s3_secret_key": read_var("S3_SECRET_KEY") is not None,
        "has_src_my_password": read_var("SRC_MY_PASSWORD") is not None,
        "has_src_ora_password": read_var("SRC_ORA_PASSWORD") is not None,
        "has_src_mongo_password": read_var("SRC_MONGO_PASSWORD") is not None,
        "has_sf_crm_access_token": read_var("SF_CRM_ACCESS_TOKEN") is not None,
        "has_sf_crm_client_secret": read_var("SF_CRM_CLIENT_SECRET") is not None,
        "has_sf_crm_password": read_var("SF_CRM_PASSWORD") is not None,
        "has_sf_crm_security_token": read_var("SF_CRM_SECURITY_TOKEN") is not None,
        "has_hs_access_token": read_var("HS_ACCESS_TOKEN") is not None,
        "has_zoho_access_token": read_var("ZOHO_ACCESS_TOKEN") is not None,
        "has_zoho_refresh_token": read_var("ZOHO_REFRESH_TOKEN") is not None,
        "has_zoho_client_secret": read_var("ZOHO_CLIENT_SECRET") is not None,
        "quality_connection_id": read_int_var("QUALITY_CONNECTION_ID"),
        "quality_config": read_dict_var("QUALITY_CONFIG"),
        "quality_on_fail": read_var("QUALITY_ON_FAIL", "warn"),
        "df_quality_config": read_dict_var("DF_QUALITY_CONFIG"),
        "df_quality_on_fail": read_var("DF_QUALITY_ON_FAIL", "warn"),
        "custom_schema": read_dict_var("CUSTOM_SCHEMA"),
    }


def get_dag_source_credentials(pipeline_name: str) -> dict | None:
    """
    Like get_dag_config(), but for SERVER-SIDE USE ONLY — this one DOES
    include real password fields (SRC_PG_PASSWORD, SF_PASSWORD). It exists
    so the backend can open a connection to a pipeline's own source (e.g.
    to list its tables for an edit-form dropdown) without ever sending the
    credentials themselves to the browser.

    NEVER return the dict from this function directly in an API response —
    only derived, non-secret data (like a list of table names).
    """
    pipeline_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def read_var(name, default=None):
        # Same escaped-quote fix as get_dag_config's read_var — a saved
        # pg_query/sf_query can contain \" and must not be truncated there.
        match = re.search(rf'^{name}\s*=\s*"((?:\\.|[^"\\])*)"', content, re.MULTILINE)
        if match:
            return match.group(1).replace('\\"', '"')
        if re.search(rf'^{name}\s*=\s*None\s*$', content, re.MULTILINE):
            return None
        return default

    return {
        "connector_type": read_var("CONNECTOR_TYPE"),
        "pg_query": read_var("PG_QUERY"),
        "src_pg_host": read_var("SRC_PG_HOST"),
        "src_pg_db": read_var("SRC_PG_DB"),
        "src_pg_user": read_var("SRC_PG_USER"),
        "src_pg_password": read_var("SRC_PG_PASSWORD"),
        "src_pg_port": read_var("SRC_PG_PORT", "5432"),
        "sf_query": read_var("SF_QUERY"),
        "sf_account": read_var("SF_ACCOUNT"),
        "sf_user": read_var("SF_USER"),
        "sf_password": read_var("SF_PASSWORD"),
        "sf_warehouse": read_var("SF_WAREHOUSE"),
        "sf_database": read_var("SF_DATABASE"),
        "sf_schema": read_var("SF_SCHEMA", "PUBLIC"),
        "sf_role": read_var("SF_ROLE"),
    }


def get_dag_raw_content(pipeline_name: str) -> str | None:
    """Exact current .py text of a pipeline's DAG file, or None if it doesn't exist."""
    pipeline_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def restore_dag_raw_content(pipeline_name: str, raw_content: str) -> dict:
    """
    Write a previously-snapshotted .py file back verbatim. This is the
    pipeline "restore" primitive — deliberately NOT a re-render from JSON
    config, because config snapshots never contain passwords (see
    get_dag_config). Writing the exact old bytes back is the only way to
    bring credentials back too.
    """
    pipeline_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Pipeline 'pipeline_{pipeline_id}' not found."}
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(raw_content)
    return {
        "status": "SUCCESS",
        "pipeline": f"pipeline_{pipeline_id}",
        "message": "DAG file restored. Airflow will reload in ~30s.",
    }


def edit_dag_file(pipeline_name: str, updates: dict) -> dict:
    """Update specific variables in an existing DAG file without regenerating it."""
    import re as _re

    pipeline_id = _safe_id(pipeline_name)
    file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")

    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Pipeline 'pipeline_{pipeline_id}' not found."}

    # ── Validate any query-shaped field BEFORE writing anything ──────────
    if "pg_query" in updates and updates["pg_query"] is not None:
        err = _validate_query_shape("postgres", updates["pg_query"])
        if err:
            return {"status": "FAILED", "error": err}
    if "sf_query" in updates and updates["sf_query"] is not None:
        err = _validate_query_shape("snowflake", updates["sf_query"])
        if err:
            return {"status": "FAILED", "error": err}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    changed = []

    if "timezone" in updates and "TIMEZONE" not in content:
        content = _re.sub(
            r'^(SCHEDULE\s*=\s*"[^"]*")$',
            r'\1\nTIMEZONE        = "Asia/Kolkata"',
            content, flags=_re.MULTILINE,
        )
        content = content.replace("from datetime import datetime", "import pendulum")
        content = content.replace(
            "start_date        = datetime(2024, 1, 1)",
            "start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE)"
        )

    field_map = {
        "schedule":           "SCHEDULE",
        "timezone":           "TIMEZONE",
        "option":             "OPTION",
        "table_name":         "TABLE_NAME",
        "sync_mode":          "SYNC_MODE",
        "incremental_column": "INCREMENTAL_COLUMN",
        "folder_path":        "FOLDER_PATH",
        "file_path":          "FILE_PATH",
        "sheet_url":          "SHEET_URL",
        "api_url":            "API_URL",
        "after_first_run":    "AFTER_FIRST_RUN",
        "src_pg_host":        "SRC_PG_HOST",
        "src_pg_db":          "SRC_PG_DB",
        "src_pg_user":        "SRC_PG_USER",
        "src_pg_password":    "SRC_PG_PASSWORD",
        "src_pg_port":        "SRC_PG_PORT",
        "pg_query":           "PG_QUERY",
        "src_my_host":        "SRC_MY_HOST",
        "src_my_db":          "SRC_MY_DB",
        "src_my_user":        "SRC_MY_USER",
        "src_my_password":    "SRC_MY_PASSWORD",
        "src_my_port":        "SRC_MY_PORT",
        "my_query":           "MY_QUERY",
        "src_ora_host":        "SRC_ORA_HOST",
        "src_ora_db":          "SRC_ORA_DB",
        "src_ora_user":        "SRC_ORA_USER",
        "src_ora_password":    "SRC_ORA_PASSWORD",
        "src_ora_port":        "SRC_ORA_PORT",
        "ora_query":           "ORA_QUERY",
        "src_mongo_host":              "SRC_MONGO_HOST",
        "src_mongo_db":                "SRC_MONGO_DB",
        "src_mongo_user":              "SRC_MONGO_USER",
        "src_mongo_password":          "SRC_MONGO_PASSWORD",
        "src_mongo_port":              "SRC_MONGO_PORT",
        "src_mongo_connection_string": "SRC_MONGO_CONNECTION_STRING",
        "mongo_collection":            "MONGO_COLLECTION",
        "mongo_query":                 "MONGO_QUERY",
        "s3_bucket":          "S3_BUCKET",
        "s3_key":             "S3_KEY",
        "s3_file_type":       "S3_FILE_TYPE",
        "s3_access_key":      "S3_ACCESS_KEY",
        "s3_secret_key":      "S3_SECRET_KEY",
        "sf_account":         "SF_ACCOUNT",
        "sf_user":            "SF_USER",
        "sf_password":        "SF_PASSWORD",
        "sf_warehouse":       "SF_WAREHOUSE",
        "sf_database":        "SF_DATABASE",
        "sf_schema":          "SF_SCHEMA",
        "sf_role":            "SF_ROLE",
        "sf_query":           "SF_QUERY",
        "sf_crm_access_token":    "SF_CRM_ACCESS_TOKEN",
        "sf_crm_instance_url":    "SF_CRM_INSTANCE_URL",
        "sf_crm_login_url":       "SF_CRM_LOGIN_URL",
        "sf_crm_client_id":       "SF_CRM_CLIENT_ID",
        "sf_crm_client_secret":   "SF_CRM_CLIENT_SECRET",
        "sf_crm_username":        "SF_CRM_USERNAME",
        "sf_crm_password":        "SF_CRM_PASSWORD",
        "sf_crm_security_token":  "SF_CRM_SECURITY_TOKEN",
        "sf_crm_object_name":    "SF_CRM_OBJECT_NAME",
        "sf_crm_soql_query":     "SF_CRM_SOQL_QUERY",
        "hs_access_token":    "HS_ACCESS_TOKEN",
        "hs_object_type":     "HS_OBJECT_TYPE",
        "zoho_access_token":  "ZOHO_ACCESS_TOKEN",
        "zoho_refresh_token": "ZOHO_REFRESH_TOKEN",
        "zoho_client_id":     "ZOHO_CLIENT_ID",
        "zoho_client_secret": "ZOHO_CLIENT_SECRET",
        "zoho_accounts_url":  "ZOHO_ACCOUNTS_URL",
        "zoho_api_domain":    "ZOHO_API_DOMAIN",
        "zoho_module":        "ZOHO_MODULE",
        "zoho_criteria":      "ZOHO_CRITERIA",
        "quality_on_fail":    "QUALITY_ON_FAIL",
        "df_quality_on_fail": "DF_QUALITY_ON_FAIL",
    }
    if "api_config" in updates:
        new_cfg = updates["api_config"] or {}
        pattern     = r'^(API_CONFIG\s*=\s*).*$'
        new_content = _re.sub(pattern, lambda m: f"{m.group(1)}{new_cfg!r}", content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append("API_CONFIG → updated")
            content = new_content

    if "quality_config" in updates:
        new_cfg = updates["quality_config"] or None
        pattern     = r'^(QUALITY_CONFIG\s*=\s*).*$'
        new_content = _re.sub(pattern, lambda m: f"{m.group(1)}{new_cfg!r}", content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append("QUALITY_CONFIG → updated")
            content = new_content

    if "df_quality_config" in updates:
        new_cfg = updates["df_quality_config"] or None
        pattern     = r'^(DF_QUALITY_CONFIG\s*=\s*).*$'
        new_content = _re.sub(pattern, lambda m: f"{m.group(1)}{new_cfg!r}", content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append("DF_QUALITY_CONFIG → updated")
            content = new_content

    # BUGFIX: this block didn't exist — custom_schema had no entry in
    # field_map (it's a dict, not a string) and no dict-write block like
    # quality_config/df_quality_config above, so editing a pipeline could
    # never change (or clear) CUSTOM_SCHEMA in the generated DAG file; the
    # schema set at creation time — or None, if never set — stuck forever.
    if "custom_schema" in updates:
        new_cfg = updates["custom_schema"] or None
        pattern     = r'^(CUSTOM_SCHEMA\s*=\s*).*$'
        new_content = _re.sub(pattern, lambda m: f"{m.group(1)}{new_cfg!r}", content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append("CUSTOM_SCHEMA → updated")
            content = new_content

    # ── List-valued fields (Python list, not a quoted string) — same repr()
    # pattern as api_config/quality_config above, so `['a','b']` gets written
    # as a real list literal instead of the stringified `"['a', 'b']"` the
    # generic string branch below would produce. ──
    for list_field, var_name in (
        ("sf_crm_fields", "SF_CRM_FIELDS"),
        ("hs_properties", "HS_PROPERTIES"),
        ("zoho_fields", "ZOHO_FIELDS"),
    ):
        if list_field in updates:
            new_val = updates[list_field] or None
            pattern     = rf'^({var_name}\s*=\s*).*$'
            new_content = _re.sub(pattern, lambda m, v=new_val: f"{m.group(1)}{v!r}", content, flags=_re.MULTILINE)
            if new_content != content:
                changed.append(f"{var_name} → updated")
                content = new_content

    if "quality_connection_id" in updates:
        new_id = updates["quality_connection_id"]
        new_id = int(new_id) if new_id not in (None, "") else None
        pattern     = r'^(QUALITY_CONNECTION_ID\s*=\s*).*$'
        new_content = _re.sub(pattern, lambda m: f"{m.group(1)}{new_id!r}", content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append("QUALITY_CONNECTION_ID → updated")
            content = new_content

    for field, new_val in updates.items():
        var = field_map.get(field)
        if not var:
            continue
        if new_val is None or str(new_val).strip() == "":
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>None'
        else:
            safe_val    = str(new_val).replace("\\", "/").replace('"', '\\"')
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>"{safe_val}"'

        new_content = _re.sub(pattern, replacement, content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append(f"{var} → {new_val!r}")
            content = new_content

    if not changed:
        return {
            "status":   "NO_CHANGE",
            "message":  "No matching variables found or values already same.",
            "pipeline": f"pipeline_{pipeline_id}",
        }

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":   "SUCCESS",
        "pipeline": f"pipeline_{pipeline_id}",
        "changed":  changed,
        "message":  f"{len(changed)} variable(s) updated. Airflow will reload in ~30s.",
    }