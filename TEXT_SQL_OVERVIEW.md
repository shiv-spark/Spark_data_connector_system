# Text-to-SQL Agent Integration

## What Was Integrated

A complete **Text-to-SQL Agent** that converts natural language questions into PostgreSQL queries. This agent enables users to ask questions about their data in plain English and get answers automatically.

## Key Components

### 1. Core Agent (`backend/text_sql/agent.py`)
- Converts natural language → SQL → Results → Summary
- Uses LangChain + LLM (Groq/OpenRouter)
- Validates queries for security
- Executes against PostgreSQL
- Generates human-friendly summaries

### 2. REST API (`backend/text_sql/router.py`)
10 FastAPI endpoints for:
- **/text2sql/ask** - Full pipeline (question → SQL → execution → summary)
- **/text2sql/generate** - Generate SQL only
- **/text2sql/schema** - Get database schema
- **/text2sql/tables** - List all tables
- **/text2sql/metadata/* ** - Query statistics and history

### 3. PostgreSQL Integration
- Uses existing database connection
- Auto-discovers schema
- Supports all project tables
- Logs queries for audit

### 4. Security Features
- ✅ Only SELECT queries allowed
- ✅ Schema validation
- ✅ Input screening
- ✅ Metadata logging
- ✅ Blocks: DELETE, DROP, INSERT, UPDATE, etc.

## How It Works

```
User: "How many pipelines failed today?"

┌────────────────────────────────────────────────────────┐
│  Step 1: Input Screening                               │
│  ✓ No malicious patterns detected                      │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Step 2: SQL Generation (LLM)                          │
│  Schema: pipeline_runs, saved_connections...            │
│                                                         │
│  Generated SQL:                                        │
│  SELECT COUNT(*) FROM pipeline_runs                    │
│  WHERE status = 'failed'                              │
│  AND run_date >= CURRENT_DATE                         │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Step 3: SQL Validation                                │
│  ✓ Valid SELECT query                                 │
│  ✓ Table exists: pipeline_runs                       │
│  ✓ Columns exist: status, run_date                  │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Step 4: Execution                                     │
│  Result: 5 rows                                        │
│  Time: 0.05s                                          │
└────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────┐
│  Step 5: Summary Generation                            │
│  "5 pipeline runs failed today."                      │
└────────────────────────────────────────────────────────┘
```

## Example Usage

### Via API

```bash
# Ask a question
curl -X POST http://localhost:8000/text2sql/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many pipeline runs today?"}'

# Response
{
  "success": true,
  "sql": "SELECT COUNT(*) FROM pipeline_runs WHERE run_date >= CURRENT_DATE",
  "row_count": 42,
  "summary": "There were 42 pipeline runs today.",
  "llm_latency": 1.23,
  "execution_latency": 0.05
}
```

### Via Python

```python
from text_sql import Text2SQLAgent

agent = Text2SQLAgent()
result = agent.run("Show me top 5 pipelines by run count")

print(result['sql'])
print(result['row_count'])
print(result['summary'])
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/text2sql/ask` | POST | Full question → SQL → answer pipeline |
| `/text2sql/generate` | POST | Generate SQL only (no execution) |
| `/text2sql/schema` | GET | Get database schema |
| `/text2sql/tables` | GET | List all tables |
| `/text2sql/execute` | POST | Execute SQL directly |
| `/text2sql/metadata/stats` | GET | Query statistics |
| `/text2sql/metadata/runs` | GET | Recent runs |
| `/text2sql/health` | GET | Service health |

## Files Created

```
backend/text_sql/
├── __init__.py              # Module exports
├── config.py                # Configuration
├── agent.py                 # Main agent
├── router.py                # FastAPI endpoints
├── postgres_executor.py     # Query execution
├── postgres_schema_manager.py # Schema extraction
├── sql_validator.py         # SQL validation
├── metadata_logger.py       # Query logging
└── README.md                # Documentation

backend/
├── test_text_sql.py         # Test suite

TEXT_SQL_INTEGRATION.md      # Integration guide
INTEGRATION_SUMMARY.md       # This summary
```

## Modified Files

- `backend/main.py` - Added Text-to-SQL router
- `backend/requirements.txt` - Added langchain dependencies

## Setup Instructions

### 1. Install Dependencies

```bash
cd /home/spark/Spark_data_connector_system/backend
pip install -r requirements.txt
```

### 2. Configure API Keys

Add to `.env`:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Start Server

```bash
python run.py
```

### 4. Test

```bash
curl http://localhost:8000/text2sql/health
```

## Security

The agent is **read-only** and **secure**:
- Only SELECT queries allowed
- Blocks all DDL/DML (CREATE, DROP, INSERT, etc.)
- Validates against known schema
- Screens for malicious patterns
- Logs all queries for audit

## Integration with Existing System

The Text-to-SQL agent:
- ✅ Uses existing PostgreSQL connection
- ✅ Integrates with FastAPI
- ✅ Follows existing code patterns
- ✅ Works with Docker deployment
- ✅ Graceful dependency handling

## Documentation

- **Integration Guide**: `TEXT_SQL_INTEGRATION.md`
- **Module Docs**: `backend/text_sql/README.md`
- **Test Suite**: `backend/test_text_sql.py`

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Add API key to `.env`
3. Start the server: `python run.py`
4. Test the endpoints
5. Integrate with React frontend
