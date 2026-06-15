# Text-to-SQL Agent Integration Guide

## Overview

The Text-to-SQL Agent has been successfully integrated into the Spark Data Connector System. This agent allows users to ask natural language questions about their data, and automatically generates and executes PostgreSQL queries.

## What Was Created

### New Module: `backend/text_sql/`

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports and version |
| `config.py` | Configuration (DB, LLM, security settings) |
| `agent.py` | Main Text2SQLAgent class |
| `router.py` | FastAPI REST API endpoints |
| `postgres_executor.py` | PostgreSQL query execution |
| `postgres_schema_manager.py` | Schema extraction and management |
| `sql_validator.py` | SQL safety validation |
| `metadata_logger.py` | Query logging and metadata |
| `README.md` | Module documentation |

## Installation

### 1. Install Dependencies

```bash
cd /home/spark/Spark_data_connector_system/backend
pip install -r requirements.txt
```

The following packages were added:
- `langchain>=0.1.0`
- `langchain-groq>=0.1.0` (for Groq LLM)
- `langchain-openai>=0.1.0` (for OpenRouter compatibility)
- `sqlglot>=23.0.0` (for SQL parsing)

### 2. Configure Environment Variables

Add to your `.env` file:

```env
# LLM Provider Configuration
LLM_PROVIDER=groq  # or openrouter

# Groq (default)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# OpenRouter (optional)
# OPENROUTER_API_KEY=your_openrouter_key_here
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# Text-to-SQL Settings
TEXT_SQL_MAX_RETRIES=2
TEXT_SQL_TEMPERATURE=0.0
```

### 3. Test the Integration

```bash
cd /home/spark/Spark_data_connector_system/backend
python test_text_sql.py
```

## API Endpoints

The Text-to-SQL agent adds these endpoints to the FastAPI server:

### Core Endpoints

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/text2sql/ask` | POST | Full pipeline: question → SQL → execution → summary | `{"question": "How many pipelines today?"}` |
| `/text2sql/generate` | POST | Generate SQL only (no execution) | `{"question": "Show failed runs"}` |
| `/text2sql/schema` | GET | Get database schema | Query param: `?tables=table1,table2` |
| `/text2sql/tables` | GET | List all tables | - |
| `/text2sql/schema/{table}` | GET | Get specific table schema | - |
| `/text2sql/execute` | POST | Execute SQL directly | `{"sql": "SELECT * FROM users"}` |

### Metadata Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/text2sql/metadata/stats` | GET | Query statistics |
| `/text2sql/metadata/runs` | GET | Recent query runs |
| `/text2sql/metadata/runs/{id}` | GET | Specific run details |
| `/text2sql/health` | GET | Service health check |

## Usage Examples

### Example 1: Ask a Question

```bash
curl -X POST http://localhost:8000/text2sql/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many pipeline runs were successful today?",
    "auto_execute": true
  }'
```

Response:
```json
{
  "success": true,
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "How many pipeline runs were successful today?",
  "sql": "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'success' AND run_date >= CURRENT_DATE",
  "validation_status": "VALID",
  "execution_status": "SUCCESS",
  "row_count": 1,
  "execution_result": {...},
  "summary": "There were 42 successful pipeline runs today.",
  "llm_latency": 1.23,
  "execution_latency": 0.05,
  "total_time": 1.28
}
```

### Example 2: Generate SQL Only

```bash
curl -X POST http://localhost:8000/text2sql/generate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the top 5 pipelines by average duration"
  }'
```

Response:
```json
{
  "success": true,
  "sql": "SELECT pipeline_name, AVG(duration) as avg_duration FROM pipeline_runs GROUP BY pipeline_name ORDER BY avg_duration DESC LIMIT 5",
  "is_valid": true,
  "prompt_tokens": 512,
  "completion_tokens": 89,
  "total_tokens": 601,
  "llm_latency": 1.45
}
```

### Example 3: Python Usage

```python
from text_sql import Text2SQLAgent, ask

# Method 1: Using the agent class
agent = Text2SQLAgent()
result = agent.run("Show me all failed pipeline runs from today")

print(f"SQL: {result['sql']}")
print(f"Rows: {result['row_count']}")
print(f"Summary: {result['summary']}")

# Method 2: Using the convenience function
result = ask("What tables are in the database?")
```

## Security Features

The Text-to-SQL agent includes multiple security layers:

1. **Input Screening**
   - Blocks malicious patterns (DELETE, DROP, etc.)
   - Prevents prompt injection attempts
   - Screens for suspicious keywords

2. **SQL Validation**
   - Only allows SELECT statements
   - Validates against known schema
   - Checks for forbidden operations

3. **Read-Only Enforcement**
   - CREATE, DROP, ALTER, INSERT, UPDATE, DELETE are blocked
   - System table access is restricted
   - Comments are stripped from queries

4. **Metadata Logging**
   - All queries are logged for audit
   - Tracks success/failure rates
   - Records token usage and latency

## Schema Management

The agent automatically discovers the database schema:

```python
from text_sql import PostgresSchemaManager

manager = PostgresSchemaManager()

# Get all tables
tables = manager.executor.get_tables()

# Get schema for specific tables
schema_text, schema_dict = manager.build_schema_text(['pipeline_runs', 'saved_connections'])

# Get schema with sample data (better for LLM context)
schema_text, schema_dict = manager.get_schema_with_samples()
```

## Configuration

### LLM Provider

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
```

## Integration with Frontend

To use the Text-to-SQL agent from the React frontend:

```typescript
// Example React component
const askQuestion = async (question: string) => {
  const response = await fetch('http://localhost:8000/text2sql/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, auto_execute: true })
  });
  
  const result = await response.json();
  return result;
};
```

## Troubleshooting

### Common Issues

1. **"Module not found" errors**
   ```bash
   pip install -r requirements.txt
   ```

2. **"Failed to generate SQL"**
   - Check LLM API key is set correctly
   - Verify database connection settings
   - Check LLM provider status

3. **"Validation failed"**
   - Schema may be out of date: `agent.refresh_schema()`
   - Query may reference non-existent tables/columns

4. **"Execution failed"**
   - Check PostgreSQL connection settings
   - Verify table permissions
   - Check query syntax

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Text-to-SQL Router                    │    │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────────────┐  │    │
│  │  │ /ask    │  │ /generate│  │ /schema         │  │    │
│  │  │ /health │  │ /execute │  │ /metadata/*     │  │    │
│  │  └────┬────┘  └────┬─────┘  └────────┬────────┘  │    │
│  │       │            │               │            │    │
│  │       └────────────┴───────┬───────┘            │    │
│  │                            ▼                    │    │
│  │                   ┌──────────────────┐         │    │
│  │                   │ Text2SQLAgent    │         │    │
│  │                   │ ┌──────────────┐ │         │    │
│  │                   │ │Schema Manager│ │         │    │
│  │                   │ │SQL Validator │ │         │    │
│  │                   │ │Query Executor│ │         │    │
│  │                   │ │Metadata Logger│ │         │    │
│  │                   │ └──────┬───────┘ │         │    │
│  │                   └────────┼──────────┘         │    │
│  │                            │                     │    │
│  └────────────────────────────┼─────────────────────┘    │
│                               ▼                          │
│                    ┌───────────────────┐                 │
│                    │   LLM Provider    │                 │
│                    │ (Groq/OpenRouter) │                 │
│                    └───────────────────┘                 │
│                               │                          │
│                               ▼                          │
│                    ┌───────────────────┐                 │
│                    │    PostgreSQL     │                 │
│                    │  (Data + Metadata)│                 │
│                    └───────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Start the server**:
   ```bash
   cd /home/spark/Spark_data_connector_system/backend
   python run.py
   ```

2. **Test the integration**:
   ```bash
   python test_text_sql.py
   ```

3. **Try the API**:
   ```bash
   curl http://localhost:8000/text2sql/health
   curl http://localhost:8000/text2sql/tables
   ```

## Support

For issues or questions:
1. Check the module README: `backend/text_sql/README.md`
2. Review the test script: `backend/test_text_sql.py`
3. Check the logs for detailed error messages
