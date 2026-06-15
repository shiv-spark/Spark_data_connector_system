"""
Snowflake Query Executor
Executes SQL queries on Snowflake and returns results
"""

import snowflake.connector
from snowflake_config import SNOWFLAKE_CONFIG


class SnowflakeExecutor:
    """
    Executes SQL queries on Snowflake database.
    """
    
    def __init__(self):
        self.config = SNOWFLAKE_CONFIG
    
    def execute(self, sql):
        """
        Execute a SQL query on Snowflake.
        
        Args:
            sql: SQL query string (SELECT only)
        
        Returns:
            Dict with success status, columns, rows, and error (if any)
        """
        
        conn = None
        
        try:
            conn = snowflake.connector.connect(
                user=self.config["user"],
                password=self.config["password"],
                account=self.config["account"],
                warehouse=self.config["warehouse"],
                database=self.config["database"],
                schema=self.config["schema"]
            )
            
            cur = conn.cursor()
            
            # Execute query
            cur.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cur.description] if cur.description else []
            
            # Fetch all rows
            rows = cur.fetchall()
            
            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0
            }
            
        finally:
            if conn:
                conn.close()
    
    def test_connection(self):
        """Test the Snowflake connection."""
        try:
            conn = snowflake.connector.connect(
                user=self.config["user"],
                password=self.config["password"],
                account=self.config["account"],
                warehouse=self.config["warehouse"],
                database=self.config["database"],
                schema=self.config["schema"]
            )
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION()")
            version = cur.fetchone()[0]
            conn.close()
            return True, f"Connected to Snowflake (version: {version})"
        except Exception as e:
            return False, str(e)


if __name__ == "__main__":
    executor = SnowflakeExecutor()
    
    # Test connection
    success, msg = executor.test_connection()
    print(f"Connection test: {'SUCCESS' if success else 'FAILED'}")
    print(f"Message: {msg}")
    
    if success:
        # Test a simple query
        print("\nTesting query execution...")
        result = executor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")
        if result["success"]:
            print(f"Database: {result['rows'][0][0]}")
            print(f"Schema: {result['rows'][0][1]}")
        else:
            print(f"Query failed: {result['error']}")
