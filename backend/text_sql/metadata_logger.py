"""
Metadata Logger for PostgreSQL - Text2SQL Run Metadata
Logs query runs to the text2sql_run_metadata table in PostgreSQL
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from .postgres_executor import PostgresExecutor
from .config import METADATA_TABLE_NAME, METADATA_TABLE_SCHEMA


class PostgresMetadataLogger:
    """
    Logs query execution metadata to PostgreSQL table: text2sql_run_metadata
    
    Table Schema:
    - run_id: UUID PRIMARY KEY
    - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    - user_question: TEXT
    - generated_sql: TEXT
    - validation_status: VARCHAR(50)
    - execution_approved: BOOLEAN
    - execution_status: VARCHAR(50)
    - row_count: INTEGER
    - model_name: VARCHAR(100)
    - prompt_tokens: INTEGER
    - completion_tokens: INTEGER
    - total_tokens: INTEGER
    - llm_latency_seconds: NUMERIC(10,2)
    - execution_latency_seconds: NUMERIC(10,2)
    - response_summary: TEXT
    - error_message: TEXT
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.executor = PostgresExecutor(config)
        self.table_name = METADATA_TABLE_NAME
        # Ensure table exists on initialization
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create the metadata table if it doesn't exist."""
        create_sql = METADATA_TABLE_SCHEMA.format(table_name=self.table_name)
        result = self.executor.execute(create_sql)
        if result["success"]:
            print(f"✓ Table '{self.table_name}' ready")
        else:
            print(f"✗ Error ensuring table exists: {result.get('error', 'Unknown error')}")
    
    def insert_run(self, metadata: Dict[str, Any]) -> bool:
        """
        Insert a query run log into text2sql_run_metadata.
        
        Args:
            metadata: Dict with run details matching the table schema
            
        Returns:
            True if successful, False otherwise
        """
        query = f"""
            INSERT INTO {self.table_name} (
                run_id, user_question, generated_sql, validation_status,
                execution_approved, execution_status, row_count, model_name,
                prompt_tokens, completion_tokens, total_tokens,
                llm_latency_seconds, execution_latency_seconds,
                response_summary, error_message
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params = (
            metadata.get("run_id", str(uuid.uuid4())),
            metadata.get("user_question"),
            metadata.get("generated_sql"),
            metadata.get("validation_status"),
            metadata.get("execution_approved"),
            metadata.get("execution_status"),
            metadata.get("row_count"),
            metadata.get("model_name"),
            metadata.get("prompt_tokens"),
            metadata.get("completion_tokens"),
            metadata.get("total_tokens"),
            metadata.get("llm_latency_seconds"),
            metadata.get("execution_latency_seconds"),
            metadata.get("response_summary"),
            metadata.get("error_message")
        )
        
        result = self.executor.execute(query, params)
        
        if result["success"]:
            print(f"✓ Query logged to {self.table_name}")
            return True
        else:
            print(f"✗ Warning: Could not log run: {result.get('error', 'Unknown error')}")
            return False
    
    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent query runs from the metadata table.
        
        Args:
            limit: Number of records to return
            
        Returns:
            List of recent runs as dictionaries
        """
        query = f"""
            SELECT run_id, created_at, user_question, execution_status, row_count
            FROM {self.table_name}
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        result = self.executor.execute(query, (limit,))
        
        if result["success"]:
            runs = []
            for row in result["rows"]:
                runs.append({
                    "run_id": row[0],
                    "created_at": row[1],
                    "user_question": row[2],
                    "execution_status": row[3],
                    "row_count": row[4]
                })
            return runs
        
        return []
    
    def get_run_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific run by ID.
        
        Args:
            run_id: UUID of the run
            
        Returns:
            Run details as dictionary or None if not found
        """
        query = f"""
            SELECT *
            FROM {self.table_name}
            WHERE run_id = %s
        """
        
        result = self.executor.execute(query, (run_id,))
        
        if result["success"] and result["rows"]:
            columns = result["columns"]
            row = result["rows"][0]
            return dict(zip(columns, row))
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from the metadata table.
        
        Returns:
            Dictionary with statistics
        """
        queries = {
            "total_runs": f"SELECT COUNT(*) FROM {self.table_name}",
            "successful_runs": f"SELECT COUNT(*) FROM {self.table_name} WHERE execution_status = 'SUCCESS'",
            "failed_runs": f"SELECT COUNT(*) FROM {self.table_name} WHERE execution_status = 'FAILED'",
            "avg_llm_latency": f"SELECT AVG(llm_latency_seconds) FROM {self.table_name}",
            "avg_exec_latency": f"SELECT AVG(execution_latency_seconds) FROM {self.table_name}",
            "total_tokens": f"SELECT SUM(total_tokens) FROM {self.table_name}",
        }
        
        stats = {}
        for key, query in queries.items():
            result = self.executor.execute(query)
            if result["success"] and result["rows"]:
                value = result["rows"][0][0]
                stats[key] = value if value is not None else 0
            else:
                stats[key] = 0
        
        return stats


if __name__ == "__main__":
    print("=" * 60)
    print("PostgreSQL Metadata Logger Test")
    print("=" * 60)
    
    logger = PostgresMetadataLogger()
    
    # Test logging
    test_metadata = {
        "run_id": str(uuid.uuid4()),
        "user_question": "Test question: Show me all users",
        "generated_sql": "SELECT * FROM users LIMIT 10",
        "validation_status": "VALID",
        "execution_approved": True,
        "execution_status": "SUCCESS",
        "row_count": 10,
        "model_name": "llama-3.3-70b-versatile",
        "prompt_tokens": 500,
        "completion_tokens": 150,
        "total_tokens": 650,
        "llm_latency_seconds": 2.5,
        "execution_latency_seconds": 0.8,
        "response_summary": "Found 10 users in the database",
        "error_message": None
    }
    
    success = logger.insert_run(test_metadata)
    print(f"\nInsert successful: {success}")
    
    # Show recent runs
    print("\nRecent runs:")
    recent = logger.get_recent_runs(5)
    for run in recent:
        print(f"  {run['run_id'][:8]}... | {run['created_at']} | {run['user_question'][:50]}... | Status: {run['execution_status']} | Rows: {run['row_count']}")
    
    # Show stats
    print("\nStatistics:")
    stats = logger.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
