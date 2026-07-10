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
    Only SELECT/WITH queries are allowed (read-only mode).
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
            query_id=result.query_id
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