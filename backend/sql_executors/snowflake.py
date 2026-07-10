"""
Snowflake SQL Executor

Executes read-only SQL queries against Snowflake databases.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
import uuid

try:
    import snowflake.connector
    from snowflake.connector import Error as SnowflakeError
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sql_executors.base import BaseSqlExecutor, QueryResult, QueryError


class SnowflakeSqlExecutor(BaseSqlExecutor):
    """SQL Executor for Snowflake databases."""

    def __init__(self, config: Dict[str, Any]):
        if not SNOWFLAKE_AVAILABLE:
            raise ImportError(
                "snowflake-connector-python not installed. "
                "Install: pip install snowflake-connector-python"
            )
        super().__init__(config)
        self._connection = None
        self._running_queries: Dict[str, dict] = {}

    def get_executor_type(self) -> str:
        return "snowflake"

    def _get_connection_params(self) -> Dict[str, Any]:
        """Extract connection parameters from config."""
        params = {
            "account": self.config.get("account"),
            "user": self.config.get("user"),
            "password": self.config.get("password"),
            "warehouse": self.config.get("warehouse"),
            "database": self.config.get("database"),
            "schema": self.config.get("schema", "PUBLIC"),
            "login_timeout": 10,
            "network_timeout": 10,
        }

        if self.config.get("role"):
            params["role"] = self.config["role"]

        return params

    def _connect(self):
        """Create a new Snowflake connection."""
        params = self._get_connection_params()
        return snowflake.connector.connect(**params)

    async def test_connection(self) -> bool:
        """Test the Snowflake connection."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_VERSION()")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True
        except Exception:
            return False

    def _parse_snowflake_type(self, type_code: int) -> str:
        """Convert Snowflake type code to string name."""
        type_map = {
            0: "FIXED",
            1: "REAL",
            2: "TEXT",
            3: "DATE",
            4: "VARIANT",
            5: "TIMESTAMP",
            6: "TIMESTAMP_LTZ",
            7: "TIMESTAMP_TZ",
            8: "TIMESTAMP_NTZ",
            9: "OBJECT",
            10: "ARRAY",
            11: "BINARY",
            12: "BOOLEAN",
            13: "GEOMETRY",
            14: "GEOGRAPHY",
        }
        return type_map.get(type_code, "UNKNOWN")

    async def execute(
        self,
        query: str,
        limit: int = 100,
        timeout_seconds: int = 30
    ) -> QueryResult:
        """
        Execute a read-only SQL query against Snowflake.

        Args:
            query: SQL query to execute
            limit: Maximum rows to return
            timeout_seconds: Query timeout

        Returns:
            QueryResult with query results

        Raises:
            QueryError: If query is not read-only or execution fails
        """
        if not self._is_read_only_query(query):
            raise QueryError(
                error_type="security",
                message="Only SELECT and WITH queries are allowed. "
                        "Write operations (INSERT, UPDATE, DELETE, DDL) are not permitted."
            )

        query_with_limit = self._inject_limit(query, limit)
        query_id = self._generate_query_id()

        def _run_query_sync():
            conn = None
            cursor = None
            try:
                conn = self._connect()

                cursor = conn.cursor()

                cursor.execute(
                    f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {timeout_seconds}"
                )

                start_time = time.perf_counter()
                cursor.execute(query_with_limit)
                rows = cursor.fetchall()
                end_time = time.perf_counter()

                execution_time_ms = int((end_time - start_time) * 1000)

                if not rows:
                    return QueryResult(
                        columns=[],
                        rows=[],
                        row_count=0,
                        truncated=False,
                        execution_time_ms=execution_time_ms,
                        query_id=query_id
                    )

                columns = []
                for desc in cursor.description:
                    columns.append({
                        "name": desc[0],
                        "type": self._parse_snowflake_type(desc[1])
                    })

                result_rows = [list(row) for row in rows]
                truncated = len(rows) >= limit

                return QueryResult(
                    columns=columns,
                    rows=result_rows,
                    row_count=len(rows),
                    truncated=truncated,
                    execution_time_ms=execution_time_ms,
                    query_id=query_id
                )

            except snowflake.connector.errors.ProgrammingError as e:
                raise QueryError(
                    error_type="syntax",
                    message=str(e)
                )
            except snowflake.connector.errors.QueryCancelledError:
                raise QueryError(
                    error_type="cancelled",
                    message="Query was cancelled"
                )
            except snowflake.connector.errors.OperationalError as e:
                if "timeout" in str(e).lower():
                    raise QueryError(
                        error_type="timeout",
                        message=f"Query timed out after {timeout_seconds} seconds"
                    )
                raise QueryError(
                    error_type="execution",
                    message=str(e)
                )
            except Exception as e:
                raise QueryError(
                    error_type="execution",
                    message=str(e)
                )
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_query_sync)
        return result

    async def cancel(self, query_id: str) -> None:
        """Cancel a running query."""
        query_info = self._running_queries.get(query_id)
        if query_info and query_info.get("cursor"):
            try:
                query_info["cursor"].close()
            except Exception:
                pass

    async def _close_connection(self) -> None:
        """Close the connection."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    async def get_schema(self) -> Dict[str, List[str]]:
        """
        Get database schema (tables and columns) for autocomplete.

        Returns:
            Dict mapping table names to column lists
        """
        schema_query = """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_catalog = %s
            ORDER BY table_name, ordinal_position
        """

        def _fetch_schema():
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                schema_query,
                (self.config.get("schema", "PUBLIC"), self.config.get("database"))
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows

        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _fetch_schema)

        schema = {}
        for row in rows:
            table_name = row[0]
            column_name = row[1]
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append(column_name)

        return schema