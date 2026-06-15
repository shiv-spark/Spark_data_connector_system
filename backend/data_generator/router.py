"""
Data Generator Router

API endpoints for synthetic data generation with multi-database support.
Uses saved connections from the database (like Text-to-SQL).
"""

import os
import sys
import json
import re
import uuid
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import random
import string

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import pandas as pd

# Create router
router = APIRouter(prefix="/datagen", tags=["Data Generator"])

# Constants
MAX_ROWS = 1000

# Determine paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
AGENT_DIR = PROJECT_ROOT / "AGENT"
GENERATED_DIR = AGENT_DIR / "generator" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

print(f"[datagen] AGENT_DIR: {AGENT_DIR}")
print(f"[datagen] GENERATED_DIR: {GENERATED_DIR}")

# Add paths to sys.path
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Import connection manager from text_sql
CONNECTION_MANAGER_AVAILABLE = False
DatabaseConnection = None
DatabaseType = None
ConnectionManager = None

# Get DB config from environment (same as main.py)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "airflow"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port": os.getenv("DB_PORT", "5432")
}

def _get_db_conn():
    """Get a connection to the PostgreSQL database."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)

def _rows_to_dicts(cursor):
    """Convert psycopg2 cursor result to list of dictionaries"""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# Connection management functions using data connector's saved_connections
def get_saved_connections():
    """Get all saved connections from the data connector."""
    conn = _get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, source_type, config, status, created_at, updated_at
        FROM saved_connections
        WHERE source_type IN ('postgres', 'snowflake')
        ORDER BY updated_at DESC, id DESC
    """)
    rows = _rows_to_dicts(cur)
    cur.close()
    conn.close()
    return rows

def get_saved_connection(connection_id: int):
    """Get a specific saved connection by ID."""
    conn = _get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, source_type, config, status, created_at, updated_at
        FROM saved_connections WHERE id = %s
    """, (connection_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))

try:
    text_sql_path = str(PROJECT_ROOT / "backend" / "text_sql")
    sys.path.insert(0, text_sql_path)
    from text_sql.connection_manager import (
        get_connection_manager as _get_connection_manager,
        DatabaseConnection,
        DatabaseType,
        ConnectionManager
    )
    CONNECTION_MANAGER_AVAILABLE = True
    print("✓ Connection manager imported successfully")
    
    def get_connection_manager():
        """Get connection manager for database operations."""
        return _get_connection_manager()
except ImportError as e:
    print(f"Warning: Connection manager not available: {e}")
    CONNECTION_MANAGER_AVAILABLE = False
    
    def get_connection_manager():
        """Dummy connection manager when not available."""
        return None


# =============================================================================
# Simple Data Generator Implementation (no external dependencies)
# =============================================================================

def _parse_with_llm(description: str, connection_id: str = None) -> dict:
    """
    Use LLM to parse the description and generate appropriate config.
    If connection_id provided, uses live database schema.
    If table doesn't exist, LLM will suggest schema and create it.
    """
    from groq import Groq
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Build schema info from connection if available
    schema_info = ""
    available_tables = []
    
    if connection_id:
        try:
            conn = get_connection(connection_id)
            available_tables = list_connection_tables(conn)
            schema_info = f"\n\nAvailable tables in database: {available_tables}"
        except Exception as e:
            print(f"[datagen] Error getting schema info: {e}")
    
    system_prompt = f"""You are a data generation assistant. 
Parse the user's request and return ONLY valid JSON.

IMPORTANT: The user wants to generate data. Analyze what entity they're referring to and create an appropriate table schema.

The JSON should have these fields:
- "table": table name (uppercase, e.g., CUSTOMERS, SUPPORT_TICKETS, PRODUCTS)
- "rows": number of rows (integer, max 1000)
- "locale": Faker locale (e.g., "en_US", "en_IN")  
- "columns": list of column names appropriate for the entity
- "hints": dict of column -> description for data generation
- "create_table": (required if table doesn't exist) SQL CREATE TABLE statement

{schema_info}

Entity mapping examples:
- "customer" → CUSTOMERS table with ID, NAME, EMAIL, PHONE, ADDRESS, CITY, COUNTRY
- "support ticket" → SUPPORT_TICKETS with TICKET_ID, CUSTOMER_NAME, ISSUE, STATUS, PRIORITY, CREATED_DATE
- "product" → PRODUCTS with PRODUCT_ID, NAME, DESCRIPTION, PRICE, CATEGORY, STOCK
- "employee" → EMPLOYEES with EMP_ID, NAME, DEPARTMENT, SALARY, HIRE_DATE
- "order" → ORDERS with ORDER_ID, CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT, STATUS

If the table doesn't exist in the database:
1. Determine appropriate table name from the entity
2. Create suitable columns based on what makes sense for that entity
3. Include the "create_table" DDL

Rules:
- Return ONLY valid JSON, no explanation, no markdown, no code fences
- If table exists in the list above, use its exact column names
- If creating new table, use appropriate data types (INTEGER for IDs, VARCHAR for text, DATE for dates, DECIMAL for money)
- Always extract the row count from the prompt (e.g., "50 tickets" = 50 rows)
- Max 1000 rows

Example for new table:
{{"table": "SUPPORT_TICKETS", "rows": 50, "locale": "en_US", "columns": ["TICKET_ID", "CUSTOMER_NAME", "ISSUE", "STATUS", "PRIORITY", "CREATED_DATE"], "hints": {{"TICKET_ID": "unique sequential integer starting from 1", "CUSTOMER_NAME": "customer full name", "ISSUE": "description of the support issue", "STATUS": "open, in_progress, resolved, closed", "PRIORITY": "low, medium, high, critical", "CREATED_DATE": "recent date within last 30 days"}}, "create_table": "CREATE OR REPLACE TABLE SUPPORT_TICKETS (TICKET_ID INTEGER, CUSTOMER_NAME VARCHAR(100), ISSUE TEXT, STATUS VARCHAR(20), PRIORITY VARCHAR(20), CREATED_DATE DATE)"}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": description}
        ],
        temperature=0
    )
    
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
    
    try:
        config = json.loads(raw)
        
        # Ensure required fields
        config.setdefault("table", "GENERATED_DATA")
        config.setdefault("rows", 10)
        config.setdefault("locale", "en_US")
        config.setdefault("columns", [])
        config.setdefault("hints", {})
        
        # Cap rows
        config["rows"] = min(max(1, config.get("rows", 10)), MAX_ROWS)
        
        print(f"[datagen] LLM parsed config: {config}")
        return config
    except json.JSONDecodeError as e:
        print(f"[datagen] LLM JSON parse error: {e}\nRaw:\n{raw}")
        # Fallback - extract what we can
        desc_lower = description.lower()
        rows = 10
        match = re.search(r'(\d+)', description)
        if match:
            rows = int(match.group(1))
        
        table = "GENERATED_DATA"
        entity_map = {
            'support ticket': 'SUPPORT_TICKETS',
            'customer': 'CUSTOMERS',
            'product': 'PRODUCTS',
            'order': 'ORDERS',
            'employee': 'EMPLOYEES',
            'user': 'USERS',
        }
        for key, tbl in entity_map.items():
            if key in desc_lower:
                table = tbl
                break
        
        return {
            "table": table,
            "rows": min(rows, MAX_ROWS),
            "locale": "en_US",
            "columns": ["ID", "NAME", "VALUE"],
            "hints": {"ID": "integer", "NAME": "text", "VALUE": "text"}
        }


def _parse_description(description: str) -> dict:
    """Fallback simple parser if LLM not available."""
    if not description or not description.strip():
        return {
            "table": "GENERATED_DATA",
            "rows": 10,
            "locale": "en_US",
            "columns": ["ID", "NAME", "EMAIL"],
            "hints": {"ID": "sequential_integer", "NAME": "full_name", "EMAIL": "email"}
        }
    
    desc_lower = description.lower()
    
    # Extract row count
    rows = 10
    match = re.search(r'(\d+)', desc_lower)
    if match:
        rows = int(match.group(1))
    rows = min(max(1, rows), MAX_ROWS)
    
    # Extract table name
    table = "GENERATED_DATA"
    entity_map = {
        'customer': 'CUSTOMERS', 'customers': 'CUSTOMERS',
        'user': 'USERS', 'users': 'USERS',
        'employee': 'EMPLOYEES', 'employees': 'EMPLOYEES',
        'product': 'PRODUCTS', 'products': 'PRODUCTS',
        'order': 'ORDERS', 'orders': 'ORDERS',
        'category': 'CATEGORIES', 'categories': 'CATEGORIES',
    }
    for key, tbl in entity_map.items():
        if key in desc_lower:
            table = tbl
            break
    
    return {
        "table": table,
        "rows": rows,
        "locale": "en_US",
        "columns": [],
        "hints": {}
    }


def _generate_simple_data(config: dict) -> pd.DataFrame:
    """Generate simple fake data without LLM."""
    rows = config.get("rows", 10)
    columns = config.get("columns", ["ID", "NAME"])
    hints = config.get("hints", {})
    
    data = {}
    
    # Sample data pools for realistic generation
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", "James", "Mary"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Taylor"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]
    countries = ["USA", "UK", "Canada", "Australia", "Germany", "France", "Japan", "India"]
    departments = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations", "IT", "Support"]
    statuses = ["active", "inactive", "pending", "completed", "cancelled"]
    products = ["Laptop", "Phone", "Tablet", "Headphones", "Camera", "Watch", "Speaker", "Monitor"]
    priorities = ["low", "medium", "high", "critical"]
    
    # India-specific data
    indian_cities = ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Jaipur", "Lucknow", "Chandigarh"]
    indian_ranges = ["Himalayas", "Karakoram", "Pir Panjal", "Aravalli", "Western Ghats", "Eastern Ghats", "Satpura", "Vindhya"]
    mountain_names = ["Kangchenjunga", "Nanda Devi", "Kamet", "Saltoro Ri", "Saser Kangri", "K12", "Kangchenjunga South", "Mansarovar", "Teram Kangri", "Chorten Nyima"]
    
    for col in columns:
        col_lower = col.lower()
        hint = hints.get(col, "").lower() if hints.get(col) else ""
        
        # Auto-infer hint from column name patterns if not provided
        if not hint:
            # ID columns
            if "id" in col_lower or "_id" in col_lower or "no" in col_lower or "num" in col_lower:
                hint = "sequential integer starting from 1"
            # Code/Coupon/Reference
            elif "code" in col_lower or "coupon" in col_lower or "ref" in col_lower or "sku" in col_lower:
                hint = "alphanumeric code like COUPON10, SAVE20"
            # Discount/Amount/Price/Cost
            elif "discount" in col_lower or "percent" in col_lower or "amount" in col_lower or "price" in col_lower or "cost" in col_lower or "salary" in col_lower:
                hint = "decimal number"
            # Date/Time columns
            elif "date" in col_lower or "time" in col_lower or "created" in col_lower or "updated" in col_lower or "expired" in col_lower or "dob" in col_lower:
                hint = "recent date in YYYY-MM-DD format"
            # Count/Quantity/Uses
            elif "count" in col_lower or "qty" in col_lower or "quantity" in col_lower or "uses" in col_lower or "limit" in col_lower:
                hint = "integer number"
            # Name
            elif "name" in col_lower:
                hint = "full name"
            # Email
            elif "email" in col_lower:
                hint = "email address"
            # Phone
            elif "phone" in col_lower or "mobile" in col_lower:
                hint = "phone number"
            # Description
            elif "description" in col_lower or "desc" in col_lower or "note" in col_lower:
                hint = "text description"
            # Status
            elif "status" in col_lower:
                hint = "status value like active, inactive"
            # Boolean
            elif "is_" in col_lower or "has_" in col_lower or "active" in col_lower:
                hint = "true or false"
        
        # Check hint FIRST - this is most important
        if hint:
            if "sequential" in hint and "integer" in hint:
                data[col] = list(range(1, rows + 1))
            elif "sequential" in hint or "starting from" in hint:
                data[col] = list(range(1, rows + 1))
            elif "alphanumeric" in hint or "code like" in hint or "coupon" in hint:
                data[col] = [f"CPN{1000+i:04d}" for i in range(rows)]
            elif "discount" in hint and "percent" in hint:
                data[col] = [round(random.uniform(5, 50), 2) for _ in range(rows)]
            elif "discount" in hint or "amount" in hint or "price" in hint or "cost" in hint or "salary" in hint or "monetary" in hint:
                data[col] = [round(random.uniform(10, 500), 2) for _ in range(rows)]
            elif "decimal" in hint:
                data[col] = [round(random.uniform(1, 1000), 2) for _ in range(rows)]
            elif "integer" in hint or "number" in hint or ("uses" in hint or "count" in hint or "limit" in hint):
                data[col] = [random.randint(1, 100) for _ in range(rows)]
            elif "name" in hint or "full name" in hint:
            elif "email" in hint:
                data[col] = [f"user{i+1}@example.com" for i in range(rows)]
            elif "phone" in hint or "mobile" in hint:
                data[col] = [f"+1-555-{1000+i:04d}" for i in range(rows)]
            elif "city" in hint or "location" in hint:
                if "india" in hint:
                    data[col] = [random.choice(indian_cities) for _ in range(rows)]
                else:
                    data[col] = [random.choice(cities) for _ in range(rows)]
            elif "range" in hint:
                if "india" in hint:
                    data[col] = [random.choice(indian_ranges) for _ in range(rows)]
                else:
                    data[col] = [random.choice(indian_ranges) for _ in range(rows)]
            elif "mountain" in hint and "name" in hint:
                data[col] = [f"{mountain_names[i % len(mountain_names)]}" for i in range(rows)]
            elif "height" in hint or "meter" in hint or "elevation" in hint:
                data[col] = [round(random.uniform(1000, 8000), 2) for _ in range(rows)]
            elif "country" in hint:
                data[col] = [random.choice(countries) for _ in range(rows)]
            elif "address" in hint:
                data[col] = [f"{i+1} Main Street, City" for i in range(rows)]
            elif "date" in hint:
                data[col] = [f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}" for _ in range(rows)]
            elif "amount" in hint or "price" in hint or "cost" in hint or "salary" in hint or "monetary" in hint:
                data[col] = [round(random.uniform(100, 10000), 2) for _ in range(rows)]
            elif "quantity" in hint or "qty" in hint or "count" in hint:
                data[col] = [random.randint(1, 100) for _ in range(rows)]
            elif "product" in hint or "item" in hint:
                data[col] = [random.choice(products) for _ in range(rows)]
            elif "company" in hint or "organization" in hint or "org" in hint:
                data[col] = [f"Company {chr(65+i%26)}" for i in range(rows)]
            elif "department" in hint or "dept" in hint:
                data[col] = [random.choice(departments) for _ in range(rows)]
            elif "description" in hint or "comment" in hint or "note" in hint or "text" in hint or "issue" in hint:
                data[col] = [f"Sample description {i+1}" for i in range(rows)]
            elif "status" in hint:
                data[col] = [random.choice(statuses) for _ in range(rows)]
            elif "priority" in hint:
                data[col] = [random.choice(priorities) for _ in range(rows)]
            elif "boolean" in hint or "true/false" in hint or "yes/no" in hint:
                data[col] = [random.choice([True, False]) for _ in range(rows)]
            elif "integer" in hint or "number" in hint:
                data[col] = [random.randint(1, 1000) for _ in range(rows)]
            elif "decimal" in hint or "float" in hint:
                data[col] = [round(random.uniform(1, 1000), 2) for _ in range(rows)]
            else:
                # Use column name pattern as fallback
                if "id" in col_lower or "_id" in col_lower:
                    data[col] = list(range(1, rows + 1))
                elif "name" in col_lower:
                    data[col] = [f"{random.choice(first_names)} {random.choice(last_names)}" for _ in range(rows)]
                else:
                    data[col] = [f"Value_{i+1}" for i in range(rows)]
        # Check column name pattern if no hint or fallback
        elif "id" in col_lower or "_id" in col_lower or "no" in col_lower:
            data[col] = list(range(1, rows + 1))
        elif "name" in col_lower:
            data[col] = [f"{random.choice(first_names)} {random.choice(last_names)}" for _ in range(rows)]
        elif "first_name" in col_lower:
            data[col] = [random.choice(first_names) for _ in range(rows)]
        elif "last_name" in col_lower:
            data[col] = [random.choice(last_names) for _ in range(rows)]
        elif "email" in col_lower:
            data[col] = [f"user{i+1}@example.com" for i in range(rows)]
        elif "phone" in col_lower or "mobile" in col_lower:
            data[col] = [f"+1-555-{1000+i:04d}" for i in range(rows)]
        elif "city" in col_lower or "location" in col_lower:
            data[col] = [random.choice(cities) for _ in range(rows)]
        elif "country" in col_lower:
            data[col] = [random.choice(countries) for _ in range(rows)]
        elif "address" in col_lower:
            data[col] = [f"{i+1} Main Street, City" for i in range(rows)]
        elif "state" in col_lower or "province" in col_lower:
            data[col] = ["California", "Texas", "New York", "Florida", "Illinois"][:rows]
            while len(data[col]) < rows:
                data[col].append(random.choice(["California", "Texas", "New York"]))
        elif "zip" in col_lower or "postal" in col_lower or "pincode" in col_lower:
            data[col] = [f"{10000 + i}" for i in range(rows)]
        elif "age" in col_lower:
            data[col] = [random.randint(18, 65) for _ in range(rows)]
        elif "date" in col_lower or "dob" in col_lower or "birthday" in col_lower or "created" in col_lower or "updated" in col_lower:
            data[col] = [f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}" for _ in range(rows)]
        elif "time" in col_lower or "timestamp" in hint:
            data[col] = [f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d} {random.randint(0,23):02d}:{random.randint(0,59):02d}:00" for _ in range(rows)]
        elif "amount" in col_lower or "price" in col_lower or "cost" in col_lower or "salary" in col_lower:
            data[col] = [round(random.uniform(100, 10000), 2) for _ in range(rows)]
        elif "quantity" in col_lower or "qty" in col_lower or "count" in col_lower:
            data[col] = [random.randint(1, 100) for _ in range(rows)]
        elif "product" in col_lower or "item" in col_lower:
            data[col] = [random.choice(products) for _ in range(rows)]
        elif "company" in col_lower or "organization" in col_lower or "org" in col_lower:
            data[col] = [f"Company {chr(65+i%26)}" for i in range(rows)]
        elif "department" in col_lower or "dept" in col_lower:
            data[col] = [random.choice(departments) for _ in range(rows)]
        elif "description" in col_lower or "comment" in col_lower or "note" in col_lower:
            data[col] = [f"Sample description {i+1}" for i in range(rows)]
        elif "status" in col_lower:
            data[col] = [random.choice(statuses) for _ in range(rows)]
        elif "priority" in col_lower:
            data[col] = [random.choice(priorities) for _ in range(rows)]
        elif "is_" in col_lower or "has_" in col_lower or "active" in col_lower:
            data[col] = [random.choice([True, False]) for _ in range(rows)]
        # Default
        else:
            data[col] = [f"Value_{i+1}" for i in range(rows)]
    
    return pd.DataFrame(data)


def _save_csv(df: pd.DataFrame, config: dict) -> str:
    """Save DataFrame to CSV."""
    import datetime
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    table = config.get("table", "output").lower()
    filename = f"{table}_{timestamp}.csv"
    filepath = os.path.join(GENERATED_DIR, filename)
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    df.to_csv(filepath, index=False)
    
    print(f"[datagen] Saved {len(df)} rows → {filepath}")
    return filepath


# Try to import better generator, fall back to simple
GENERATOR_AVAILABLE = False

try:
    sys.path.insert(0, str(AGENT_DIR / "generator"))
    sys.path.insert(0, str(AGENT_DIR / "metadata"))
    
    from generator.prompt_parser import parse_prompt as _parse_prompt_llm
    from generator.fake_generator import generate_data as _generate_data_llm
    import generator.csv_writer as _csv_writer_module
    
    # Test if they work
    test_config = _parse_prompt_llm("Generate 5 users with name email")
    _test_df = _generate_data_llm(test_config)
    
    def parse_generation_prompt(description: str) -> dict:
        """Parse using LLM."""
        return _parse_prompt_llm(description)
    
    def generate_data(config: dict) -> pd.DataFrame:
        """Generate using LLM-powered faker."""
        return _generate_data_llm(config)
    
    def save_csv(df: pd.DataFrame, config: dict) -> str:
        """Save CSV."""
        if _csv_writer_module:
            _csv_writer_module.GENERATED_DIR = str(GENERATED_DIR)
            from generator.csv_writer import save_csv as _save_csv_orig
            return _save_csv_orig(df, config)
        return _save_csv(df, config)
    
    GENERATOR_AVAILABLE = True
    print("✓ Data generator (LLM) imported successfully")
    
except Exception as e:
    print(f"Warning: LLM generator not available: {e}")
    print("Using simple fallback generator")
    
    def parse_generation_prompt(description: str) -> dict:
        """Parse using simple rules."""
        return _parse_description(description)
    
    def generate_data(config: dict) -> pd.DataFrame:
        """Generate using simple fallback."""
        return _generate_simple_data(config)
    
    def save_csv(df: pd.DataFrame, config: dict) -> str:
        """Save CSV."""
        return _save_csv(df, config)
    
    GENERATOR_AVAILABLE = True
    print("✓ Data generator (simple) available")


# =============================================================================
# Request/Response Models
# =============================================================================

class DataGenRequest(BaseModel):
    """Request to generate synthetic data."""
    description: str = Field(..., description="Natural language description of data to generate")
    connection_id: Optional[str] = Field(None, description="Connection ID from saved_connections")
    load_to_db: bool = Field(True, description="Whether to load generated data to the database")


class DataGenResponse(BaseModel):
    """Response from data generation."""
    success: bool
    table: str
    rows: int
    columns: List[str]
    preview: List[Dict[str, Any]]
    csv_path: str
    loaded_to_db: bool = False
    db_table: Optional[str] = None
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None
    error: Optional[str] = None
    generation_config: Optional[Dict[str, Any]] = None


class LoadToDbRequest(BaseModel):
    """Request to load generated CSV to database."""
    csv_path: str = Field(..., description="Path to the CSV file")
    table: str = Field(..., description="Target table name in database")
    connection_id: str = Field(..., description="Connection ID from saved_connections")


class LoadToDbResponse(BaseModel):
    """Response from loading data to database."""
    success: bool
    table: str
    rows_loaded: int
    total_rows_in_table: int
    connection_id: str
    connection_name: str
    error: Optional[str] = None


class CatalogResponse(BaseModel):
    """Response with schema catalog for a connection."""
    connection_id: str
    connection_name: str
    db_type: str
    tables: List[str]
    catalog_json: Dict[str, Any]


# =============================================================================
# Helper Functions
# =============================================================================

def get_connection(connection_id: str):
    """Get a database connection by ID from saved_connections."""
    if not CONNECTION_MANAGER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Connection manager not available")
    
    # Parse connection_id (can be string like "11" or UUID)
    conn_id_int = None
    try:
        conn_id_int = int(connection_id)
    except (ValueError, TypeError):
        pass
    
    # Load from saved_connections table if it's an integer
    saved_conn = None
    if conn_id_int is not None:
        saved_conn = get_saved_connection(conn_id_int)
    
    # If integer ID and found in saved_connections
    if conn_id_int is not None and saved_conn:
        config = saved_conn.get("config", {})
        source_type = saved_conn.get("source_type", "")
        
        # Create a DatabaseConnection from saved config
        manager = get_connection_manager()
        
        # Map source_type to DatabaseType
        if source_type == "postgres":
            db_type = DatabaseType.POSTGRESQL
            norm_config = {
                "host": config.get("host", "localhost"),
                "port": int(config.get("port", "5432")),
                "database": config.get("database", ""),
                "user": config.get("user", ""),
                "password": config.get("password", ""),
            }
        elif source_type == "snowflake":
            db_type = DatabaseType.SNOWFLAKE
            norm_config = {
                "account": config.get("account", ""),
                "user": config.get("user", ""),
                "password": config.get("password", ""),
                "warehouse": config.get("warehouse", ""),
                "database": config.get("database", ""),
                "schema": config.get("schema", "PUBLIC"),
                "role": config.get("role", ""),
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source_type: {source_type}")
        
        # Add connection to manager and return
        conn_uuid = manager.add_connection(saved_conn["name"], db_type, norm_config)
        return manager.get_connection(conn_uuid)
    
    # Fallback: try UUID-based lookup from text2sql connections
    manager = get_connection_manager()
    manager._load_saved_connections_from_db()
    
    conn = manager.get_connection(connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
    return conn


def load_to_db(filepath: str, config: dict, connection) -> int:
    """Load CSV data to database based on connection type."""
    table = config["table"].upper()
    columns = [c.upper() for c in config["columns"]]
    
    df = pd.read_csv(filepath)
    
    if connection.db_type == DatabaseType.SNOWFLAKE:
        return _load_to_snowflake(filepath, table, columns, connection)
    elif connection.db_type == DatabaseType.POSTGRESQL:
        return _load_to_postgres(df, table, connection)
    elif connection.db_type == DatabaseType.MYSQL:
        return _load_to_mysql(df, table, connection)
    elif connection.db_type == DatabaseType.SQLITE:
        return _load_to_sqlite(df, table, connection)
    else:
        raise ValueError(f"Unsupported database type: {connection.db_type}")


def get_table_schema(connection, table_name: str) -> dict:
    """Get schema info (columns, types) for a table from the database."""
    if not connection._connection:
        connection.connect()
    
    schema = {"columns": {}, "sample_data": []}
    
    if connection.db_type == DatabaseType.SNOWFLAKE:
        cursor = connection._cursor
        try:
            # Get column definitions
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{table_name.upper()}'
                ORDER BY ORDINAL_POSITION
            """)
            for row in cursor.fetchall():
                col_name = row[0]
                schema["columns"][col_name] = {
                    "data_type": row[1],
                    "nullable": row[2] == "YES"
                }
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name.upper()} LIMIT 5")
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            schema["sample_data"] = [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            print(f"[datagen] Error fetching Snowflake schema: {e}")
            
    elif connection.db_type == DatabaseType.POSTGRESQL:
        cursor = connection._cursor
        try:
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name.lower(),))
            for row in cursor.fetchall():
                schema["columns"][row[0]] = {
                    "data_type": row[1],
                    "nullable": row[2] == "YES"
                }
            
            cursor.execute(f'SELECT * FROM "{table_name.lower()}" LIMIT 5')
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            schema["sample_data"] = [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            print(f"[datagen] Error fetching PostgreSQL schema: {e}")
    
    return schema


def _build_hints_from_schema(schema: dict, user_columns: List[str] = None) -> dict:
    """Build hints from database schema for data generation."""
    hints = {}
    columns = schema.get("columns", {})
    sample_data = schema.get("sample_data", [])
    
    # Get data type mappings to hints
    type_hints = {
        "VARCHAR": "text value",
        "TEXT": "text value",
        "CHAR": "text value",
        "INTEGER": "integer",
        "INT": "integer",
        "BIGINT": "integer",
        "SMALLINT": "integer",
        "NUMERIC": "decimal number",
        "DECIMAL": "decimal number",
        "FLOAT": "decimal number",
        "DOUBLE": "decimal number",
        "REAL": "decimal number",
        "BOOLEAN": "true or false",
        "DATE": "date",
        "TIMESTAMP": "timestamp",
        "DATETIME": "datetime",
    }
    
    col_names = user_columns if user_columns else list(columns.keys())
    
    for col in col_names:
        col_upper = col.upper()
        col_lower = col.lower()
        
        if col_upper in columns:
            data_type = columns[col_upper].get("data_type", "VARCHAR").upper()
            hint = type_hints.get(data_type, "realistic value")
            
            # Add column-specific hints based on name patterns
            if "id" in col_lower or "_id" in col_lower or "no" in col_lower or "num" in col_lower:
                hint = "sequential integer starting from 1"
            elif "code" in col_lower or "coupon" in col_lower or "ref" in col_lower or "sku" in col_lower:
                hint = "alphanumeric code like COUPON10, SAVE20"
            elif "name" in col_lower:
                hint = "realistic name"
            elif "email" in col_lower:
                hint = "email address"
            elif "phone" in col_lower or "mobile" in col_lower:
                hint = "phone number"
            elif "address" in col_lower:
                hint = "full address"
            elif "city" in col_lower:
                hint = "city name"
            elif "country" in col_lower:
                hint = "country name"
            elif "date" in col_lower or "created" in col_lower or "updated" in col_lower:
                hint = "recent date"
            elif "amount" in col_lower or "price" in col_lower or "cost" in col_lower:
                hint = "monetary amount"
            elif "id" in col_lower or "_id" in col_lower:
                hint = "unique sequential integer"
            elif "status" in col_lower:
                hint = "status value like active, inactive, pending"
            elif "description" in col_lower or "comment" in col_lower:
                hint = "short text description"
            elif "discount" in col_lower or "percent" in col_lower:
                hint = "decimal number for discount percentage"
            elif "amount" in col_lower or "price" in col_lower or "cost" in col_lower:
                hint = "monetary amount"
            elif "count" in col_lower or "qty" in col_lower or "quantity" in col_lower or "uses" in col_lower or "limit" in col_lower:
                hint = "integer number"
            
            hints[col] = hint
        else:
            # Default hint for unknown columns
            hints[col] = "realistic value"
    
    return hints


def _load_to_snowflake(filepath: str, table: str, columns: List[str], connection) -> int:
    """Load CSV to Snowflake using table stage."""
    if not connection._connection:
        connection.connect()
    
    cursor = connection._cursor
    
    try:
        # Create table if it doesn't exist
        col_defs = []
        for col in columns:
            col_upper = col.upper()
            col_lower = col.lower()
            if "id" in col_lower or "date" in col_lower:
                col_defs.append(f'"{col_upper}" INTEGER')
            elif "amount" in col_lower or "price" in col_lower:
                col_defs.append(f'"{col_upper}" DECIMAL(10,2)')
            else:
                col_defs.append(f'"{col_upper}" VARCHAR(255)')
        
        create_sql = f'CREATE TABLE IF NOT EXISTS {table} ({", ".join(col_defs)})'
        cursor.execute(create_sql)
        
        # Create stage for the table if it doesn't exist
        try:
            cursor.execute(f"CREATE STAGE IF NOT EXISTS %{table}")
        except:
            pass  # Stage might already exist or be created automatically
        
        normalized_path = filepath.replace("\\", "/")
        
        put_sql = f"PUT 'file://{normalized_path}' @%{table} OVERWRITE=TRUE AUTO_COMPRESS=FALSE"
        cursor.execute(put_sql)
        
        col_list = ", ".join([f'"{c.upper()}"' for c in columns])
        filename = os.path.basename(filepath)
        
        copy_sql = f"""
        COPY INTO {table} ({col_list})
        FROM @%{table}/{filename}
        FILE_FORMAT = (
            TYPE = 'CSV'
            FIELD_DELIMITER = ','
            SKIP_HEADER = 1
            FIELD_OPTIONALLY_ENCLOSED_BY = '"'
            NULL_IF = ('', 'NULL', 'null', 'None')
            EMPTY_FIELD_AS_NULL = TRUE
        )
        ON_ERROR = 'ABORT_STATEMENT'
        """
        
        cursor.execute(copy_sql)
        
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = cursor.fetchone()[0]
        
        try:
            cursor.execute(f"REMOVE @%{table}/{filename}")
        except:
            pass  # Cleanup optional
        
        return total_rows
        
    except Exception as e:
        raise Exception(f"Snowflake load failed: {e}")


def _load_to_postgres(df, table: str, connection) -> int:
    """Load DataFrame to PostgreSQL."""
    if not connection._connection:
        connection.connect()
    
    try:
        columns_def = []
        for col in df.columns:
            pd_dtype = str(df[col].dtype)
            if 'int' in pd_dtype:
                pg_type = 'INTEGER'
            elif 'float' in pd_dtype:
                pg_type = 'DECIMAL(10,2)'
            else:
                pg_type = 'VARCHAR(255)'
            columns_def.append(f'"{col}" {pg_type}')
        
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(columns_def)})'
        connection._cursor.execute(create_sql)
        connection._connection.commit()
        
        # Use copy_expert for proper PostgreSQL bulk loading
        import io
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, header=False)
        buffer.seek(0)
        
        columns_list = ", ".join([f'"{c}"' for c in df.columns])
        copy_sql = f'COPY "{table}" ({columns_list}) FROM STDIN WITH CSV'
        connection._cursor.copy_expert(copy_sql, buffer)
        connection._connection.commit()
        
        connection._cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        total_rows = connection._cursor.fetchone()[0]
        
        return total_rows
        
    except Exception as e:
        raise Exception(f"PostgreSQL load failed: {e}")


def _load_to_mysql(df, table: str, connection) -> int:
    """Load DataFrame to MySQL."""
    if not connection._connection:
        connection.connect()
    
    try:
        columns_def = []
        for col in df.columns:
            pd_dtype = str(df[col].dtype)
            if 'int' in pd_dtype:
                my_type = 'INT'
            elif 'float' in pd_dtype:
                my_type = 'DECIMAL(10,2)'
            else:
                my_type = 'VARCHAR(255)'
            columns_def.append(f"`{col}` {my_type}")
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns_def)})"
        connection._cursor.execute(create_sql)
        connection._connection.commit()
        
        df.to_sql(
            table,
            connection._connection,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=100
        )
        
        connection._cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = connection._cursor.fetchone()[0]
        
        return total_rows
        
    except Exception as e:
        raise Exception(f"MySQL load failed: {e}")


def _load_to_sqlite(df, table: str, connection) -> int:
    """Load DataFrame to SQLite."""
    if not connection._connection:
        connection.connect()
    
    try:
        df.to_sql(
            table,
            connection._connection,
            if_exists='append',
            index=False
        )
        
        connection._cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = connection._cursor.fetchone()[0]
        
        return total_rows
        
    except Exception as e:
        raise Exception(f"SQLite load failed: {e}")


def list_connection_tables(connection) -> List[str]:
    """List all tables in the database."""
    if not connection._connection:
        connection.connect()
    
    tables = []
    
    if connection.db_type == DatabaseType.SNOWFLAKE:
        cursor = connection._cursor
        try:
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = current_schema()
                ORDER BY TABLE_NAME
            """)
            tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"[datagen] Error listing Snowflake tables: {e}")
            
    elif connection.db_type == DatabaseType.POSTGRESQL:
        cursor = connection._cursor
        try:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"[datagen] Error listing PostgreSQL tables: {e}")
    
    return tables


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/connections")
async def list_connections_for_datagen():
    """List available database connections for data generator."""
    try:
        connections = get_saved_connections()
        # Return in format compatible with frontend
        return {
            "connections": [
                {
                    "id": str(c["id"]),
                    "name": c["name"],
                    "type": c["source_type"],
                    "config": c.get("config", {})
                }
                for c in connections
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/tables")
async def list_tables_for_connection(connection_id: str):
    """List available tables for a given connection."""
    try:
        print(f"[datagen] Listing tables for connection_id: {connection_id}")
        conn = get_connection(connection_id)
        print(f"[datagen] Got connection: {conn.name}, db_type: {conn.db_type}")
        tables = list_connection_tables(conn)
        print(f"[datagen] Found tables: {tables}")
        return {"connection_id": connection_id, "tables": tables}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[datagen] Error listing tables: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/schema/{table_name}")
async def get_table_schema_endpoint(connection_id: str, table_name: str):
    """Get schema info for a specific table."""
    try:
        conn = get_connection(connection_id)
        schema = get_table_schema(conn, table_name)
        return {"table": table_name, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for data generator."""
    return {
        "status": "healthy",
        "generator_available": GENERATOR_AVAILABLE,
        "connection_manager_available": CONNECTION_MANAGER_AVAILABLE,
        "generated_dir": str(GENERATED_DIR)
    }


@router.post("/generate", response_model=DataGenResponse)
async def generate_data_endpoint(request: DataGenRequest):
    """Generate synthetic data from natural language description."""
    try:
        print(f"[datagen] Parsing description: {request.description}")
        
        # Use LLM to parse the description (pass connection_id for schema context)
        try:
            config = _parse_with_llm(request.description, request.connection_id)
        except Exception as llm_err:
            print(f"[datagen] LLM parsing failed, using fallback: {llm_err}")
            config = parse_generation_prompt(request.description)
        
        if config.get("rows", 0) > MAX_ROWS:
            config["rows"] = MAX_ROWS
        
        print(f"[datagen] Config from LLM: {config}")
        
        # Handle table creation if needed
        table_created = False
        if request.connection_id and config.get("table"):
            try:
                conn = get_connection(request.connection_id)
                print(f"[datagen] Got connection: {conn.name}, type: {conn.db_type}")
                
                # Check if table exists
                tables = list_connection_tables(conn)
                table_name = config.get("table", "").upper()
                print(f"[datagen] Available tables: {tables}")
                
                if table_name not in tables:
                    # Table doesn't exist - check if we have create_table DDL
                    if config.get("create_table"):
                        print(f"[datagen] Creating table: {table_name}")
                        ddl = config["create_table"]
                        
                        # Adjust DDL for the specific database type
                        if conn.db_type == DatabaseType.POSTGRESQL:
                            conn._cursor.execute(ddl)
                            conn._connection.commit()
                            print(f"[datagen] Table {table_name} created in PostgreSQL")
                            table_created = True
                        elif conn.db_type == DatabaseType.SNOWFLAKE:
                            conn._cursor.execute(ddl)
                            print(f"[datagen] Table {table_name} created in Snowflake")
                            table_created = True
                    else:
                        print(f"[datagen] Table {table_name} doesn't exist and no DDL provided")
                        # Use parsed columns from LLM
                        if not config.get("columns"):
                            config["columns"] = ["ID", "NAME", "VALUE"]
                            config["hints"] = {"ID": "sequential integer", "NAME": "text", "VALUE": "text"}
                else:
                    # Table exists - get actual schema
                    schema = get_table_schema(conn, table_name)
                    if schema.get("columns"):
                        config["columns"] = list(schema["columns"].keys())
                        config["hints"] = _build_hints_from_schema(schema, config["columns"])
                        print(f"[datagen] Using existing table columns: {config['columns']}")
                        
            except Exception as e:
                import traceback
                print(f"[datagen] Schema/table creation error: {e}")
                print(traceback.format_exc())
        
        # Generate the data
        print(f"[datagen] Final config for generation: {config}")
        df = generate_data(config)
        
        # Save to CSV
        csv_path = save_csv(df, config)
        
        # Get preview (first 5 rows)
        preview = df.head(5).to_dict(orient='records')
        
        result = DataGenResponse(
            success=True,
            table=config.get("table", "unknown"),
            rows=len(df),
            columns=list(df.columns),
            preview=preview,
            csv_path=csv_path,
            generation_config=config
        )
        
        # Load to database if requested
        if request.load_to_db and request.connection_id:
            try:
                conn = get_connection(request.connection_id)
                
                load_config = {
                    "table": config["table"],
                    "columns": config["columns"]
                }
                
                total_rows = load_to_db(csv_path, load_config, conn)
                
                result.loaded_to_db = True
                result.db_table = config["table"]
                result.connection_id = request.connection_id
                result.connection_name = conn.name
                
                print(f"[datagen] Loaded {total_rows} rows to {conn.name}")
                
            except Exception as load_error:
                result.error = f"Generation successful but load failed: {str(load_error)}"
                print(f"[datagen] Load error: {load_error}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()[:500]}"
        print(f"[datagen] Error: {error_msg}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview", response_model=DataGenResponse)
async def preview_data(request: DataGenRequest):
    """Generate and preview data without loading to database."""
    try:
        config = parse_generation_prompt(request.description)
        
        if config.get("rows", 0) > MAX_ROWS:
            config["rows"] = MAX_ROWS
        
        df = generate_data(config)
        
        csv_path = save_csv(df, config)
        
        preview = df.head(5).to_dict(orient='records')
        
        return DataGenResponse(
            success=True,
            table=config.get("table", "unknown"),
            rows=len(df),
            columns=list(df.columns),
            preview=preview,
            csv_path=csv_path,
            generation_config=config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load", response_model=LoadToDbResponse)
async def load_to_database(request: LoadToDbRequest):
    """Load a previously generated CSV file to a database table."""
    if not os.path.exists(request.csv_path):
        raise HTTPException(status_code=404, detail=f"CSV file not found: {request.csv_path}")
    
    try:
        conn = get_connection(request.connection_id)
        
        df = pd.read_csv(request.csv_path)
        columns = list(df.columns)
        
        load_config = {
            "table": request.table,
            "columns": columns
        }
        
        total_rows = load_to_db(request.csv_path, load_config, conn)
        
        return LoadToDbResponse(
            success=True,
            table=request.table,
            rows_loaded=len(df),
            total_rows_in_table=total_rows,
            connection_id=request.connection_id,
            connection_name=conn.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full", response_model=DataGenResponse)
async def generate_and_load(request: DataGenRequest):
    """Full workflow: Generate data and load to database in one call."""
    if not request.connection_id:
        raise HTTPException(status_code=400, detail="connection_id required for full workflow")
    
    request.load_to_db = True
    return await generate_data_endpoint(request)


# =============================================================================
# Export
# =============================================================================

__all__ = ["router"]