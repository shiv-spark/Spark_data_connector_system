"""
Base SQL Executor Abstract Class

Defines the interface for all SQL executors (PostgreSQL, Snowflake, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class QueryResult:
    columns: List[Dict[str, str]]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    execution_time_ms: int
    query_id: str
    is_write: bool = False  # True for INSERT/UPDATE/DELETE/MERGE — row_count then
                             # means "rows affected", not "rows returned" (there's
                             # no result set to show for these).


class QueryError(Exception):
    def __init__(
        self,
        error_type: str,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.line = line
        self.column = column


class BaseSqlExecutor(ABC):
    """Abstract base class for SQL executors."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize executor with connection config from saved_connections.

        Args:
            config: Connection configuration dict from saved_connections.config
        """
        self.config = config
        self._connection = None

    @abstractmethod
    async def execute(
        self,
        query: str,
        limit: int = 100,
        timeout_seconds: int = 30
    ) -> QueryResult:
        """
        Execute a SQL query against the target database.

        Args:
            query: SQL query to execute
            limit: Maximum rows to return (server enforces this)
            timeout_seconds: Query timeout

        Returns:
            QueryResult with columns, rows, and metadata
        """
        pass

    @abstractmethod
    async def cancel(self, query_id: str) -> None:
        """
        Cancel a running query.

        Args:
            query_id: UUID of the query to cancel
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test the connection to the database.

        Returns:
            True if connection is successful
        """
        pass

    @abstractmethod
    def get_executor_type(self) -> str:
        """
        Return the executor type identifier.

        Returns:
            One of: "snowflake", "postgresql"
        """
        pass

    async def close(self) -> None:
        """Close the connection."""
        if self._connection:
            await self._close_connection()

    @abstractmethod
    async def _close_connection(self) -> None:
        """Internal method to close the specific connection."""
        pass

    def _generate_query_id(self) -> str:
        """Generate a unique query ID."""
        return str(uuid.uuid4())

    def _is_read_only_query(self, query: str) -> bool:
        """
        Check if the query is read-only (SELECT or WITH only).

        Args:
            query: SQL query string

        Returns:
            True if query is read-only
        """
        cleaned = self._clean_query(query)

        if cleaned.startswith('SELECT'):
            return True
        if cleaned.startswith('WITH'):
            return True
        if cleaned.startswith('TABLE'):
            return True
        if cleaned.startswith('VALUES'):
            return True
        if cleaned.startswith(('SHOW', 'DESCRIBE', 'DESC ', 'EXPLAIN')):
            return True

        return False

    # ── Write queries (INSERT/UPDATE/DELETE/MERGE) — allowed, but they
    # don't return a result set, so the executor needs to know to ask the
    # DB driver for an "N rows affected" count instead of fetching rows. ──
    _WRITE_PREFIXES = ('INSERT', 'UPDATE', 'DELETE', 'MERGE')

    def _is_write_query(self, query: str) -> bool:
        cleaned = self._clean_query(query)
        return cleaned.startswith(self._WRITE_PREFIXES)

    # ── Schema-changing / irreversible statements — always blocked from the
    # SQL Editor regardless of the read/write setting above. If a person
    # genuinely needs these, that's a job for a migration tool, not an ad
    # hoc query box. ──────────────────────────────────────────────────────
    _BLOCKED_PREFIXES = ('DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE')

    def _is_blocked_query(self, query: str) -> bool:
        cleaned = self._clean_query(query)
        return cleaned.startswith(self._BLOCKED_PREFIXES)

    @staticmethod
    def _clean_query(query: str) -> str:
        """Strip comments and normalize for prefix-matching. Shared by all
        three classifiers above so they always agree on what "the query"
        actually starts with."""
        import re

        cleaned = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        return cleaned.strip().upper()

    def _inject_limit(self, query: str, limit: int) -> str:
        """
        Inject LIMIT clause if not present in the query.

        Args:
            query: Original SQL query
            limit: Limit value to inject

        Returns:
            Query with LIMIT injected
        """
        import re

        cleaned = query.strip()

        has_limit = re.search(r'\bLIMIT\s+\d+', cleaned, re.IGNORECASE)
        has_fetch = re.search(r'\bFETCH\s+(?:FIRST|NEXT)\s+\d+', cleaned, re.IGNORECASE)

        if has_limit or has_fetch:
            return query

        if cleaned.endswith(';'):
            return f"{cleaned[:-1]} LIMIT {limit};"

        return f"{cleaned} LIMIT {limit}"