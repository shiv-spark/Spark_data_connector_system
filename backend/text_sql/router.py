"""
FastAPI Router for Text-to-SQL Agent

Provides REST API endpoints for the text-to-SQL functionality.
Supports multiple database connections (PostgreSQL, MySQL, SQLite, Snowflake).
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

# Import connection manager first (doesn't require langchain)
from .connection_manager import (
    get_connection_manager,
    DatabaseConnection,
    DatabaseType,
    ConnectionManager
)

# Optional imports - these require langchain
try:
    from .agent import Text2SQLAgent
    from .postgres_schema_manager import PostgresSchemaManager
    from .metadata_logger import PostgresMetadataLogger
    from .postgres_executor import PostgresExecutor
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Text2SQL agent not available: {e}")
    AGENT_AVAILABLE = False
    Text2SQLAgent = None
    PostgresSchemaManager = None
    PostgresMetadataLogger = None
    PostgresExecutor = None


# Request/Response Models
class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(None, description="Database port")
    database: Optional[str] = Field(None, description="Database name")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    database_path: Optional[str] = Field(None, description="Path for SQLite database")
    account: Optional[str] = Field(None, description="Snowflake account")
    warehouse: Optional[str] = Field(None, description="Snowflake warehouse")
    schema: Optional[str] = Field(None, description="Snowflake schema")
    role: Optional[str] = Field(None, description="Snowflake role")
    sslmode: Optional[str] = Field("prefer", description="SSL mode for PostgreSQL")


class ConnectionRequest(BaseModel):
    """Request to create a new database connection."""
    name: str = Field(..., description="Connection name")
    db_type: str = Field(..., description="Database type (postgresql, mysql, sqlite, snowflake)")
    config: DatabaseConfig = Field(..., description="Database configuration")


class ConnectionResponse(BaseModel):
    """Response with connection details."""
    id: str
    name: str
    type: str
    config: Dict[str, Any]


class Text2SQLRequest(BaseModel):
    """Request to ask a natural language question."""
    question: str = Field(..., description="Natural language question about the data")
    connection_id: Optional[str] = Field(None, description="Optional connection ID to use (defaults to default connection)")
    tables: Optional[List[str]] = Field(None, description="Optional list of specific tables to query")
    auto_execute: bool = Field(True, description="Whether to automatically execute the generated SQL")
    include_samples: bool = Field(True, description="Whether to include sample data in schema context")


class Text2SQLResponse(BaseModel):
    """Response from text-to-SQL query."""
    success: bool
    run_id: str
    question: str
    sql: Optional[str]
    connection_id: Optional[str]
    connection_name: Optional[str]
    validation_status: str
    execution_status: str
    row_count: int
    execution_result: Optional[Dict[str, Any]]
    summary: Optional[str]
    llm_latency: float
    execution_latency: float
    total_time: float
    error: Optional[str]


class SchemaInfoResponse(BaseModel):
    """Response with schema information."""
    connection_id: str
    connection_name: str
    db_type: str
    tables: List[str]
    schema_text_length: int
    column_count: int


class TableSchemaResponse(BaseModel):
    """Response with table schema."""
    connection_id: str
    table_name: str
    columns: Dict[str, Dict[str, Any]]
    column_list: List[str]


class MetadataStatsResponse(BaseModel):
    """Response with metadata statistics."""
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_llm_latency: float
    avg_exec_latency: float
    total_tokens: int


class RecentRunResponse(BaseModel):
    """Response with recent run information."""
    run_id: str
    created_at: Any
    user_question: str
    execution_status: str
    row_count: int


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str


# Create router
router = APIRouter(prefix="/text2sql", tags=["Text-to-SQL"])


# Dependencies
def get_connection_manager_dep():
    """Get connection manager instance."""
    manager = get_connection_manager()
    # Refresh connections from database
    manager._load_saved_connections_from_db()
    return manager


def get_connection(connection_id: Optional[str] = None) -> DatabaseConnection:
    """Get a database connection by ID or return default.
    
    Supports both local connections (UUID) and saved_connections table (integer ID).
    """
    manager = get_connection_manager()
    
    if connection_id:
        # Try to get by ID directly
        conn = manager.get_connection(connection_id)
        if conn:
            return conn
        
        # If not found and ID looks like a saved_connections ID (integer), try converting
        try:
            # Reload from database to get latest connections
            manager._load_saved_connections_from_db()
            conn = manager.get_connection(connection_id)
            if conn:
                return conn
        except Exception:
            pass
        
        raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
    
    # Return default connection
    conn = manager.get_default_connection()
    if not conn:
        raise HTTPException(status_code=404, detail="No default connection available")
    return conn


# ============ Connection Management Endpoints ============

@router.get("/connections", response_model=List[ConnectionResponse])
async def list_connections(
    manager: ConnectionManager = Depends(get_connection_manager_dep)
):
    """
    List all saved database connections.
    
    Returns a list of all configured database connections with their
    details (passwords are masked for security).
    """
    try:
        connections = manager.list_connections()
        return [
            ConnectionResponse(
                id=conn["id"],
                name=conn["name"],
                type=conn["type"],
                config=conn["config"]
            )
            for conn in connections
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections", response_model=ConnectionResponse)
async def create_connection(
    request: ConnectionRequest,
    manager: ConnectionManager = Depends(get_connection_manager_dep)
):
    """
    Create a new database connection.
    
    Supports PostgreSQL, MySQL, SQLite, and Snowflake databases.
    
    **Example - PostgreSQL:**
    ```json
    {
      "name": "My Postgres DB",
      "db_type": "postgresql",
      "config": {
        "host": "localhost",
        "port": 5432,
        "database": "mydb",
        "user": "postgres",
        "password": "secret"
      }
    }
    ```
    
    **Example - Snowflake:**
    ```json
    {
      "name": "My Snowflake DWH",
      "db_type": "snowflake",
      "config": {
        "account": "xy12345.us-east-1",
        "user": "username",
        "password": "secret",
        "warehouse": "COMPUTE_WH",
        "database": "MY_DB",
        "schema": "PUBLIC",
        "role": "ACCOUNTADMIN"
      }
    }
    ```
    """
    try:
        # Map string type to enum
        try:
            db_type = DatabaseType(request.db_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid database type: {request.db_type}. Must be one of: postgresql, mysql, sqlite, snowflake"
            )
        
        # Convert config to dict
        config = request.config.dict(exclude_none=True)
        
        # Create connection
        conn_id = manager.add_connection(request.name, db_type, config)
        
        return ConnectionResponse(
            id=conn_id,
            name=request.name,
            type=request.db_type,
            config=config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection_details(
    connection_id: str,
    manager: ConnectionManager = Depends(get_connection_manager_dep)
):
    """
    Get details of a specific connection.
    """
    try:
        conn = manager.get_connection(connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
        
        return ConnectionResponse(
            id=conn.connection_id,
            name=conn.name,
            type=conn.db_type.value,
            config={k: "***" if "password" in k.lower() else v 
                   for k, v in conn.config.items()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    manager: ConnectionManager = Depends(get_connection_manager_dep)
):
    """
    Delete a database connection.
    """
    try:
        success = manager.remove_connection(connection_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
        
        return {"success": True, "message": f"Connection '{connection_id}' deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: str,
    manager: ConnectionManager = Depends(get_connection_manager_dep)
):
    """
    Test a database connection.
    
    Attempts to connect to the database and returns the result.
    """
    try:
        success, message = manager.test_connection(connection_id)
        return ConnectionTestResponse(success=success, message=message)
        
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))


# ============ Text-to-SQL Query Endpoints ============

@router.post("/ask", response_model=Text2SQLResponse)
async def ask_question(request: Text2SQLRequest):
    """
    Convert natural language question to SQL and optionally execute it.
    
    This endpoint takes a natural language question, generates a SQL query,
    validates it, optionally executes it, and returns the results with a summary.
    
    You can specify a connection_id to query a specific database.
    If not provided, uses the default connection.
    """
    try:
        # Get the connection
        manager = get_connection_manager()
        conn = get_connection(request.connection_id)
        
        # Create agent with this connection
        agent = Text2SQLAgent(
            connection=conn,
            tables=request.tables,
            include_samples=request.include_samples
        )
        
        result = agent.run(request.question, auto_execute=request.auto_execute)
        
        return Text2SQLResponse(
            success=result.get("success", False),
            run_id=result.get("run_id", ""),
            question=result.get("question", ""),
            sql=result.get("sql"),
            connection_id=conn.connection_id,
            connection_name=conn.name,
            validation_status=result.get("validation_status", "UNKNOWN"),
            execution_status=result.get("execution_status", "UNKNOWN"),
            row_count=result.get("row_count", 0),
            execution_result=result.get("execution_result"),
            summary=result.get("summary"),
            llm_latency=result.get("llm_latency", 0.0),
            execution_latency=result.get("execution_latency", 0.0),
            total_time=result.get("total_time", 0.0),
            error=result.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=Dict[str, Any])
async def generate_sql_only(request: Text2SQLRequest):
    """
    Generate SQL from natural language question without executing.
    
    This endpoint is useful for getting the SQL query without actually
    running it against the database.
    """
    try:
        # Get the connection
        conn = get_connection(request.connection_id)
        
        # Create agent
        agent = Text2SQLAgent(
            connection=conn,
            tables=request.tables,
            include_samples=request.include_samples
        )
        
        # Generate SQL only
        generation = agent.generate_sql(request.question)
        
        if not generation.get("success"):
            return {
                "success": False,
                "error": generation.get("error", "Failed to generate SQL"),
                "attempts": generation.get("attempts", 0)
            }
        
        # Validate the SQL
        is_valid, validation_msg = agent.validate(generation["sql"])
        
        return {
            "success": True,
            "sql": generation["sql"],
            "is_valid": is_valid,
            "validation_message": validation_msg,
            "prompt_tokens": generation.get("prompt_tokens", 0),
            "completion_tokens": generation.get("completion_tokens", 0),
            "total_tokens": generation.get("total_tokens", 0),
            "llm_latency": generation.get("llm_latency", 0.0),
            "attempts": generation.get("attempts", 0),
            "connection_id": conn.connection_id,
            "connection_name": conn.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Schema Endpoints (Connection-specific) ============

@router.get("/schema", response_model=SchemaInfoResponse)
async def get_schema_info(
    connection_id: Optional[str] = Query(None, description="Connection ID (uses default if not provided)"),
    tables: Optional[str] = Query(None, description="Comma-separated list of table names")
):
    """
    Get database schema information.
    
    Returns information about available tables and their structure.
    Optionally filter to specific tables.
    """
    try:
        conn = get_connection(connection_id)
        
        table_list = None
        if tables:
            table_list = [t.strip() for t in tables.split(",")]
        
        # Get schema from connection
        schema_dict = conn.get_all_schemas()
        
        if table_list:
            schema_dict = {k: v for k, v in schema_dict.items() if k in table_list}
        
        # Build schema text directly
        schema_parts = []
        schema_parts.append(f"Database: {conn.name}")
        schema_parts.append(f"Type: {conn.db_type.value}")
        schema_parts.append("")
        
        for table_name in sorted(schema_dict.keys()):
            table_info = schema_dict[table_name]
            schema_parts.append("-" * 60)
            schema_parts.append(f"Table: {table_name}")
            schema_parts.append("  Columns:")
            
            for col_name in table_info.get("column_list", []):
                col_info = table_info.get("columns", {}).get(col_name, {})
                data_type = col_info.get("data_type", "UNKNOWN")
                nullable = col_info.get("nullable", "YES")
                schema_parts.append(f"    - {col_name} ({data_type}, {nullable})")
            
            schema_parts.append("")
        
        schema_text = "\n".join(schema_parts)
        
        return SchemaInfoResponse(
            connection_id=conn.connection_id,
            connection_name=conn.name,
            db_type=conn.db_type.value,
            tables=list(schema_dict.keys()),
            schema_text_length=len(schema_text),
            column_count=sum(len(v.get("column_list", [])) for v in schema_dict.values())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{table_name}", response_model=TableSchemaResponse)
async def get_table_schema(
    table_name: str,
    connection_id: Optional[str] = Query(None, description="Connection ID")
):
    """
    Get detailed schema for a specific table.
    """
    try:
        conn = get_connection(connection_id)
        schema = conn.get_table_schema(table_name)
        
        if not schema or not schema.get("columns"):
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found in connection '{conn.name}'")
        
        return TableSchemaResponse(
            connection_id=conn.connection_id,
            table_name=schema["table_name"],
            columns=schema["columns"],
            column_list=schema["column_list"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables", response_model=Dict[str, Any])
async def list_tables(
    connection_id: Optional[str] = Query(None, description="Connection ID")
):
    """
    List all available tables in the database.
    """
    try:
        conn = get_connection(connection_id)
        tables = conn.get_tables()
        
        return {
            "connection_id": conn.connection_id,
            "connection_name": conn.name,
            "db_type": conn.db_type.value,
            "tables": tables
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Execute Endpoint ============

@router.post("/execute", response_model=Dict[str, Any])
async def execute_sql_directly(
    sql: str,
    connection_id: Optional[str] = Query(None, description="Connection ID")
):
    """
    Execute a SQL query directly (for testing/validation).
    
    WARNING: This should be used with caution. Only SELECT queries are allowed.
    """
    try:
        from .sql_validator import validate_sql
        
        conn = get_connection(connection_id)
        
        # Get schema for validation
        schema_dict = {k: set(v.get("column_list", [])) 
                      for k, v in conn.get_all_schemas().items()}
        
        # Validate the SQL
        is_valid, validation_msg = validate_sql(sql, schema_dict)
        
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"SQL validation failed: {validation_msg}"
            )
        
        # Execute the query on the specific connection
        result = conn.execute(sql)
        
        return {
            "success": result.get("success", False),
            "connection_id": conn.connection_id,
            "connection_name": conn.name,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "execution_time": result.get("execution_time", 0.0),
            "error": result.get("error")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Metadata Endpoints ============

@router.get("/metadata/stats", response_model=MetadataStatsResponse)
async def get_metadata_stats():
    """
    Get statistics from the metadata logging table.
    """
    try:
        logger = PostgresMetadataLogger()
        stats = logger.get_stats()
        
        return MetadataStatsResponse(
            total_runs=stats.get("total_runs", 0),
            successful_runs=stats.get("successful_runs", 0),
            failed_runs=stats.get("failed_runs", 0),
            avg_llm_latency=round(stats.get("avg_llm_latency", 0.0), 2),
            avg_exec_latency=round(stats.get("avg_exec_latency", 0.0), 2),
            total_tokens=stats.get("total_tokens", 0)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata/runs", response_model=List[RecentRunResponse])
async def get_recent_runs(limit: int = Query(10, ge=1, le=100)):
    """
    Get recent query runs from the metadata table.
    """
    try:
        logger = PostgresMetadataLogger()
        runs = logger.get_recent_runs(limit)
        
        return [
            RecentRunResponse(
                run_id=run["run_id"],
                created_at=run["created_at"],
                user_question=run["user_question"],
                execution_status=run["execution_status"],
                row_count=run["row_count"]
            )
            for run in runs
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata/runs/{run_id}", response_model=Dict[str, Any])
async def get_run_by_id(run_id: str):
    """
    Get details of a specific run by ID.
    """
    try:
        logger = PostgresMetadataLogger()
        run = logger.get_run_by_id(run_id)
        
        if not run:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        
        return run
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Health Endpoint ============

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the text2sql service.
    """
    try:
        manager = get_connection_manager()
        conn = manager.get_default_connection()
        
        if conn:
            success, msg = conn.test_connection()
            return {
                "status": "healthy" if success else "degraded",
                "database_connection": "connected" if success else "failed",
                "connection_name": conn.name,
                "db_type": conn.db_type.value,
                "message": msg
            }
        else:
            return {
                "status": "degraded",
                "database_connection": "no_default",
                "message": "No default connection configured"
            }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "database_connection": "failed",
            "message": str(e)
        }


# Export router
__all__ = ["router"]
