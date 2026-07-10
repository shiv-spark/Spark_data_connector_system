"""
PostgreSQL SQL Executor

Executes read-only SQL queries against PostgreSQL databases.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

try:
    import asyncpg
    import psycopg2
    from psycopg2 import OperationalError
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sql_executors.base import BaseSqlExecutor, QueryResult, QueryError


class PostgresSqlExecutor(BaseSqlExecutor):
    """SQL Executor for PostgreSQL databases."""

    def __init__(self, config: Dict[str, Any]):
        if not ASYNCPG_AVAILABLE:
            raise ImportError(
                "asyncpg not installed. Install: pip install asyncpg"
            )
        super().__init__(config)
        self._pool = None
        self._running_queries: Dict[str, asyncio.Task] = {}

    def get_executor_type(self) -> str:
        return "postgresql"

    def _get_connection_params(self) -> Dict[str, Any]:
        """Extract connection parameters from config."""
        return {
            "host": self.config.get("host"),
            "port": self.config.get("port", 5432),
            "database": self.config.get("database"),
            "user": self.config.get("user"),
            "password": self.config.get("password"),
            "ssl": self.config.get("sslmode") in ["require", "verify-full"],
            "timeout": 30,
        }

    async def _ensure_pool(self) -> None:
        """Create connection pool if not exists."""
        if self._pool is None:
            params = self._get_connection_params()
            self._pool = await asyncpg.create_pool(
                **params,
                min_size=1,
                max_size=2,
            )

    async def test_connection(self) -> bool:
        """Test the PostgreSQL connection."""
        try:
            await self._ensure_pool()
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    async def execute(
        self,
        query: str,
        limit: int = 100,
        timeout_seconds: int = 30
    ) -> QueryResult:
        """
        Execute a read-only SQL query against PostgreSQL.

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

        await self._ensure_pool()

        async def _run_query():
            async with self._pool.acquire() as conn:
                try:
                    await conn.execute(
                        f"SET statement_timeout = '{timeout_seconds}s'"
                    )

                    start_time = time.perf_counter()
                    rows = await conn.fetch(query_with_limit)
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
                    for desc in rows[0].keys():
                        columns.append({"name": desc, "type": "unknown"})

                    result_rows = [[row[col] for col in row.keys()] for row in rows]
                    truncated = len(rows) >= limit

                    return QueryResult(
                        columns=columns,
                        rows=result_rows,
                        row_count=len(rows),
                        truncated=truncated,
                        execution_time_ms=execution_time_ms,
                        query_id=query_id
                    )

                except asyncio.CancelledError:
                    raise QueryError(
                        error_type="cancelled",
                        message="Query was cancelled"
                    )
                except asyncpg.exceptions.QueryCanceledError:
                    raise QueryError(
                        error_type="timeout",
                        message=f"Query timed out after {timeout_seconds} seconds"
                    )
                except asyncpg.exceptions.PostgresSyntaxError as e:
                    raise QueryError(
                        error_type="syntax",
                        message=str(e)
                    )
                except Exception as e:
                    raise QueryError(
                        error_type="execution",
                        message=str(e)
                    )

        task = asyncio.create_task(_run_query())
        self._running_queries[query_id] = task

        try:
            result = await task
            return result
        except Exception as e:
            if isinstance(e, QueryError):
                raise
            raise QueryError(
                error_type="execution",
                message=str(e)
            )
        finally:
            self._running_queries.pop(query_id, None)

    async def cancel(self, query_id: str) -> None:
        """Cancel a running query."""
        task = self._running_queries.get(query_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _close_connection(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def get_schema(self) -> Dict[str, List[str]]:
        """
        Get database schema (tables and columns) for autocomplete.

        Returns:
            Dict mapping table names to column lists
        """
        await self._ensure_pool()

        schema = {}

        async with self._pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

            for row in tables:
                table_name = row["table_name"]
                column_name = row["column_name"]
                if table_name not in schema:
                    schema[table_name] = []
                schema[table_name].append(column_name)

        return schema