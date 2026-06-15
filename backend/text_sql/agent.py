"""
Text-to-SQL Agent for Multiple Databases

Main agent that orchestrates natural language to SQL conversion.
Supports PostgreSQL, MySQL, SQLite, and Snowflake.
"""

import os
import time
import re
import uuid
import json
from typing import Dict, Any, Optional, List, Tuple

# Optional langchain imports - handle gracefully if not installed
try:
    from langchain_groq import ChatGroq
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatGroq = None
    ChatOpenAI = None
    ChatPromptTemplate = None

from .config import (
    MODEL_NAME,
    MAX_RETRIES,
    BLOCK_PATTERNS,
    LLM_PROVIDER,
    API_KEY,
    TEMPERATURE,
)
from .sql_validator import clean_sql, validate_sql
from .metadata_logger import PostgresMetadataLogger
from .connection_manager import DatabaseConnection, DatabaseType


# Database-specific SQL generation prompts
SQL_GENERATION_PROMPTS = {
    DatabaseType.POSTGRESQL: """You are an expert PostgreSQL SQL engineer.

Schema:
{schema}

CRITICAL RULES:
- Return exactly one PostgreSQL SELECT query
- Output only raw SQL, no explanations, no markdown
- Use only the tables and columns listed in the schema above
- Read-only queries only (SELECT statements only)
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL
- Prefer explicit JOIN syntax
- Use table aliases when joining (e.g., SELECT u.name FROM users u)
- If the user asks for top N, use ORDER BY and LIMIT N
- Use proper PostgreSQL functions: DATE_TRUNC, DATE_PART, CURRENT_DATE, EXTRACT, etc.
- Cast data types explicitly when needed using :: syntax (e.g., column::DATE)
- For date differences: use AGE(end_date, start_date) or (end_date - start_date)
- For aggregations: use GROUP BY with all non-aggregated columns

COLUMN NAME RULES:
- Use ONLY the exact column names as shown in the schema
- Column descriptions after "|" are NOT part of the column name
- Never add column descriptions or meanings as aliases or column names
- Never use spaces in column references

User Request:
{question}
""",

    DatabaseType.MYSQL: """You are an expert MySQL SQL engineer.

Schema:
{schema}

CRITICAL RULES:
- Return exactly one MySQL SELECT query
- Output only raw SQL, no explanations, no markdown
- Use only the tables and columns listed in the schema above
- Read-only queries only (SELECT statements only)
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL
- Prefer explicit JOIN syntax
- Use table aliases when joining (e.g., SELECT u.name FROM users u)
- If the user asks for top N, use ORDER BY and LIMIT N
- Use proper MySQL functions: DATE_FORMAT, CURDATE(), DATEDIFF, TIMESTAMPDIFF, etc.
- Use backticks (`) for identifiers if needed

COLUMN NAME RULES:
- Use ONLY the exact column names as shown in the schema
- Never add column descriptions or meanings as aliases or column names
- Never use spaces in column references

User Request:
{question}
""",

    DatabaseType.SQLITE: """You are an expert SQLite SQL engineer.

Schema:
{schema}

CRITICAL RULES:
- Return exactly one SQLite SELECT query
- Output only raw SQL, no explanations, no markdown
- Use only the tables and columns listed in the schema above
- Read-only queries only (SELECT statements only)
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL
- Prefer explicit JOIN syntax
- Use table aliases when joining (e.g., SELECT u.name FROM users u)
- If the user asks for top N, use ORDER BY and LIMIT N
- Use proper SQLite functions: strftime, date, time, julianday, etc.
- Use double quotes (") for identifiers if needed

COLUMN NAME RULES:
- Use ONLY the exact column names as shown in the schema
- Never add column descriptions or meanings as aliases or column names
- Never use spaces in column references

User Request:
{question}
""",

    DatabaseType.SNOWFLAKE: """You are an expert Snowflake SQL engineer.

Schema:
{schema}

CRITICAL RULES:
- Return exactly one Snowflake SELECT query
- Output only raw SQL, no explanations, no markdown
- For table names use the EXACT fully-qualified names given in the schema
  above (the "Fully-qualified table prefix" plus table name). Do not invent,
  guess, or substitute any other database/schema name (e.g. never use
  "snowflake.public").
- Use only the tables and columns listed in the schema above
- Read-only queries only (SELECT statements only)
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL
- Prefer explicit JOIN syntax
- Use table aliases when joining
- If the user asks for top N, use ORDER BY and LIMIT N
- Use proper Snowflake functions: DATE_TRUNC, DATE_PART, CURRENT_DATE, DATEDIFF, etc.
- Cast data types explicitly when needed using :: syntax (e.g., column::DATE)
- Always include date part in DATEDIFF: DATEDIFF(day, start, end)

COLUMN NAME RULES:
- Use ONLY the exact column names as shown in the schema
- Never add column descriptions or meanings as aliases or column names
- Never use spaces in column references

User Request:
{question}
""",
}


RESULT_SUMMARY_PROMPT = """You are a business analyst summarizing database query results.

User Question:
{question}

SQL Query:
{sql}

Result Summary:
- Total Rows: {row_count}
- Columns: {columns}

First 10 Rows (as JSON):
{sample_data}

Provide:
1. A brief, conversational answer to the user's question
2. Key insights from the data
3. Any notable patterns or observations

Keep the response under 150 words and make it natural and helpful.
"""


ERROR_SUMMARY_PROMPT = """You are a helpful assistant explaining a database query error.

User Question:
{question}

Generated SQL:
{sql}

Error:
{error}

Provide:
1. A brief explanation of what went wrong
2. A helpful suggestion for what the user could try instead

Keep the response under 100 words.
"""


class Text2SQLAgent:
    """
    Text-to-SQL Agent supporting multiple database types.
    
    Supports: PostgreSQL, MySQL, SQLite, Snowflake
    """
    
    def __init__(self, connection: DatabaseConnection, tables: Optional[List[str]] = None, include_samples: bool = True):
        """
        Initialize the Text2SQL Agent.
        
        Args:
            connection: DatabaseConnection instance
            tables: Optional list of specific tables to use
            include_samples: Whether to include sample data in schema
        """
        self.connection = connection
        self.tables = tables
        self.include_samples = include_samples
        
        # Load schema from connection
        self.schema_dict = connection.get_all_schemas()
        if tables:
            self.schema_dict = {k: v for k, v in self.schema_dict.items() if k in tables}
        
        self.schema_text = self._build_schema_text()
        
        # Initialize LLM
        self.llm = self._init_llm()
        
        # Get appropriate prompt for database type
        prompt_template = SQL_GENERATION_PROMPTS.get(
            connection.db_type, 
            SQL_GENERATION_PROMPTS[DatabaseType.POSTGRESQL]
        )
        self.prompt = ChatPromptTemplate.from_template(prompt_template)
    
    def _get_table_prefix(self) -> str:
        """
        Build the fully-qualified table prefix for the connection's
        database type.

        For Snowflake this returns "DATABASE.SCHEMA." so that table names
        in the schema text (and therefore in generated SQL) are correctly
        qualified using the *actual* connection config, instead of the LLM
        guessing/hallucinating a placeholder like "snowflake.public".

        For other database types this returns "" (no prefix needed).
        """
        if self.connection.db_type == DatabaseType.SNOWFLAKE:
            db = self.connection.config.get("database", "")
            sch = self.connection.config.get("schema", "")
            if db and sch:
                return f"{db}.{sch}."
        return ""

    def _build_schema_text(self) -> str:
        """Build schema text from connection's schema dict."""
        schema_parts = []
        schema_parts.append(f"Database: {self.connection.name}")
        schema_parts.append(f"Type: {self.connection.db_type.value}")

        table_prefix = self._get_table_prefix()
        if table_prefix:
            schema_parts.append(f"Fully-qualified table prefix: {table_prefix}")
            schema_parts.append(
                "IMPORTANT: Always reference tables using this exact prefix, "
                f"e.g. {table_prefix}<TABLE_NAME>. Do NOT use any other "
                "database or schema name (e.g. do not use 'snowflake.public')."
            )

        schema_parts.append("")
        
        for table_name in sorted(self.schema_dict.keys()):
            table_info = self.schema_dict[table_name]
            schema_parts.append("-" * 60)
            display_name = f"{table_prefix}{table_name}" if table_prefix else table_name
            schema_parts.append(f"Table: {display_name}")
            schema_parts.append("  Columns:")
            
            for col_name in table_info.get("column_list", []):
                col_info = table_info.get("columns", {}).get(col_name, {})
                data_type = col_info.get("data_type", "UNKNOWN")
                nullable = col_info.get("nullable", "YES")
                schema_parts.append(f"    - {col_name} ({data_type}, {nullable})")
            
            schema_parts.append("")
        
        return "\n".join(schema_parts)
    
    def _init_llm(self):
        """Initialize the LLM based on configuration."""
        if LLM_PROVIDER == "groq":
            return ChatGroq(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                api_key=API_KEY or os.getenv("GROQ_API_KEY")
            )
        elif LLM_PROVIDER == "openrouter":
            return ChatOpenAI(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                api_key=API_KEY or os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            return ChatGroq(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                api_key=API_KEY or os.getenv("GROQ_API_KEY")
            )
    
    def _extract_response(self, response) -> str:
        """Extract content from LLM response."""
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip()
        return ""
    
    def screen_input(self, question: str) -> Tuple[bool, str]:
        """
        Screen user input for malicious patterns.
        
        Args:
            question: User's natural language question
            
        Returns:
            Tuple of (is_safe, message)
        """
        q = question.strip().lower()
        
        if not q:
            return False, "Empty question"
        
        for pattern in BLOCK_PATTERNS:
            if re.search(pattern, q):
                return False, f"Blocked pattern detected: {pattern}"
        
        return True, "SAFE"
    
    def generate_sql(self, question: str) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.
        
        Args:
            question: User's natural language question
            
        Returns:
            Dictionary with SQL generation results
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                messages = self.prompt.format_messages(
                    schema=self.schema_text,
                    question=question
                )
                
                start = time.time()
                response = self.llm.invoke(messages)
                elapsed = round(time.time() - start, 2)
                
                # Extract usage metadata if available
                usage_metadata = getattr(response, "usage_metadata", {})
                
                sql = clean_sql(self._extract_response(response))

                if sql:
                    sql = self._fix_table_qualification(sql)

                if sql:
                    return {
                        "success": True,
                        "sql": sql,
                        "prompt_tokens": usage_metadata.get("input_tokens", 0),
                        "completion_tokens": usage_metadata.get("output_tokens", 0),
                        "total_tokens": usage_metadata.get("total_tokens", 0),
                        "llm_latency": elapsed,
                        "attempts": attempt
                    }
                
            except Exception as e:
                print(f"Attempt {attempt} failed: {e}")
        
        return {
            "success": False,
            "error": "Failed to generate SQL after all retries",
            "attempts": MAX_RETRIES
        }

    def _fix_table_qualification(self, sql: str) -> str:
        """
        Safety net for Snowflake: if the LLM still produces table references
        using a wrong/hallucinated database.schema prefix (e.g.
        "snowflake.public.INVENTORY"), rewrite them to use the connection's
        actual "{database}.{schema}." prefix.

        This is a defensive post-processing step; the primary fix is giving
        the LLM the correct prefix in the schema text via
        _get_table_prefix()/_build_schema_text().
        """
        if self.connection.db_type != DatabaseType.SNOWFLAKE:
            return sql

        table_prefix = self._get_table_prefix()
        if not table_prefix:
            return sql

        # For each known table, replace any "<anything>.<anything>.<TABLE>"
        # or bare "<TABLE>" reference with the correct fully-qualified name.
        # Match word-boundary table names, case-insensitively, optionally
        # preceded by a wrong db.schema. prefix or quoted identifiers.
        for table_name in self.schema_dict.keys():
            # Pattern matches optional "ident.ident." prefix (with optional
            # quotes) followed by the table name, as a whole identifier.
            pattern = re.compile(
                r'(?:"?[A-Za-z0-9_]+"?\.){0,2}("?' + re.escape(table_name) + r'"?)\b',
                re.IGNORECASE
            )

            def _replace(match, _table_name=table_name, _prefix=table_prefix):
                return f"{_prefix}{_table_name}"

            sql = pattern.sub(_replace, sql)

        return sql

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate generated SQL.
        
        Args:
            sql: Generated SQL string
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Convert schema dict to validation format
        validation_schema = {k: set(v.get("column_list", [])) for k, v in self.schema_dict.items()}
        return validate_sql(sql, validation_schema)
    
    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query.
        
        Args:
            sql: SQL query string
            
        Returns:
            Dictionary with execution results
        """
        return self.connection.execute(sql)
    
    def summarize_result(self, question: str, sql: str, result: Dict[str, Any]) -> str:
        """
        Summarize query results.
        
        Args:
            question: Original user question
            sql: Executed SQL
            result: Query execution result
            
        Returns:
            Summary string
        """
        if not result.get("success"):
            return "Unable to summarize due to execution error."
        
        # Prepare sample data (first few rows as JSON)
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        
        sample_data = []
        for i, row in enumerate(rows[:10]):
            row_dict = {col: str(val)[:50] for col, val in zip(columns, row)}
            sample_data.append(row_dict)
        
        sample_json = json.dumps(sample_data, indent=2, default=str)
        
        prompt = ChatPromptTemplate.from_template(RESULT_SUMMARY_PROMPT)
        messages = prompt.format_messages(
            question=question,
            sql=sql,
            row_count=result.get("row_count", 0),
            columns=", ".join(columns),
            sample_data=sample_json
        )
        
        try:
            response = self.llm.invoke(messages)
            return self._extract_response(response)
        except Exception as e:
            return f"Query returned {result.get('row_count', 0)} rows. (Summary generation failed: {str(e)})"
    
    def summarize_error(self, question: str, sql: str, error: str) -> str:
        """
        Summarize execution error.
        
        Args:
            question: Original user question
            sql: Generated SQL
            error: Error message
            
        Returns:
            Error summary string
        """
        prompt = ChatPromptTemplate.from_template(ERROR_SUMMARY_PROMPT)
        messages = prompt.format_messages(
            question=question,
            sql=sql,
            error=error
        )
        
        try:
            response = self.llm.invoke(messages)
            return self._extract_response(response)
        except Exception:
            return f"Error executing query: {error}"
    
    def run(self, question: str, auto_execute: bool = True) -> Dict[str, Any]:
        """
        Run the full text-to-SQL pipeline.
        
        Args:
            question: User's natural language question
            auto_execute: Whether to automatically execute the generated SQL
            
        Returns:
            Dictionary with full results
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Step 1: Screen input
        is_safe, screen_msg = self.screen_input(question)
        if not is_safe:
            return {
                "success": False,
                "run_id": run_id,
                "question": question,
                "sql": None,
                "error": f"Input validation failed: {screen_msg}",
                "summary": None,
                "execution_result": None
            }
        
        # Step 2: Generate SQL
        generation = self.generate_sql(question)
        
        if not generation.get("success"):
            return {
                "success": False,
                "run_id": run_id,
                "question": question,
                "sql": None,
                "error": generation.get("error", "Failed to generate SQL"),
                "summary": None,
                "execution_result": None
            }
        
        sql = generation["sql"]
        
        # Step 3: Validate SQL
        is_valid, validation_msg = self.validate(sql)
        
        # Step 4: Execute SQL (if approved and valid)
        execution_result = None
        execution_summary = None
        execution_status = "NOT_EXECUTED"
        row_count = 0
        exec_latency = 0.0
        error_message = None
        
        if auto_execute and is_valid:
            exec_start = time.time()
            execution_result = self.execute(sql)
            exec_latency = round(time.time() - exec_start, 2)
            
            if execution_result.get("success"):
                execution_status = "SUCCESS"
                row_count = execution_result.get("row_count", 0)
                execution_summary = self.summarize_result(question, sql, execution_result)
            else:
                execution_status = "FAILED"
                error_message = execution_result.get("error", "Unknown error")
                execution_summary = self.summarize_error(question, sql, error_message)
        elif not is_valid:
            execution_status = "VALIDATION_FAILED"
            error_message = validation_msg
            execution_summary = f"SQL validation failed: {validation_msg}"
        
        # Step 5: Log to metadata
        total_time = round(time.time() - start_time, 2)
        
        try:
            metadata_logger = PostgresMetadataLogger()
            metadata_logger.insert_run({
                "run_id": run_id,
                "user_question": question,
                "generated_sql": sql,
                "validation_status": "VALID" if is_valid else "INVALID",
                "execution_approved": auto_execute,
                "execution_status": execution_status,
                "row_count": row_count,
                "model_name": MODEL_NAME,
                "prompt_tokens": generation.get("prompt_tokens", 0),
                "completion_tokens": generation.get("completion_tokens", 0),
                "total_tokens": generation.get("total_tokens", 0),
                "llm_latency_seconds": generation.get("llm_latency", 0),
                "execution_latency_seconds": exec_latency if auto_execute else 0,
                "response_summary": execution_summary,
                "error_message": error_message
            })
        except Exception as e:
            print(f"Warning: Could not log metadata: {e}")
        
        # Return final result
        return {
            "success": execution_status in ["SUCCESS", "NOT_EXECUTED"],
            "run_id": run_id,
            "question": question,
            "sql": sql,
            "validation_status": "VALID" if is_valid else "INVALID",
            "execution_status": execution_status,
            "execution_result": execution_result,
            "summary": execution_summary,
            "row_count": row_count,
            "llm_latency": generation.get("llm_latency", 0),
            "execution_latency": exec_latency if auto_execute else 0,
            "total_time": total_time,
            "error": error_message
        }
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get current schema information.
        
        Returns:
            Dictionary with schema details
        """
        return {
            "connection_id": self.connection.connection_id,
            "connection_name": self.connection.name,
            "db_type": self.connection.db_type.value,
            "tables": list(self.schema_dict.keys()),
            "schema_text_length": len(self.schema_text),
            "column_count": sum(len(v.get("column_list", [])) for v in self.schema_dict.values())
        }
    
    def refresh_schema(self):
        """Refresh the schema from the database."""
        self.schema_dict = self.connection.get_all_schemas()
        if self.tables:
            self.schema_dict = {k: v for k, v in self.schema_dict.items() if k in self.tables}
        self.schema_text = self._build_schema_text()


# Convenience function for direct usage
def ask(
    question: str, 
    connection: Optional[DatabaseConnection] = None,
    tables: Optional[List[str]] = None, 
    auto_execute: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to ask a question and get results.
    
    Args:
        question: Natural language question
        connection: DatabaseConnection instance (uses default if None)
        tables: Optional list of tables to use
        auto_execute: Whether to execute the generated SQL
        
    Returns:
        Dictionary with results
    """
    if not connection:
        from .connection_manager import get_connection_manager
        manager = get_connection_manager()
        connection = manager.get_default_connection()
        if not connection:
            raise ValueError("No default connection available. Please create a connection first.")
    
    agent = Text2SQLAgent(connection, tables=tables)
    return agent.run(question, auto_execute=auto_execute)


if __name__ == "__main__":
    print("=" * 60)
    print("Text-to-SQL Agent Test")
    print("=" * 60)
    
    from .connection_manager import get_connection_manager
    
    # Get default connection
    manager = get_connection_manager()
    conn = manager.get_default_connection()
    
    if not conn:
        print("No default connection available.")
        print("Please create a connection first.")
        exit(1)
    
    print(f"\nUsing connection: {conn.name} ({conn.db_type.value})")
    
    # Test agent
    agent = Text2SQLAgent(conn)
    
    print("\nSchema Info:")
    info = agent.get_schema_info()
    print(f"  Tables: {info['tables']}")
    print(f"  Schema length: {info['schema_text_length']} characters")
    
    # Test questions
    test_questions = [
        "Show me all tables",
        "How many rows are in the pipeline_runs table?",
    ]
    
    for question in test_questions:
        print(f"\n{'=' * 60}")
        print(f"Question: {question}")
        print("-" * 60)
        
        result = agent.run(question)
        
        print(f"SQL: {result.get('sql', 'N/A')}")
        print(f"Validation: {result.get('validation_status', 'N/A')}")
        print(f"Execution: {result.get('execution_status', 'N/A')}")
        print(f"Rows: {result.get('row_count', 0)}")
        
        if result.get('summary'):
            print(f"\nSummary: {result['summary']}")
        
        if result.get('error'):
            print(f"Error: {result['error']}")
    
    print("\n" + "=" * 60)
    print("Test complete!")