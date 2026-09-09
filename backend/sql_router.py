"""
SQL Editor Router

API endpoints for executing SQL queries against saved connections.
"""

import os
import time
import uuid
from typing import Optional, List, Dict, Any
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import psycopg2
from psycopg2 import pool

from sql_executors import get_executor, is_sql_capable, get_supported_types
from sql_executors.base import QueryError as SqlQueryError
from utils import history_store

router = APIRouter(prefix="/sql", tags=["sql"])

DB_POOL = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "app_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres")
)

MAX_ROW_LIMIT = 100
DEFAULT_TIMEOUT = 30

running_queries: Dict[str, dict] = {}
user_query_counts: Dict[int, int] = defaultdict(int)

def get_db_connection():
    """Get database connection from pool."""
    try:
        conn = DB_POOL.getconn()
        yield conn
    finally:
        DB_POOL.putconn(conn)

def get_connection_from_db(connection_id: int) -> Dict[str, Any]:
    """Fetch connection config from saved_connections table."""
    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT config, source_type FROM saved_connections WHERE id = %s",
            (connection_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Connection with id {connection_id} not found"
            )
        return {"config": row[0], "source_type": row[1]}
    finally:
        cur.close()
        DB_POOL.putconn(conn)


class SqlExecuteRequest(BaseModel):
    connection_id: int
    query: str
    limit: int = MAX_ROW_LIMIT
    timeout_seconds: int = DEFAULT_TIMEOUT


class SqlExecuteResponse(BaseModel):
    columns: List[Dict[str, str]]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    execution_time_ms: int
    query_id: str
    is_write: bool = False  # True for INSERT/UPDATE/DELETE/MERGE — row_count
                             # means "rows affected" here, not "rows returned"


class QueryHistoryItem(BaseModel):
    query_id: str
    connection_id: int
    connection_name: Optional[str] = ""
    connection_type: Optional[str] = ""
    query_text: str
    status: str
    row_count: Optional[int]
    executed_at: str
    duration_ms: Optional[int]


def sanitize_error(error: SqlQueryError) -> Dict[str, Any]:
    """Sanitize error message to prevent leaking internal details."""
    message = error.message

    sensitive_patterns = [
        r'password[^\s]*',
        r'secret[^\s]*',
        r'token[^\s]*',
        r'connection string[^\s]*',
    ]

    import re
    for pattern in sensitive_patterns:
        message = re.sub(pattern, '***', message, flags=re.IGNORECASE)

    return {
        "error_type": error.error_type,
        "message": message,
        "line": error.line,
        "column": error.column
    }


@router.post("/execute", response_model=SqlExecuteResponse)
async def execute_sql(
    req: SqlExecuteRequest,
):
    """
    Execute a SQL query against a saved connection.

    Credentials are retrieved from the saved_connections table.
    SELECT/WITH and INSERT/UPDATE/DELETE/MERGE are allowed. Schema-changing
    statements (DROP/TRUNCATE/ALTER/CREATE/GRANT/REVOKE) are always blocked —
    see BaseSqlExecutor._is_blocked_query().
    """
    user_id = 1  # TODO: replace with actual user ID from authentication

    if req.limit > MAX_ROW_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Row limit cannot exceed {MAX_ROW_LIMIT}"
        )

    if user_query_counts.get(user_id, 0) >= 2:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent queries. Please wait for running queries to complete."
        )

    connection_data = get_connection_from_db(req.connection_id)
    config = connection_data["config"]
    source_type = connection_data["source_type"]

    if not is_sql_capable(source_type):
        raise HTTPException(
            status_code=400,
            detail=f"Connection type '{source_type}' does not support SQL queries. "
                   f"Only {', '.join(get_supported_types())} connections are supported."
        )

    query_id = str(uuid.uuid4())
    running_queries[query_id] = {
        "user_id": user_id,
        "connection_id": req.connection_id,
        "status": "running"
    }
    user_query_counts[user_id] += 1

    try:
        executor = get_executor(source_type, config)

        start_time = time.perf_counter()
        result = await executor.execute(
            query=req.query,
            limit=req.limit,
            timeout_seconds=req.timeout_seconds
        )
        end_time = time.perf_counter()
        execution_time_ms = int((end_time - start_time) * 1000)

        conn = DB_POOL.getconn()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO sql_query_history
                (query_id, connection_id, user_id, query_text, status, row_count, duration_ms)
                VALUES (%s, %s, %s, %s, 'success', %s, %s)
            """, (query_id, req.connection_id, user_id, req.query, result.row_count, execution_time_ms))
            conn.commit()
        finally:
            cur.close()
            DB_POOL.putconn(conn)

        return SqlExecuteResponse(
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            execution_time_ms=result.execution_time_ms,
            query_id=result.query_id,
            is_write=result.is_write,
        )

    except SqlQueryError as e:
        error_info = sanitize_error(e)

        conn = DB_POOL.getconn()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO sql_query_history
                (query_id, connection_id, user_id, query_text, status, error_message, duration_ms)
                VALUES (%s, %s, %s, %s, 'error', %s, %s)
            """, (query_id, req.connection_id, user_id, req.query, error_info["message"], 0))
            conn.commit()
        finally:
            cur.close()
            DB_POOL.putconn(conn)

        raise HTTPException(
            status_code=400,
            detail=error_info
        )

    except Exception as e:
        conn = DB_POOL.getconn()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO sql_query_history
                (query_id, connection_id, user_id, query_text, status, error_message, duration_ms)
                VALUES (%s, %s, %s, %s, 'error', %s, %s)
            """, (query_id, req.connection_id, user_id, req.query, str(e), 0))
            conn.commit()
        finally:
            cur.close()
            DB_POOL.putconn(conn)

        raise HTTPException(
            status_code=500,
            detail={"error_type": "execution", "message": str(e)}
        )

    finally:
        running_queries.pop(query_id, None)
        user_query_counts[user_id] = max(0, user_query_counts.get(user_id, 1) - 1)


@router.post("/cancel/{query_id}")
async def cancel_query(
    query_id: str,
):
    """Cancel a running query."""
    user_id = 1  # TODO: replace with actual user ID from authentication

    query_info = running_queries.get(query_id)
    if not query_info:
        raise HTTPException(
            status_code=404,
            detail="Query not found or already completed"
        )

    if query_info["user_id"] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only cancel your own queries"
        )

    query_info["status"] = "cancelled"

    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE sql_query_history
            SET status = 'cancelled'
            WHERE query_id = %s
        """, (query_id,))
        conn.commit()
    finally:
        cur.close()
        DB_POOL.putconn(conn)

    return {"success": True, "message": "Query cancelled"}


@router.get("/history", response_model=List[QueryHistoryItem])
async def get_query_history(
    connection_id: Optional[int] = Query(None),
    limit: int = Query(50, le=100),
):
    """Get query history for the current user."""
    user_id = 1  # TODO: replace with actual user ID from authentication

    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        if connection_id:
            cur.execute("""
                SELECT h.query_id, h.connection_id, c.name as connection_name, c.source_type as connection_type,
                       h.query_text, h.status, h.row_count, h.executed_at, h.duration_ms
                FROM sql_query_history h
                LEFT JOIN saved_connections c ON h.connection_id = c.id
                WHERE h.user_id = %s AND h.connection_id = %s
                ORDER BY h.executed_at DESC
                LIMIT %s
            """, (user_id, connection_id, limit))
        else:
            cur.execute("""
                SELECT h.query_id, h.connection_id, c.name as connection_name, c.source_type as connection_type,
                       h.query_text, h.status, h.row_count, h.executed_at, h.duration_ms
                FROM sql_query_history h
                LEFT JOIN saved_connections c ON h.connection_id = c.id
                WHERE h.user_id = %s
                ORDER BY h.executed_at DESC
                LIMIT %s
            """, (user_id, limit))

        rows = cur.fetchall()
        return [
            QueryHistoryItem(
                query_id=str(row[0]),
                connection_id=row[1],
                connection_name=row[2] if row[2] else "",
                connection_type=row[3] if row[3] else "",
                query_text=row[4],
                status=row[5],
                row_count=row[6],
                executed_at=str(row[7]) if row[7] else "",
                duration_ms=row[8]
            )
            for row in rows
        ]
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.post("/format")
async def format_sql(
    req: dict,
):
    """Format a SQL query (simple formatting)."""
    query = req.get("query", "")

    formatted = query.strip()

    keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "ORDER BY", "GROUP BY",
                "HAVING", "LIMIT", "OFFSET", "JOIN", "LEFT JOIN", "RIGHT JOIN",
                "INNER JOIN", "OUTER JOIN", "ON", "AS", "WITH"]

    for kw in keywords:
        formatted = formatted.replace(kw, f"\n{kw}")

    formatted = "\n".join(line.strip() for line in formatted.split("\n") if line.strip())

    return {"formatted_query": formatted}


@router.get("/schema/{connection_id}")
async def get_connection_schema(
    connection_id: int,
):
    """Get schema information for autocomplete."""
    connection_data = get_connection_from_db(connection_id)
    config = connection_data["config"]
    source_type = connection_data["source_type"]

    if not is_sql_capable(source_type):
        raise HTTPException(
            status_code=400,
            detail=f"Connection type '{source_type}' does not support SQL queries."
        )

    try:
        executor = get_executor(source_type, config)
        schema = await executor.get_schema()
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error_type": "schema", "message": str(e)}
        )


# ─────────────────────────────────────────────────────────────────────────
# Saved queries — CRUD + version history
#
# `sql_saved_queries` (created in init.sql) previously had no endpoints at
# all — no way to save, list, edit, or delete a named query existed
# anywhere in the app. This adds the full CRUD, plus versioning on PUT
# using the same generic entity_history table pipelines/reverse_etl use
# (entity_type="sql_query", entity_id=str(query id)).
# ─────────────────────────────────────────────────────────────────────────

class SavedQueryCreate(BaseModel):
    connection_id: int
    name: str
    query_text: str


class SavedQueryUpdate(BaseModel):
    name: Optional[str] = None
    query_text: Optional[str] = None
    connection_id: Optional[int] = None


class SavedQueryItem(BaseModel):
    id: str
    connection_id: int
    connection_name: Optional[str] = ""
    connection_type: Optional[str] = ""
    name: str
    query_text: str
    created_at: str
    updated_at: str


def _saved_query_row_to_item(row) -> SavedQueryItem:
    return SavedQueryItem(
        id=str(row[0]),
        connection_id=row[1],
        name=row[2],
        query_text=row[3],
        created_at=str(row[4]) if row[4] else "",
        updated_at=str(row[5]) if row[5] else "",
        connection_name=row[6] if len(row) > 6 and row[6] else "",
        connection_type=row[7] if len(row) > 7 and row[7] else "",
    )


@router.post("/saved_queries", response_model=SavedQueryItem)
async def create_saved_query(req: SavedQueryCreate):
    """Save the current editor query under a name, so it can be reloaded/edited later."""
    user_id = 1  # TODO: replace with actual user ID from authentication

    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO sql_saved_queries (connection_id, user_id, name, query_text)
            VALUES (%s, %s, %s, %s)
            RETURNING id, connection_id, name, query_text, created_at, updated_at
            """,
            (req.connection_id, user_id, req.name, req.query_text),
        )
        row = cur.fetchone()
        conn.commit()
        return _saved_query_row_to_item(row)
    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        raise HTTPException(status_code=404, detail=f"Connection {req.connection_id} not found")
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.get("/saved_queries", response_model=List[SavedQueryItem])
async def list_saved_queries(connection_id: Optional[int] = Query(None)):
    """List saved queries for the current user, newest-edited first."""
    user_id = 1  # TODO: replace with actual user ID from authentication

    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        if connection_id:
            cur.execute(
                """
                SELECT q.id, q.connection_id, q.name, q.query_text, q.created_at, q.updated_at,
                       c.name AS connection_name, c.source_type AS connection_type
                FROM sql_saved_queries q
                LEFT JOIN saved_connections c ON q.connection_id = c.id
                WHERE q.user_id = %s AND q.connection_id = %s
                ORDER BY q.updated_at DESC
                """,
                (user_id, connection_id),
            )
        else:
            cur.execute(
                """
                SELECT q.id, q.connection_id, q.name, q.query_text, q.created_at, q.updated_at,
                       c.name AS connection_name, c.source_type AS connection_type
                FROM sql_saved_queries q
                LEFT JOIN saved_connections c ON q.connection_id = c.id
                WHERE q.user_id = %s
                ORDER BY q.updated_at DESC
                """,
                (user_id,),
            )
        return [_saved_query_row_to_item(row) for row in cur.fetchall()]
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.get("/saved_queries/{query_id}", response_model=SavedQueryItem)
async def get_saved_query(query_id: str):
    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT q.id, q.connection_id, q.name, q.query_text, q.created_at, q.updated_at,
                   c.name AS connection_name, c.source_type AS connection_type
            FROM sql_saved_queries q
            LEFT JOIN saved_connections c ON q.connection_id = c.id
            WHERE q.id = %s
            """,
            (query_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Saved query not found")
        return _saved_query_row_to_item(row)
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.put("/saved_queries/{query_id}", response_model=SavedQueryItem)
async def update_saved_query(query_id: str, req: SavedQueryUpdate):
    """Edit a saved query. The version being replaced is snapshotted first,
    so it can be recovered via /saved_queries/{id}/restore/{version_id}."""
    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, connection_id, name, query_text FROM sql_saved_queries WHERE id = %s",
            (query_id,),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Saved query not found")

        if req.name is None and req.query_text is None and req.connection_id is None:
            raise HTTPException(status_code=400, detail="At least one field required for update.")

        # Only a real query_text change is a "version" worth recovering —
        # renaming or repointing the connection alone shouldn't clutter
        # history with entries that have nothing to actually restore.
        if req.query_text is not None and req.query_text != existing[3]:
            history_store.push_history(
                entity_type="sql_query",
                entity_id=str(query_id),
                config={
                    "connection_id": existing[1],
                    "name": existing[2],
                    "query_text": existing[3],
                },
                label="Edited query",
            )

        cur.execute(
            """
            UPDATE sql_saved_queries
            SET name = COALESCE(%s, name),
                query_text = COALESCE(%s, query_text),
                connection_id = COALESCE(%s, connection_id),
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, connection_id, name, query_text, created_at, updated_at
            """,
            (req.name, req.query_text, req.connection_id, query_id),
        )
        row = cur.fetchone()
        conn.commit()
        return _saved_query_row_to_item(row)
    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        raise HTTPException(status_code=404, detail=f"Connection {req.connection_id} not found")
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.delete("/saved_queries/{query_id}")
async def delete_saved_query(query_id: str):
    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM sql_saved_queries WHERE id = %s RETURNING id", (query_id,))
        deleted = cur.fetchone()
        conn.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Saved query not found")
        return {"status": "DELETED", "id": query_id}
    finally:
        cur.close()
        DB_POOL.putconn(conn)


@router.get("/saved_queries/{query_id}/history")
async def get_saved_query_history(query_id: str):
    return {"history": history_store.list_history("sql_query", str(query_id))}


@router.post("/saved_queries/{query_id}/restore/{version_id}", response_model=SavedQueryItem)
async def restore_saved_query_version(query_id: str, version_id: int):
    """Restore = UPDATE name + query_text back to the snapshotted values.
    The restored version and anything newer than it is then dropped from
    history — no redo, same rule as pipelines/reverse-etl/dashboards."""
    version = history_store.get_version("sql_query", str(query_id), version_id)
    if not version:
        raise HTTPException(status_code=404, detail="History version not found.")
    cfg = version["config"]

    conn = DB_POOL.getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE sql_saved_queries
            SET name = %s, query_text = %s, connection_id = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, connection_id, name, query_text, created_at, updated_at
            """,
            (cfg.get("name"), cfg.get("query_text"), cfg.get("connection_id"), query_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Saved query not found")
        conn.commit()
    finally:
        cur.close()
        DB_POOL.putconn(conn)

    history_store.discard_from("sql_query", str(query_id), version_id)
    return _saved_query_row_to_item(row)