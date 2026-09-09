"""
MongoDB destination adapter — same adapter interface as the SQL adapters,
adapted for a schemaless document store.

Requires `pymongo`. Config keys match testers/mongodb.py and
reverse_etl/writers/mongodb_writer.py exactly, so an existing MongoDB
saved connection works unchanged as an ingest destination too:
    connection_string (mongodb:// / mongodb+srv://, takes priority)
    OR host, port (default 27017), user, password
    database (required)

Because Mongo has no fixed table schema, several adapter calls that matter
a lot for the SQL engines are deliberately no-ops or trivial here:
- create_table(): Mongo creates a collection implicitly on first insert,
  so this just makes sure the collection exists.
- evolve_schema(): nothing to ALTER — new fields on a document just work.
- check_schema_mismatch(): always reports 100% match (there IS no fixed
  schema to mismatch against) so db_loader's threshold logic is a no-op
  here and every column always gets written.
- alter_existing_columns_to_custom_schema(): no-op — custom_schema still
  COERCES the incoming values (that happens upstream in
  utils/schema_applier.py before this adapter ever sees the data), it
  just doesn't need a DDL step on the Mongo side.
`table_name` is used as the collection name.
"""

try:
    from pymongo import MongoClient

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

import numpy as np
import pandas as pd

MAX_IDENTIFIER_LEN = 120

CANONICAL_TO_NATIVE = {
    "integer": "int", "float": "float", "boolean": "bool",
    "date": "date", "timestamp": "date", "text": "string", "json": "object",
}  # informational only — Mongo has no column DDL to map these to


def validate_identifier(table_name: str):
    if not table_name:
        raise ValueError("table_name (collection name) is required")
    if len(table_name) > MAX_IDENTIFIER_LEN:
        raise ValueError(f"table_name cannot be longer than {MAX_IDENTIFIER_LEN} characters")


def _require_pymongo():
    if not PYMONGO_AVAILABLE:
        raise ImportError("MongoDB destination requires pymongo (pip install pymongo).")


def connect(config: dict):
    _require_pymongo()
    connection_string = config.get("connection_string")
    if connection_string:
        client = MongoClient(connection_string, serverSelectionTimeoutMS=10000)
    else:
        client = MongoClient(
            host=config.get("host"),
            port=int(config.get("port") or 27017),
            username=config.get("user") or None,
            password=config.get("password") or None,
            serverSelectionTimeoutMS=10000,
        )
    database = config.get("database")
    if not database:
        raise ValueError("mongodb destination requires 'database' in config")
    # Stash the target db on the client object so every other function
    # here only needs `conn` (mirrors the SQL adapters' single-connection-object shape).
    client._destination_db_name = database
    return client


def close(conn):
    try:
        conn.close()
    except Exception:
        pass


def _db(conn):
    return conn[conn._destination_db_name]


def dtype_to_native(dtype: str) -> str:
    return "mixed"  # Mongo is schemaless — nothing to map to


def table_exists(conn, table_name: str) -> bool:
    return table_name in _db(conn).list_collection_names()


def check_schema_mismatch(conn, df, table_name: str) -> dict:
    return {"matched": list(df.columns), "missing_in_file": [], "extra_in_file": [], "match_pct": 100.0}


def create_table(conn, df, table_name: str, custom_schema=None):
    db = _db(conn)
    if table_name not in db.list_collection_names():
        db.create_collection(table_name)
        print(f"[mongodb] Collection '{table_name}' created")


def evolve_schema(conn, df, table_name: str, custom_schema=None):
    return []  # documents are schema-flexible — nothing to evolve


def alter_existing_columns_to_custom_schema(conn, table_name: str, custom_schema):
    return [], []  # nothing to ALTER on a document store


def _mongo_value(v):
    """Like destinations.common.sanitize_value, but keeps list/dict as
    native BSON instead of JSON-stringifying them — Mongo can store those
    directly as embedded arrays/documents, which is the more natural fit."""
    if v is None:
        return None
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (list, dict)):
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (np.integer, np.floating)):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    return v


def insert_data(conn, df, table_name: str, batch_size: int = 1000, custom_schema=None):
    db = _db(conn)
    collection = db[table_name]
    cols = list(df.columns)

    docs = [
        {col: _mongo_value(v) for col, v in zip(cols, row)}
        for row in df.itertuples(index=False, name=None)
    ]

    inserted = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        if batch:
            collection.insert_many(batch, ordered=False)
            inserted += len(batch)

    print(f"[mongodb] {inserted} documents inserted into '{table_name}'")


def drop_table(conn, table_name: str):
    _db(conn).drop_collection(table_name)


def get_last_incremental_value(conn, table_name: str, incremental_column: str):
    db = _db(conn)
    try:
        doc = db[table_name].find_one(sort=[(incremental_column, -1)])
        return doc.get(incremental_column) if doc else None
    except Exception as e:
        print(f"[mongodb] Could not fetch last incremental value: {e}")
        return None
