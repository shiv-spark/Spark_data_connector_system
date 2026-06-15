# Snowflake Support in Text-to-SQL

## Overview
Snowflake is fully supported in the text-to-SQL module. Users can create Snowflake connections and use them to:
- Query Snowflake databases using natural language
- Explore Snowflake tables and schemas
- Execute SQL queries on Snowflake warehouses

## API Endpoints

### Create Snowflake Connection
```http
POST /text2sql/connections
Content-Type: application/json

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

### Test Connection
```http
POST /text2sql/connections/{connection_id}/test
```

### List Tables
```http
GET /text2sql/tables?connection_id={connection_id}
```

### Get Schema
```http
GET /text2sql/schema?connection_id={connection_id}
```

### Ask Question (Text-to-SQL)
```http
POST /text2sql/ask
Content-Type: application/json

{
  "question": "Show me the top 10 customers by revenue",
  "connection_id": "snowflake-connection-id",
  "auto_execute": true
}
```

## Snowflake Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| account | Yes | Snowflake account identifier (e.g., "xy12345.us-east-1") |
| user | Yes | Snowflake username |
| password | Yes | Snowflake password |
| warehouse | Yes | Warehouse name (e.g., "COMPUTE_WH") |
| database | Yes | Database name |
| schema | No | Schema name (default: "PUBLIC") |
| role | No | Role to use (e.g., "ACCOUNTADMIN") |

## Supported Features

### ✅ Supported
- ✅ Create and manage Snowflake connections
- ✅ List Snowflake tables
- ✅ Get Snowflake table schemas
- ✅ Generate Snowflake SQL from natural language
- ✅ Execute queries on Snowflake
- ✅ Result summarization
- ✅ Metadata logging

### Database Types Supported
The text-to-sql module supports these database types:
- `postgresql`
- `mysql`
- `sqlite`
- `snowflake`

## Frontend Integration

The frontend already supports Snowflake connections:

```typescript
import { createText2SQLConnection } from "@/lib/api";

const createSnowflakeConnection = async () => {
  const response = await createText2SQLConnection({
    name: "Snowflake Production",
    db_type: "snowflake",
    config: {
      account: "xy12345.us-east-1",
      user: "myuser",
      password: "mypassword",
      warehouse: "COMPUTE_WH",
      database: "PRODUCTION",
      schema: "PUBLIC"
    }
  });
  return response;
};
```

## Snowflake-Specific SQL Generation

The text-to-SQL agent uses Snowflake-specific SQL prompts that include:
- Fully qualified table names: `database.schema.table`
- Snowflake-specific functions: `DATE_TRUNC`, `DATEDIFF`, etc.
- Type casting syntax: `column::DATE`
- Proper date part syntax: `DATEDIFF(day, start, end)`

## Connection Storage

Snowflake connections are stored in `~/.text2sql/connections.json` alongside other database connections.

## Testing

To test a Snowflake connection:

```bash
curl -X POST http://localhost:8000/text2sql/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Snowflake",
    "db_type": "snowflake",
    "config": {
      "account": "your_account.region",
      "user": "your_user",
      "password": "your_password",
      "warehouse": "your_warehouse",
      "database": "your_database",
      "schema": "PUBLIC"
    }
  }'
```

Then test it:
```bash
curl -X POST http://localhost:8000/text2sql/connections/{connection_id}/test
```

## Requirements

The Snowflake connector requires:
```bash
pip install snowflake-connector-python
```

This is already included in `backend/requirements.txt`.

## Troubleshooting

### "snowflake-connector-python not installed"
Install the required package:
```bash
pip install snowflake-connector-python
```

### "Connection failed"
- Verify account format: `xy12345.region` or `xy12345.region.cloud`
- Check warehouse is running
- Verify user has access to database and schema
- Check role permissions

### "No tables found"
- Verify schema name (case-sensitive in Snowflake)
- Check database and schema exist
- Verify user has SELECT privileges

## Examples

### Basic Query
```json
{
  "question": "How many rows in the customers table?"
}
```
Generated SQL:
```sql
SELECT COUNT(*) FROM MY_DB.PUBLIC.CUSTOMERS
```

### Filtered Query
```json
{
  "question": "Show me sales from last month"
}
```
Generated SQL:
```sql
SELECT * FROM MY_DB.PUBLIC.SALES 
WHERE DATE_TRUNC('month', sale_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
```

### Aggregation
```json
{
  "question": "What is the average order value by region?"
}
```
Generated SQL:
```sql
SELECT region, AVG(order_value) 
FROM MY_DB.PUBLIC.ORDERS 
GROUP BY region
```

## Security Notes

- Passwords are stored in `~/.text2sql/connections.json` in plain text (for now)
- Use environment variables for sensitive credentials in production
- Consider using key-pair authentication for better security
- All queries are logged to the metadata table
