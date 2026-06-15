"""
Snowflake Connector for Data Ingestion
Reads data from Snowflake and returns a pandas DataFrame
"""

import os
from typing import Optional

try:
    import snowflake.connector
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

import pandas as pd


def snowflake_connector(
    account: str,
    user: str,
    password: str,
    warehouse: str,
    database: str,
    schema: str,
    query: str,
    role: Optional[str] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Connect to Snowflake and execute a query.
    
    Args:
        account: Snowflake account identifier (e.g., 'xy12345.us-east-1')
        user: Snowflake username
        password: Snowflake password
        warehouse: Snowflake warehouse name
        database: Snowflake database name
        schema: Snowflake schema name
        query: SQL query to execute
        role: Optional Snowflake role
        **kwargs: Additional connection parameters
    
    Returns:
        pandas DataFrame with query results
    """
    if not SNOWFLAKE_AVAILABLE:
        raise ImportError(
            "Snowflake support requires snowflake-connector-python. "
            "Install: pip install snowflake-connector-python"
        )
    
    conn = None
    try:
        # Build connection parameters
        conn_params = {
            "account": account,
            "user": user,
            "password": password,
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
        }
        
        # Add optional role if provided
        if role:
            conn_params["role"] = role
        
        # Connect to Snowflake
        conn = snowflake.connector.connect(**conn_params)
        
        # Execute query and fetch results
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description]
        
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=columns)
        
        cursor.close()
        
        return df
        
    finally:
        if conn:
            conn.close()


def test_snowflake_connection(
    account: str,
    user: str,
    password: str,
    warehouse: str,
    database: str,
    schema: str = "PUBLIC",
    role: Optional[str] = None
) -> tuple[bool, str]:
    """
    Test Snowflake connection.
    
    Returns:
        Tuple of (success, message)
    """
    if not SNOWFLAKE_AVAILABLE:
        return False, "snowflake-connector-python not installed"
    
    try:
        conn_params = {
            "account": account,
            "user": user,
            "password": password,
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
        }
        
        if role:
            conn_params["role"] = role
        
        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return True, f"Snowflake connected: {version}"
        
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    print("Snowflake Connector Test")
    print("=" * 60)
    
    # Test with environment variables
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    
    if all([account, user, password, warehouse, database]):
        print(f"Testing connection to {account}...")
        success, msg = test_snowflake_connection(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema="PUBLIC"
        )
        print(f"Result: {msg}")
    else:
        print("Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,")
        print("SNOWFLAKE_WAREHOUSE, and SNOWFLAKE_DATABASE environment variables")
