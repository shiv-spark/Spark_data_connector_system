"""
Database Connection Manager for Text-to-SQL Agent

Supports multiple database types and dynamic connection switching.
"""

import os
import json
import logging
import sys
import traceback
from typing import Dict, Any, Optional, List
from enum import Enum

# Set up logging to both console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/text2sql_debug.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Optional PostgreSQL support
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    sql = None

# Note: Environment variables should be loaded by the main application (main.py)
# This module relies on those environment variables being set


class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    SNOWFLAKE = "snowflake"
    # Future support
    # SQLSERVER = "sqlserver"
    # ORACLE = "oracle"


def _escape_sql_literal(value: str) -> str:
    """Escape single quotes for safe inclusion in a SQL string literal.

    Used only for Snowflake identifier/config values (schema, database,
    table names) that come from trusted connection config, not raw user input.
    """
    return value.replace("'", "''")


class DatabaseConnection:
    """
    Generic database connection wrapper.
    Supports PostgreSQL, MySQL, SQLite, and Snowflake.
    """

    def __init__(self, connection_id: str, name: str, db_type: DatabaseType, config: Dict[str, Any]):
        self.connection_id = connection_id
        self.name = name
        self.db_type = db_type
        self.config = config
        self._connection = None
        self._cursor = None

    def connect(self):
        """Establish database connection."""
        if self.db_type == DatabaseType.POSTGRESQL:
            return self._connect_postgresql()
        elif self.db_type == DatabaseType.MYSQL:
            return self._connect_mysql()
        elif self.db_type == DatabaseType.SQLITE:
            return self._connect_sqlite()
        elif self.db_type == DatabaseType.SNOWFLAKE:
            return self._connect_snowflake()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def _connect_postgresql(self):
        """Connect to PostgreSQL."""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("PostgreSQL support requires psycopg2. Install: pip install psycopg2-binary")
        self._connection = psycopg2.connect(
            host=self.config.get("host", "localhost"),
            port=self.config.get("port", 5432),
            database=self.config.get("database"),
            user=self.config.get("user"),
            password=self.config.get("password"),
            sslmode=self.config.get("sslmode", "prefer")
        )
        self._cursor = self._connection.cursor()
        return self._connection

    def _connect_mysql(self):
        """Connect to MySQL."""
        try:
            import pymysql
            self._connection = pymysql.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 3306),
                database=self.config.get("database"),
                user=self.config.get("user"),
                password=self.config.get("password"),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self._cursor = self._connection.cursor()
            return self._connection
        except ImportError:
            raise ImportError("MySQL support requires pymysql. Install: pip install pymysql")

    def _connect_sqlite(self):
        """Connect to SQLite."""
        import sqlite3
        self._connection = sqlite3.connect(self.config.get("database_path", ":memory:"))
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()
        return self._connection

    def _connect_snowflake(self):
        """Connect to Snowflake."""
        try:
            import snowflake.connector

            account = self.config.get("account", "")
            if not account:
                raise ValueError("Snowflake connection config is missing 'account'")

            # Warn (but don't fail) if the account identifier looks like it's
            # missing the region/cloud segment, which causes the connector to
            # fall back to the GLOBAL Snowflake domain and can lead to
            # connection/query failures.
            if "." not in account and "-" not in account:
                logger.warning(
                    "Snowflake 'account' value '%s' looks like a short/legacy "
                    "identifier. If you see 'Connecting to GLOBAL Snowflake "
                    "domain' in logs and connections fail, use the full "
                    "account identifier (e.g. 'orgname-accountname' or "
                    "'account.region.cloud').",
                    account
                )

            self._connection = snowflake.connector.connect(
                user=self.config.get("user"),
                password=self.config.get("password"),
                account=account,
                warehouse=self.config.get("warehouse"),
                database=self.config.get("database"),
                schema=self.config.get("schema", "PUBLIC"),
                role=self.config.get("role") or None
            )
            self._cursor = self._connection.cursor()
            return self._connection
        except ImportError:
            raise ImportError("Snowflake support requires snowflake-connector-python")

    def execute(self, query: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """Execute a query and return results."""
        import time

        if not self._connection:
            self.connect()

        start_time = time.time()

        try:
            if self.db_type == DatabaseType.MYSQL:
                # MySQL uses parameterized queries differently
                self._cursor.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    rows = self._cursor.fetchall()
                    columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
                    # Convert dict rows to tuple rows for consistency
                    tuple_rows = []
                    for row in rows:
                        if isinstance(row, dict):
                            tuple_rows.append([row.get(col) for col in columns])
                        else:
                            tuple_rows.append(list(row))
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": tuple_rows,
                        "row_count": len(tuple_rows),
                        "execution_time": round(time.time() - start_time, 2)
                    }
                else:
                    self._connection.commit()
                    return {"success": True, "row_count": self._cursor.rowcount}

            elif self.db_type == DatabaseType.SQLITE:
                self._cursor.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    rows = self._cursor.fetchall()
                    columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": [list(row) for row in rows],
                        "row_count": len(rows),
                        "execution_time": round(time.time() - start_time, 2)
                    }
                else:
                    self._connection.commit()
                    return {"success": True, "row_count": self._cursor.rowcount}

            elif self.db_type == DatabaseType.SNOWFLAKE:
                self._cursor.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    rows = self._cursor.fetchall()
                    columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
                    # Handle both dict and tuple results
                    processed_rows = []
                    for row in rows:
                        if isinstance(row, dict):
                            processed_rows.append([row.get(col, None) for col in columns])
                        else:
                            processed_rows.append(list(row))
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": processed_rows,
                        "row_count": len(rows),
                        "execution_time": round(time.time() - start_time, 2)
                    }
                else:
                    return {"success": True, "row_count": self._cursor.rowcount}

            else:  # PostgreSQL default
                self._cursor.execute(query, params)
                if self._cursor.description:
                    columns = [desc[0] for desc in self._cursor.description]
                    rows = self._cursor.fetchall()
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                        "execution_time": round(time.time() - start_time, 2)
                    }
                else:
                    self._connection.commit()
                    return {"success": True, "row_count": self._cursor.rowcount}

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_time": round(time.time() - start_time, 2)
            }

    def test_connection(self) -> tuple[bool, str]:
        """Test the connection."""
        try:
            if not self._connection:
                self.connect()

            if self.db_type == DatabaseType.POSTGRESQL:
                self._cursor.execute("SELECT version()")
                version = self._cursor.fetchone()[0]
                return True, f"PostgreSQL connected: {version[:50]}..."

            elif self.db_type == DatabaseType.MYSQL:
                self._cursor.execute("SELECT VERSION()")
                version = self._cursor.fetchone()[0]
                return True, f"MySQL connected: {version}"

            elif self.db_type == DatabaseType.SQLITE:
                self._cursor.execute("SELECT sqlite_version()")
                version = self._cursor.fetchone()[0]
                return True, f"SQLite connected: {version}"

            elif self.db_type == DatabaseType.SNOWFLAKE:
                self._cursor.execute("SELECT CURRENT_VERSION()")
                row = self._cursor.fetchone()
                if isinstance(row, dict):
                    version = row.get('CURRENT_VERSION()', row.get('CURRENT_VERSION', 'unknown'))
                else:
                    version = row[0] if row else 'unknown'
                return True, f"Snowflake connected: {version}"

            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def get_tables(self) -> List[str]:
        """Get list of tables."""
        if not self._connection:
            self.connect()

        if self.db_type == DatabaseType.POSTGRESQL:
            self._cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            return [row[0] for row in self._cursor.fetchall()]

        elif self.db_type == DatabaseType.MYSQL:
            self._cursor.execute("SHOW TABLES")
            return [list(row.values())[0] if isinstance(row, dict) else row[0]
                    for row in self._cursor.fetchall()]

        elif self.db_type == DatabaseType.SQLITE:
            self._cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            return [row[0] for row in self._cursor.fetchall()]

        elif self.db_type == DatabaseType.SNOWFLAKE:
            # Snowflake stores unquoted identifiers in uppercase, so normalize
            # both schema and database to uppercase for matching.
            schema = self.config.get('schema', 'PUBLIC').upper()
            database = self.config.get('database', '').upper()

            logger.info(f"Fetching tables from Snowflake - database: {database}, schema: {schema}")

            try:
                # NOTE: snowflake-connector-python's default paramstyle is
                # 'pyformat' (%(name)s), NOT psycopg2-style positional '%s'.
                # Using '%s' with a list here raises a ProgrammingError on
                # bind, which was the root cause of the 500 error and the
                # "0 tables" result. Fix: build the query with safely-escaped
                # literals (these come from trusted connection config, not
                # end-user input) instead of parameter binding.
                schema_lit = _escape_sql_literal(schema)

                query = f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = '{schema_lit}'
                """

                if database:
                    database_lit = _escape_sql_literal(database)
                    query += f" AND table_catalog = '{database_lit}'"

                query += " ORDER BY table_name"

                logger.info(f"Executing Snowflake query: {query}")
                self._cursor.execute(query)
                rows = self._cursor.fetchall()
                logger.info(f"Found {len(rows)} rows from information_schema.tables")

                tables = []
                for row in rows:
                    if isinstance(row, dict):
                        table_name = row.get('table_name') or row.get('TABLE_NAME')
                    else:
                        table_name = row[0]
                    if table_name:
                        tables.append(table_name)

                logger.info(f"Extracted {len(tables)} tables: {tables}")

                if tables:
                    return tables

                # If information_schema returned nothing (e.g. the role/
                # warehouse can't see information_schema, or the database
                # wasn't set on the session), fall through to SHOW TABLES.
                logger.info("information_schema.tables returned 0 rows, trying SHOW TABLES fallback")

            except Exception as e:
                logger.error(f"Failed to fetch Snowflake tables via information_schema: {e}", exc_info=True)

            # Fallback: try SHOW TABLES if information_schema fails or returns empty
            try:
                if database:
                    full_schema_name = f'"{database}"."{schema}"'
                else:
                    full_schema_name = f'"{schema}"'

                query = f'SHOW TABLES IN SCHEMA {full_schema_name}'
                logger.info(f"Fallback: Executing Snowflake query: {query}")
                self._cursor.execute(query)
                rows = self._cursor.fetchall()

                # Get column names so we can find 'name' robustly regardless
                # of dict vs tuple cursor and column ordering.
                columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
                name_idx = None
                for i, col in enumerate(columns):
                    if col.lower() == 'name':
                        name_idx = i
                        break

                tables = []
                for row in rows:
                    if isinstance(row, dict):
                        table_name = row.get('name') or row.get('NAME')
                    elif name_idx is not None and len(row) > name_idx:
                        table_name = row[name_idx]
                    elif isinstance(row, (list, tuple)) and len(row) > 1:
                        table_name = row[1]
                    else:
                        table_name = None
                    if table_name:
                        tables.append(table_name)

                logger.info(f"Fallback extracted {len(tables)} tables: {tables}")
                return tables
            except Exception as e2:
                logger.error(f"Fallback SHOW TABLES also failed: {e2}", exc_info=True)
                return []

        return []

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema for a specific table."""
        if not self._connection:
            self.connect()

        if self.db_type == DatabaseType.POSTGRESQL:
            self._cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))
            columns = {}
            for row in self._cursor.fetchall():
                columns[row[0]] = {"data_type": row[1], "nullable": row[2]}
            return {"table_name": table_name, "columns": columns, "column_list": list(columns.keys())}

        elif self.db_type == DatabaseType.MYSQL:
            self._cursor.execute("DESCRIBE %s", (table_name,))
            columns = {}
            for row in self._cursor.fetchall():
                if isinstance(row, dict):
                    columns[row['Field']] = {"data_type": row['Type'], "nullable": row['Null']}
                else:
                    columns[row[0]] = {"data_type": row[1], "nullable": row[2]}
            return {"table_name": table_name, "columns": columns, "column_list": list(columns.keys())}

        elif self.db_type == DatabaseType.SQLITE:
            self._cursor.execute(f"PRAGMA table_info({table_name})")
            columns = {}
            for row in self._cursor.fetchall():
                columns[row[1]] = {"data_type": row[2], "nullable": "NO" if row[3] else "YES"}
            return {"table_name": table_name, "columns": columns, "column_list": list(columns.keys())}

        elif self.db_type == DatabaseType.SNOWFLAKE:
            schema = self.config.get('schema', 'PUBLIC').upper()
            database = self.config.get('database', '').upper()

            logger.info(f"Fetching schema for table '{table_name}' from {database}.{schema}")

            try:
                # Use DESCRIBE TABLE with fully qualified, quoted name.
                table_name_upper = table_name.upper()
                if database:
                    full_table_name = f'"{database}"."{schema}"."{table_name_upper}"'
                else:
                    full_table_name = f'"{schema}"."{table_name_upper}"'

                query = f'DESCRIBE TABLE {full_table_name}'
                logger.info(f"Executing: {query}")
                self._cursor.execute(query)
                rows = self._cursor.fetchall()
                logger.info(f"Found {len(rows)} columns")

                columns = {}
                for i, row in enumerate(rows):
                    logger.debug(f"Column row {i}: {row}")
                    if isinstance(row, dict):
                        col_name = (row.get('name') or
                                  row.get('column_name') or
                                  row.get('NAME') or
                                  row.get('COLUMN_NAME', ''))
                        data_type = (row.get('type') or
                                   row.get('data_type') or
                                   row.get('DATA_TYPE') or
                                   row.get('TYPE', 'UNKNOWN'))
                        is_nullable = row.get('null?', row.get('is_nullable', 'YES'))
                        if col_name:
                            columns[col_name] = {"data_type": data_type, "nullable": is_nullable}
                    else:
                        # Tuple: name, type, kind, null?, ...
                        if len(row) >= 4:
                            columns[row[0]] = {"data_type": row[1], "nullable": row[3]}
                        elif len(row) >= 2:
                            columns[row[0]] = {"data_type": row[1], "nullable": "YES"}

                logger.info(f"Extracted {len(columns)} columns: {list(columns.keys())}")
                return {"table_name": table_name, "columns": columns, "column_list": list(columns.keys())}

            except Exception as e:
                logger.error(f"Failed to fetch schema: {e}", exc_info=True)
                return {"table_name": table_name, "columns": {}, "column_list": []}

        return {"table_name": table_name, "columns": {}, "column_list": []}

    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get all table schemas."""
        tables = self.get_tables()
        schemas = {}
        for table in tables:
            schemas[table] = self.get_table_schema(table)
        return schemas

    def close(self):
        """Close the connection."""
        if self._cursor:
            self._cursor.close()
        if self._connection:
            self._connection.close()
        self._connection = None
        self._cursor = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ConnectionManager:
    """
    Manages multiple database connections.
    Loads from both local config file and saved_connections table.
    """

    def __init__(self):
        self.connections: Dict[str, DatabaseConnection] = {}
        # Only load from saved_connections table - not from local file or env
        self._load_saved_connections_from_db()

    def _load_local_connections(self):
        """Load saved connections from local config file."""
        config_path = os.path.expanduser("~/.text2sql/connections.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    for conn_data in data.get("connections", []):
                        self._add_connection_internal(
                            conn_data["name"],
                            DatabaseType(conn_data["type"]),
                            conn_data["config"],
                            conn_data.get("id")
                        )
            except Exception as e:
                print(f"Warning: Could not load local connections: {e}")

    def _load_saved_connections_from_db(self):
        """Load connections from saved_connections table in PostgreSQL."""
        if not PSYCOPG2_AVAILABLE:
            return

        try:
            # Get DB config from environment (same as main.py)
            db_config = {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432"),
                "database": os.getenv("DB_NAME", "airflow"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "spark")
            }

            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()

            # Check if saved_connections table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'saved_connections'
                )
            """)
            table_exists = cur.fetchone()[0]

            if not table_exists:
                cur.close()
                conn.close()
                return

            # Load text-to-sql compatible connections (postgres, mysql, sqlite, snowflake)
            cur.execute("""
                SELECT id, name, source_type, config
                FROM saved_connections
                WHERE source_type IN ('postgres', 'postgresql', 'mysql', 'sqlite', 'snowflake')
            """)

            for row in cur.fetchall():
                try:
                    conn_id = str(row[0])  # Convert ID to string
                    name = row[1]
                    source_type = row[2].lower()
                    config = row[3] if isinstance(row[3], dict) else json.loads(row[3])

                    # Map source_type to DatabaseType
                    type_mapping = {
                        'postgres': DatabaseType.POSTGRESQL,
                        'postgresql': DatabaseType.POSTGRESQL,
                        'mysql': DatabaseType.MYSQL,
                        'sqlite': DatabaseType.SQLITE,
                        'snowflake': DatabaseType.SNOWFLAKE,
                    }

                    db_type = type_mapping.get(source_type)
                    if db_type:
                        # Normalize config keys for text-to-sql
                        normalized_config = self._normalize_config(config, db_type)
                        self._add_connection_internal(name, db_type, normalized_config, conn_id)

                except Exception as e:
                    print(f"Warning: Could not load connection {row[1]}: {e}")

            cur.close()
            conn.close()

        except Exception as e:
            print(f"Warning: Could not load connections from database: {e}")

    def _normalize_config(self, config: Dict[str, Any], db_type: DatabaseType) -> Dict[str, Any]:
        """Normalize config from saved_connections format to text-to-sql format."""
        normalized = {}

        if db_type == DatabaseType.POSTGRESQL:
            normalized = {
                "host": config.get("host", "localhost"),
                "port": int(config.get("port", "5432")),
                "database": config.get("database", ""),
                "user": config.get("user", ""),
                "password": config.get("password", ""),
            }
        elif db_type == DatabaseType.MYSQL:
            normalized = {
                "host": config.get("host", "localhost"),
                "port": int(config.get("port", "3306")),
                "database": config.get("database", ""),
                "user": config.get("user", ""),
                "password": config.get("password", ""),
            }
        elif db_type == DatabaseType.SQLITE:
            normalized = {
                "database_path": config.get("database_path", config.get("base_path", ":memory:"))
            }
        elif db_type == DatabaseType.SNOWFLAKE:
            normalized = {
                "account": config.get("account", ""),
                "user": config.get("user", ""),
                "password": config.get("password", ""),
                "warehouse": config.get("warehouse", ""),
                "database": config.get("database", ""),
                "schema": config.get("schema", "PUBLIC"),
                "role": config.get("role", "") if config.get("role") else config.get("sf_role", "")
            }

        return normalized

    def _add_connection_internal(self, name: str, db_type: DatabaseType, config: Dict[str, Any], connection_id: Optional[str] = None) -> str:
        """Add a connection without saving to file (for loading existing connections)."""
        import uuid
        conn_id = connection_id or str(uuid.uuid4())

        conn = DatabaseConnection(conn_id, name, db_type, config)
        self.connections[conn_id] = conn

        return conn_id

    def _save_connections(self):
        """Save connections to config file."""
        config_dir = os.path.expanduser("~/.text2sql")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "connections.json")

        data = {
            "connections": [
                {
                    "id": conn.connection_id,
                    "name": conn.name,
                    "type": conn.db_type.value,
                    "config": conn.config
                }
                for conn in self.connections.values()
            ]
        }

        try:
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save connections: {e}")

    def add_connection(self, name: str, db_type: DatabaseType, config: Dict[str, Any], connection_id: Optional[str] = None) -> str:
        """Add a new connection."""
        conn_id = self._add_connection_internal(name, db_type, config, connection_id)
        self._save_connections()
        return conn_id

    def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection."""
        if connection_id in self.connections:
            self.connections[connection_id].close()
            del self.connections[connection_id]
            self._save_connections()
            return True
        return False

    def get_connection(self, connection_id: str) -> Optional[DatabaseConnection]:
        """Get a connection by ID."""
        return self.connections.get(connection_id)

    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a connection by name."""
        for conn in self.connections.values():
            if conn.name == name:
                return conn
        return None

    def list_connections(self) -> List[Dict[str, Any]]:
        """List all connections."""
        return [
            {
                "id": conn.connection_id,
                "name": conn.name,
                "type": conn.db_type.value,
                "config": {k: "***" if "password" in k.lower() else v
                          for k, v in conn.config.items()}
            }
            for conn in self.connections.values()
        ]

    def test_connection(self, connection_id: str) -> tuple[bool, str]:
        """Test a connection."""
        conn = self.get_connection(connection_id)
        if not conn:
            return False, "Connection not found"
        return conn.test_connection()

    def get_default_connection(self) -> Optional[DatabaseConnection]:
        """Get the first available connection from saved_connections.

        Returns None if no connections are available.
        Does NOT create a default connection from environment variables.
        """
        if not self.connections:
            return None

        # Return first connection (they are loaded from saved_connections table)
        return list(self.connections.values())[0]


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager