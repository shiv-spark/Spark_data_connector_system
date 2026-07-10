"""
SQL Executor Registry

Factory for creating SQL executors based on connection type.
"""

from typing import Any, Dict, Optional, Type

from sql_executors.base import BaseSqlExecutor
from sql_executors.postgres import PostgresSqlExecutor
from sql_executors.snowflake import SnowflakeSqlExecutor


EXECUTOR_REGISTRY: Dict[str, Type[BaseSqlExecutor]] = {
    "postgresql": PostgresSqlExecutor,
    "postgres": PostgresSqlExecutor,
    "snowflake": SnowflakeSqlExecutor,
}


def get_executor(
    source_type: str,
    config: Dict[str, Any]
) -> BaseSqlExecutor:
    """
    Create a SQL executor based on source type.

    Args:
        source_type: Connection type (postgresql, snowflake)
        config: Connection configuration from saved_connections

    Returns:
        Instance of appropriate SQL executor

    Raises:
        ValueError: If source type is not supported
    """
    executor_class = EXECUTOR_REGISTRY.get(source_type.lower())

    if not executor_class:
        raise ValueError(
            f"Unsupported source type: {source_type}. "
            f"Supported types: {list(EXECUTOR_REGISTRY.keys())}"
        )

    return executor_class(config)


def is_sql_capable(source_type: str) -> bool:
    """
    Check if a source type supports SQL queries.

    Args:
        source_type: Connection type

    Returns:
        True if source supports SQL queries
    """
    return source_type.lower() in EXECUTOR_REGISTRY


def get_supported_types() -> list:
    """
    Get list of supported SQL-capable source types.

    Returns:
        List of source type strings
    """
    return list(set(EXECUTOR_REGISTRY.keys()))