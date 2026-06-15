"""
Metadata Logger for Snowflake - Text2SQL Run Metadata
Logs query runs to the text2sql_run_metadata table in Snowflake
"""

import uuid
import snowflake.connector
from snowflake_config import SNOWFLAKE_CONFIG


class SnowflakeMetadataLogger:
    """
    Logs query execution metadata to Snowflake table: text2sql_run_metadata
    
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
    
    TABLE_NAME = "text2sql_run_metadata"
    
    def __init__(self):
        self.config = SNOWFLAKE_CONFIG
        # Ensure table exists on initialization
        self._ensure_table_exists()
    
    def _get_connection(self):
        """Get Snowflake connection."""
        return snowflake.connector.connect(
            user=self.config["user"],
            password=self.config["password"],
            account=self.config["account"],
            warehouse=self.config["warehouse"],
            database=self.config["database"],
            schema=self.config["schema"]
        )
    
    def check_table_exists(self):
        """Check if the metadata table exists."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Check if table exists in current schema
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = '{self.TABLE_NAME.upper()}'
                AND TABLE_SCHEMA = CURRENT_SCHEMA()
            """)
            
            result = cur.fetchone()
            return result[0] > 0
            
        except Exception as e:
            print(f"Warning: Could not check table existence: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def create_table(self):
        """Create the text2sql_run_metadata table."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Use the schema from config
            schema = self.config.get("schema", "PUBLIC")
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {schema}.{self.TABLE_NAME} (
                run_id VARCHAR(36) PRIMARY KEY,
                created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                user_question TEXT,
                generated_sql TEXT,
                validation_status VARCHAR(50),
                execution_approved BOOLEAN,
                execution_status VARCHAR(50),
                row_count INTEGER,
                model_name VARCHAR(100),
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                llm_latency_seconds NUMBER(10,2),
                execution_latency_seconds NUMBER(10,2),
                response_summary TEXT,
                error_message TEXT
            )
            """
            
            cur.execute(create_table_sql)
            conn.commit()
            
            print(f"✓ Table '{self.TABLE_NAME}' created successfully in schema '{schema}'")
            return True
            
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def _ensure_table_exists(self):
        """Create the metadata table if it doesn't exist."""
        if not self.check_table_exists():
            print(f"Table '{self.TABLE_NAME}' not found. Creating...")
            return self.create_table()
        return True
    
    def insert_run(self, metadata):
        """
        Insert a query run log into text2sql_run_metadata.
        
        Args:
            metadata: Dict with run details matching the table schema
        """
        # Ensure table exists
        self._ensure_table_exists()
        
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            schema = self.config.get("schema", "PUBLIC")
            
            insert_sql = f"""
            INSERT INTO {schema}.{self.TABLE_NAME} (
                run_id, user_question, generated_sql, validation_status,
                execution_approved, execution_status, row_count, model_name,
                prompt_tokens, completion_tokens, total_tokens,
                llm_latency_seconds, execution_latency_seconds,
                response_summary, error_message
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            
            cur.execute(insert_sql, (
                metadata.get("run_id"),
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
            ))
            
            conn.commit()
            print(f"✓ Query logged to {self.TABLE_NAME}")
            
        except Exception as e:
            print(f"✗ Warning: Could not log run: {e}")
        finally:
            if conn:
                conn.close()
    
    def get_recent_runs(self, limit=10):
        """
        Get recent query runs from the metadata table.
        
        Args:
            limit: Number of records to return
            
        Returns:
            List of recent runs
        """
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            schema = self.config.get("schema", "PUBLIC")
            
            cur.execute(f"""
                SELECT run_id, created_at, user_question, execution_status, row_count
                FROM {schema}.{self.TABLE_NAME}
                ORDER BY created_at DESC
                LIMIT {limit}
            """)
            
            rows = cur.fetchall()
            return rows
            
        except Exception as e:
            print(f"Error fetching recent runs: {e}")
            return []
        finally:
            if conn:
                conn.close()


if __name__ == "__main__":
    logger = SnowflakeMetadataLogger()
    
    # Test logging
    test_metadata = {
        "run_id": str(uuid.uuid4()),
        "user_question": "Test question: Show me all departments",
        "generated_sql": "SELECT * FROM AGENT_DB.agents.departments",
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
        "response_summary": "Found 10 departments in the organization",
        "error_message": None
    }
    
    logger.insert_run(test_metadata)
    
    # Show recent runs
    print("\nRecent runs:")
    recent = logger.get_recent_runs(5)
    for run in recent:
        print(f"  {run[0][:8]}... | {run[1]} | {run[2][:50]}... | Status: {run[3]} | Rows: {run[4]}")
