"""
Text-to-SQL Agent Module

A natural language to SQL conversion agent supporting multiple databases:
- PostgreSQL
- MySQL
- SQLite
- Snowflake
"""

from .agent import Text2SQLAgent, ask
from .postgres_executor import PostgresExecutor
from .postgres_schema_manager import PostgresSchemaManager, get_schema
from .sql_validator import validate_sql, clean_sql
from .metadata_logger import PostgresMetadataLogger
from .connection_manager import (
    DatabaseConnection,
    DatabaseType,
    ConnectionManager,
    get_connection_manager,
)
from .config import POSTGRES_CONFIG, MODEL_NAME, MAX_RETRIES

# Import router (may fail if FastAPI is not available)
try:
    from .router import router
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False

__version__ = "2.0.0"

__all__ = [
    # Main classes
    "Text2SQLAgent",
    "DatabaseConnection",
    "DatabaseType",
    "ConnectionManager",
    "PostgresExecutor",
    "PostgresSchemaManager",
    "PostgresMetadataLogger",
    
    # Functions
    "ask",
    "get_schema",
    "validate_sql",
    "clean_sql",
    "get_connection_manager",
    
    # Configuration
    "POSTGRES_CONFIG",
    "MODEL_NAME",
    "MAX_RETRIES",
]

# Add router to exports if available
if ROUTER_AVAILABLE:
    __all__.append("router")
