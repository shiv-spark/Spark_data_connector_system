"""
PostgreSQL Query Executor for Text-to-SQL Agent
Executes SQL queries on PostgreSQL and returns results
"""

import time
from typing import Dict, List, Any, Optional, Tuple
from .config import POSTGRES_CONFIG

# Optional PostgreSQL support
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    sql = None


class PostgresExecutor:
    """
    Executes SQL queries on PostgreSQL database.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or POSTGRES_CONFIG
    
    def _get_connection(self):
        """Get PostgreSQL connection."""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("PostgreSQL support requires psycopg2. Install: pip install psycopg2-binary")
        return psycopg2.connect(
            host=self.config["host"],
            port=self.config["port"],
            database=self.config["database"],
            user=self.config["user"],
            password=self.config["password"]
        )
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Execute a SQL query on PostgreSQL.
        
        Args:
            query: SQL query string (SELECT only)
            params: Optional query parameters
        
        Returns:
            Dict with success status, columns, rows, and error (if any)
        """
        conn = None
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Execute query
            cur.execute(query, params)
            
            # Check if query returns results (has description)
            if cur.description:
                # Get column names
                columns = [desc[0] for desc in cur.description]
                # Fetch all rows
                rows = cur.fetchall()
            else:
                # DDL statements (CREATE, INSERT, etc.) don't return rows
                columns = []
                rows = []
                # Commit for write operations
                conn.commit()
            
            execution_time = round(time.time() - start_time, 2)
            
            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time": execution_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time": round(time.time() - start_time, 2)
            }
            
        finally:
            if conn:
                conn.close()
    
    def execute_many(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Execute multiple SQL queries.
        
        Args:
            queries: List of SQL query strings
        
        Returns:
            List of result dictionaries
        """
        results = []
        for query in queries:
            result = self.execute(query)
            results.append(result)
        return results
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test the PostgreSQL connection."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            conn.close()
            return True, f"Connected to PostgreSQL (version: {version})"
        except Exception as e:
            return False, str(e)
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database."""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        result = self.execute(query)
        if result["success"]:
            return [row[0] for row in result["rows"]]
        return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table."""
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        result = self.execute(query, (table_name,))
        if result["success"]:
            columns = {}
            for row in result["rows"]:
                columns[row[0]] = {
                    "data_type": row[1],
                    "nullable": row[2]
                }
            return {
                "table_name": table_name,
                "columns": columns,
                "column_list": list(columns.keys())
            }
        return {}
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get schema information for all tables."""
        query = """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """
        result = self.execute(query)
        schemas = {}
        
        if result["success"]:
            for row in result["rows"]:
                table_name, column_name, data_type, is_nullable = row
                if table_name not in schemas:
                    schemas[table_name] = {
                        "columns": {},
                        "column_list": []
                    }
                schemas[table_name]["columns"][column_name] = {
                    "data_type": data_type,
                    "nullable": is_nullable
                }
                schemas[table_name]["column_list"].append(column_name)
        
        return schemas


if __name__ == "__main__":
    executor = PostgresExecutor()
    
    # Test connection
    success, msg = executor.test_connection()
    print(f"Connection test: {'SUCCESS' if success else 'FAILED'}")
    print(f"Message: {msg}")
    
    if success:
        # Test get tables
        print("\nTables in database:")
        tables = executor.get_tables()
        for table in tables[:10]:  # Limit to first 10
            print(f"  - {table}")
        
        # Test get schema
        if tables:
            print(f"\nSchema for table '{tables[0]}':")
            schema = executor.get_table_schema(tables[0])
            for col, info in schema.get("columns", {}).items():
                print(f"  - {col}: {info['data_type']} ({info['nullable']})")
