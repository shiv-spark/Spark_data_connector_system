# Multi-Database Text-to-SQL Integration

## Overview

The Text-to-SQL agent has been enhanced to support **multiple database types** and **dynamic database connections**. Users can now:

1. **Connect to any database** (PostgreSQL, MySQL, SQLite, Snowflake)
2. **Switch between connections** dynamically
3. **Manage multiple connections** from the UI
4. **Query across different databases** without changing code

## Backend Changes

### New File: `connection_manager.py`

This is the core component for multi-database support:

```python
# Supported database types
class DatabaseType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    SNOWFLAKE = "snowflake"

# Key features:
# - Generic DatabaseConnection class
# - ConnectionManager for multiple connections
# - Automatic connection pooling
# - Persistent storage in ~/.text2sql/connections.json
```

### Updated: `router.py`

New endpoints added for connection management:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/text2sql/connections` | GET | List all connections |
| `/text2sql/connections` | POST | Create new connection |
| `/text2sql/connections/{id}` | GET | Get connection details |
| `/text2sql/connections/{id}` | DELETE | Delete connection |
| `/text2sql/connections/{id}/test` | POST | Test connection |

All existing endpoints now support `connection_id` parameter:
- `/text2sql/ask?connection_id=xxx`
- `/text2sql/schema?connection_id=xxx`
- `/text2sql/tables?connection_id=xxx`

### Updated: `agent.py`

- Now accepts a `DatabaseConnection` parameter
- Database-specific SQL generation prompts
- Automatic dialect detection
- Schema extraction from any database

## Frontend Changes

### New Component: `ConnectionManager.tsx`

A complete UI for managing database connections:

**Features:**
- ➕ Add new connections (PostgreSQL, MySQL, SQLite, Snowflake)
- 🗑️ Delete connections
- ✅ Test connections
- 📋 View connection details
- 🔒 Passwords masked in UI

**UI Preview:**
```
┌─────────────────────────────────────────────────────┐
│ Database Connections                    [Add +]    │
├─────────────────────────────────────────────────────┤
│ 🐘 Production DB     PostgreSQL              [v]   │
│   Host: localhost                                   │
│   Port: 5432                                        │
│   Database: airflow                                 │
│   User: airflow                                     │
│   Password: ********                                │
│   [Test] [Delete]                                   │
├─────────────────────────────────────────────────────┤
│ 🐬 Analytics DB      MySQL                      [v]  │
│ 🗄️ Local Cache      SQLite                    [v]  │
│ ❄️ Snowflake DW     Snowflake                 [v]  │
└─────────────────────────────────────────────────────┘
```

### Updated: `Text2SQL.tsx`

Now includes:
- Connection selector dropdown
- Per-connection schema display
- Connection-specific query history

### New API Functions: `api.ts`

```typescript
fetchText2SQLConnections()     // GET /text2sql/connections
createText2SQLConnection()     // POST /text2sql/connections
deleteText2SQLConnection()    // DELETE /text2sql/connections/:id
testText2SQLConnection()      // POST /text2sql/connections/:id/test
```

### New UI Components

- `dialog.tsx` - Modal dialogs for forms
- `select.tsx` - Dropdown selects
- `tabs.tsx` - Tabbed interfaces

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           ConnectionManager.tsx                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │  │
│  │  │PostgreSQL│ │  MySQL   │ │ Snowflake│            │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘            │  │
│  └───────┼────────────┼────────────┼──────────────────┘  │
└──────────┼────────────┼────────────┼──────────────────────┘
           │            │            │
           │ HTTP/API   │            │
           ▼            ▼            ▼
┌────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           router.py (Connection Endpoints)       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │  │
│  │  │ POST /   │ │ GET /    │ │ DELETE / │          │  │
│  │  │connections│ │connections│ │:id/test │          │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘          │  │
│  └───────┼────────────┼────────────┼──────────────────┘  │
│          │            │            │                       │
│          ▼            ▼            ▼                       │
│  ┌──────────────────────────────────────────────────┐    │
│  │        connection_manager.py                     │    │
│  │  ┌──────────────────────────────────────────┐   │    │
│  │  │         ConnectionManager                │   │    │
│  │  │  - connections: Dict[str, Connection]   │   │    │
│  │  │  - add_connection()                    │   │    │
│  │  │  - remove_connection()                   │   │    │
│  │  │  - get_connection()                      │   │    │
│  │  └──────────────────────────────────────────┘   │    │
│  │                                                   │    │
│  │  ┌──────────────────────────────────────────┐   │    │
│  │  │       DatabaseConnection                 │   │    │
│  │  │  - connect()                             │   │    │
│  │  │  - execute()                             │   │    │
│  │  │  - get_tables()                          │   │    │
│  │  │  - get_table_schema()                    │   │    │
│  │  └──────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │  PostgreSQL  │ │    MySQL     │ │   Snowflake  │
  │  (psycopg2)  │ │  (pymysql)   │ │ (snowflake)  │
  └──────────────┘ └──────────────┘ └──────────────┘
```

## Usage Examples

### Create a Connection (API)

```bash
# PostgreSQL
curl -X POST http://localhost:8000/text2sql/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production DB",
    "db_type": "postgresql",
    "config": {
      "host": "db.example.com",
      "port": 5432,
      "database": "analytics",
      "user": "analyst",
      "password": "secret123"
    }
  }'

# MySQL
curl -X POST http://localhost:8000/text2sql/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analytics MySQL",
    "db_type": "mysql",
    "config": {
      "host": "mysql.example.com",
      "port": 3306,
      "database": "reports",
      "user": "reader",
      "password": "secret123"
    }
  }'

# Snowflake
curl -X POST http://localhost:8000/text2sql/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Snowflake DW",
    "db_type": "snowflake",
    "config": {
      "account": "xyz12345",
      "warehouse": "COMPUTE_WH",
      "database": "PROD",
      "schema": "PUBLIC",
      "user": "data_analyst",
      "password": "secret123"
    }
  }'

# SQLite
curl -X POST http://localhost:8000/text2sql/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local Cache",
    "db_type": "sqlite",
    "config": {
      "database_path": "/path/to/database.db"
    }
  }'
```

### Query a Specific Connection

```bash
# Use a specific connection
curl -X POST http://localhost:8000/text2sql/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many users signed up today?",
    "connection_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

### Python Usage

```python
from text_sql import Text2SQLAgent, ask
from text_sql.connection_manager import get_connection_manager, DatabaseType

# Get connection manager
manager = get_connection_manager()

# Create a new connection
conn_id = manager.add_connection(
    name="Production DB",
    db_type=DatabaseType.POSTGRESQL,
    config={
        "host": "db.example.com",
        "port": 5432,
        "database": "analytics",
        "user": "analyst",
        "password": "secret123"
    }
)

# Get the connection
conn = manager.get_connection(conn_id)

# Query using this connection
agent = Text2SQLAgent(connection=conn)
result = agent.run("How many users today?")

# Or use the convenience function
from text_sql import ask
result = ask("Show me all tables", connection=conn)
```

## Configuration

### Environment Variables

```env
# Default connection (if no connections exist)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=airflow
DB_USER=airflow
DB_PASSWORD=airflow

# LLM Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
```

### Persistent Storage

Connections are saved to `~/.text2sql/connections.json`:

```json
{
  "connections": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Production DB",
      "type": "postgresql",
      "config": {
        "host": "db.example.com",
        "port": 5432,
        "database": "analytics",
        "user": "analyst",
        "password": "***"
      }
    }
  ]
}
```

## Security Features

- ✅ Passwords masked in API responses
- ✅ Connections stored in user's home directory
- ✅ SQL injection prevention per database
- ✅ Read-only enforcement across all DB types
- ✅ Connection testing before saving

## Dependencies

### Backend

```python
# Already installed (via requirements.txt)
psycopg2-binary  # PostgreSQL

# Optional - install as needed
pymysql          # MySQL
snowflake-connector-python  # Snowflake
```

### Frontend

All UI components included, no additional dependencies needed.

## Migration Guide

### From Single Database

If you were using the previous single-database version:

1. **Default connection automatically created** from environment variables
2. **All existing queries continue to work** (uses default connection)
3. **New connections can be added** via UI or API

### Steps to Upgrade

1. **Update backend**:
   ```bash
   cd /home/spark/Spark_data_connector_system/backend
   pip install -r requirements.txt
   # Optional: pip install pymysql  # for MySQL
   # Optional: pip install snowflake-connector-python  # for Snowflake
   ```

2. **Restart server**:
   ```bash
   python run.py
   ```

3. **Update frontend**:
   ```bash
   cd /home/spark/Spark_data_connector_system/frontend
   npm install
   npm run dev
   ```

4. **Access new UI**:
   - Navigate to `/text2sql`
   - Click "Database Connections" in sidebar
   - Add new connections as needed

## API Endpoints Summary

### Connection Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/text2sql/connections` | List all connections |
| POST | `/text2sql/connections` | Create connection |
| GET | `/text2sql/connections/{id}` | Get connection details |
| DELETE | `/text2sql/connections/{id}` | Delete connection |
| POST | `/text2sql/connections/{id}/test` | Test connection |

### Query Operations (with optional connection_id parameter)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/text2sql/ask` | Query any database |
| POST | `/text2sql/generate` | Generate SQL |
| GET | `/text2sql/schema` | Get schema |
| GET | `/text2sql/tables` | List tables |
| POST | `/text2sql/execute` | Execute SQL |

## Troubleshooting

### "Module not found: pymysql"
```bash
pip install pymysql
```

### "Snowflake connector not found"
```bash
pip install snowflake-connector-python
```

### Connection test fails
- Check credentials
- Verify network access
- Check firewall rules
- Review database logs

### Schema not loading
- Verify connection permissions
- Check if user can read information_schema
- Test with simple query first

## Next Steps

1. **Install optional dependencies** for databases you want to use
2. **Create connections** via UI or API
3. **Test connections** to verify setup
4. **Start querying** across multiple databases

## Files Added/Modified

### Backend
- ✅ `text_sql/connection_manager.py` (new)
- ✅ `text_sql/router.py` (updated)
- ✅ `text_sql/agent.py` (updated)
- ✅ `text_sql/__init__.py` (updated)

### Frontend
- ✅ `components/ConnectionManager.tsx` (new)
- ✅ `components/ui/dialog.tsx` (new)
- ✅ `components/ui/select.tsx` (new)
- ✅ `components/ui/tabs.tsx` (new)
- ✅ `pages/Text2SQL.tsx` (updated)
- ✅ `lib/api.ts` (updated)

## Summary

✅ **Multi-database support** (PostgreSQL, MySQL, SQLite, Snowflake)
✅ **Dynamic connection switching**
✅ **Connection management UI**
✅ **Persistent storage**
✅ **Security features**
✅ **Full API support**
✅ **Backward compatible**

The Text-to-SQL agent is now a **true multi-database query tool**!
