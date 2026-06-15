# Text-to-SQL Agent Module for PostgreSQL

A natural language to SQL conversion agent integrated with the Spark Data Connector System.

## Overview

This module provides:

1. **Text-to-SQL Generation**: Convert natural language questions into PostgreSQL queries
2. **SQL Validation**: Ensure generated queries are safe (SELECT only) and valid
3. **Query Execution**: Execute validated queries against PostgreSQL
4. **Result Summarization**: Generate human-friendly summaries of query results
5. **Metadata Logging**: Track all queries for auditing and analysis
6. **REST API**: FastAPI endpoints for integration

## Architecture

```
text_sql/
├── __init__.py              # Module exports
├── config.py                # Configuration (DB, LLM, security)
├── agent.py                 # Main Text2SQLAgent class
├── router.py                # FastAPI endpoints
├── postgres_executor.py     # PostgreSQL query execution
├── postgres_schema_manager.py # Schema extraction
├── sql_validator.py         # SQL safety validation
└── metadata_logger.py       # Query logging
```

## Integration

### 1. Add to requirements.txt

Add these dependencies to `backend/requirements.txt`:

```
# Already in project:
# psycopg2-binary
# python-dotenv

# Text-to-SQL specific:
langchain>=0.1.0
langchain-groq>=0.1.0
langchain-openai>=0.1.0
sqlglot>=23.0.0
```

### 2. Install Dependencies

```bash
cd /home/spark/Spark_data_connector_system/backend
pip install -r requirements.txt
```

### 3. Environment Variables

Add to your `.env` file:

```env
# LLM Configuration
LLM_PROVIDER=groq  # or openrouter
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Optional: OpenRouter
# OPENROUTER_API_KEY=your_openrouter_key
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# Text-to-SQL Settings
TEXT_SQL_MAX_RETRIES=2
TEXT_SQL_TEMPERATURE=0.0
```

### 4. Database Setup

The metadata table will be created automatically on first use:
- `text2sql_run_metadata`: Stores all query executions

## Usage

### Python API

```python
from text_sql.agent import Text2SQLAgent, ask

# Method 1: Using the agent class
agent = Text2SQLAgent()
result = agent.run("Show me the top 5 pipelines by run count")

print(result["sql"])           # Generated SQL
print(result["row_count"])     # Number of rows returned
print(result["summary"])       # Human-friendly summary

# Method 2: Using the convenience function
result = ask("What tables are in the database?")
```

### REST API

```bash
# Ask a question
curl -X POST http://localhost:8000/text2sql/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many pipelines were run today?",
    "auto_execute": true
  }'

# Generate SQL only (no execution)
curl -X POST http://localhost:8000/text2sql/generate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me all failed pipeline runs"
  }'

# Get schema info
curl http://localhost:8000/text2sql/schema

# List tables
curl http://localhost:8000/text2sql/tables

# Get table details
curl http://localhost:8000/text2sql/schema/pipeline_runs

# Get recent runs
curl http://localhost:8000/text2sql/metadata/runs

# Get stats
curl http://localhost:8000/text2sql/metadata/stats

# Health check
curl http://localhost:8000/text2sql/health
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/text2sql/ask` | POST | Full text-to-SQL pipeline |
| `/text2sql/generate` | POST | Generate SQL only |
| `/text2sql/schema` | GET | Get schema info |
| `/text2sql/schema/{table}` | GET | Get table schema |
| `/text2sql/tables` | GET | List all tables |
| `/text2sql/execute` | POST | Execute SQL directly |
| `/text2sql/metadata/stats` | GET | Query statistics |
| `/text2sql/metadata/runs` | GET | Recent runs |
| `/text2sql/metadata/runs/{id}` | GET | Run details |
| `/text2sql/health` | GET | Health check |

## Security Features

1. **Input Screening**: Blocks malicious patterns (DROP, DELETE, etc.)
2. **SQL Validation**: Only allows SELECT statements
3. **Schema Validation**: Ensures queries reference existing tables/columns
4. **Query Logging**: All queries logged with metadata
5. **No DDL/DML**: CREATE, DROP, INSERT, UPDATE, DELETE are forbidden

## Configuration Options

### LLM Providers

**Groq (default)**:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

**OpenRouter**:
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

### Advanced Settings

```env
# Number of retries for SQL generation
TEXT_SQL_MAX_RETRIES=2

# LLM temperature (0.0 = deterministic, 1.0 = creative)
TEXT_SQL_TEMPERATURE=0.0

# Include sample data in schema (better SQL generation)
INCLUDE_SAMPLES=true
```

## Examples

### Example 1: Simple Query
```python
result = agent.run("How many pipeline runs are there?")
# SQL: SELECT COUNT(*) FROM pipeline_runs
```

### Example 2: Filtered Query
```python
result = agent.run("Show me failed pipeline runs from today")
# SQL: SELECT * FROM pipeline_runs 
#      WHERE status = 'failed' 
#      AND run_date >= CURRENT_DATE
```

### Example 3: Aggregation
```python
result = agent.run("What is the average execution time by connector type?")
# SQL: SELECT connector_type, AVG(duration) 
#      FROM pipeline_runs 
#      GROUP BY connector_type
```

### Example 4: Join Query
```python
result = agent.run("Show pipeline runs with their connection names")
# SQL: SELECT pr.*, sc.name AS connection_name
#      FROM pipeline_runs pr
#      JOIN saved_connections sc ON pr.connection_id = sc.id
```

## Testing

Run the test suite:

```bash
cd /home/spark/Spark_data_connector_system/backend
python -m text_sql.agent
python -m text_sql.sql_validator
python -m text_sql.postgres_executor
python -m text_sql.postgres_schema_manager
python -m text_sql.metadata_logger
```

## Troubleshooting

### Common Issues

1. **"Failed to generate SQL"**
   - Check LLM API key is set correctly
   - Verify database connection
   - Check schema is accessible

2. **"Validation failed"**
   - Query may reference non-existent tables/columns
   - Check schema is up to date: `agent.refresh_schema()`

3. **"Execution failed"**
   - Check PostgreSQL connection settings
   - Verify table permissions
   - Check for syntax errors in generated SQL

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

Part of the Spark Data Connector System project.
