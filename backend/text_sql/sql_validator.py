"""
SQL Validator for Text-to-SQL Agent
Validates and cleans SQL queries for PostgreSQL and Snowflake
"""

import re
from typing import Tuple, Dict, Set

# PostgreSQL forbidden keywords (DDL and DML that modify data)
FORBIDDEN_KEYWORDS = [
    "DELETE",
    "INSERT",
    "UPDATE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "MERGE",
    "CALL",
    "EXECUTE",
    "EXEC",
]

# PostgreSQL reserved keywords that might indicate malicious queries
SUSPICIOUS_PATTERNS = [
    r"\bpg_\w+",  # PostgreSQL system tables
    r"\binformation_schema\b",
    r"\bcopy\s+\w+\s+(?:to|from)",
    r"\blistener\b",
    r"\bnotify\b",
]


def clean_sql(sql: str) -> str:
    """
    Clean SQL output from LLM, removing markdown and fixing common errors.
    
    Args:
        sql: Raw SQL string from LLM
        
    Returns:
        Cleaned SQL string
    """
    if not sql:
        return ""
    
    # Remove markdown code blocks
    sql = (
        sql.strip()
        .replace("```sql", "")
        .replace("```", "")
        .strip()
    )
    
    # Remove any explanatory text after the SQL
    # Look for common patterns that indicate the end of SQL
    sql = re.split(r'\n\n', sql)[0]  # Take only the first paragraph
    
    # Remove trailing semicolon if there's text after it
    if ';' in sql:
        parts = sql.split(';')
        sql = parts[0] + ';' if len(parts) > 1 and parts[1].strip() else parts[0]
    
    # Clean up any double spaces
    sql = re.sub(r'\s+', ' ', sql)
    
    return sql.strip()


# Matches an identifier in a FROM/JOIN clause, including optionally
# dotted/qualified names and double-quoted segments, e.g.:
#   CUSTOMERS
#   AGENT_DB.AGENTS.CUSTOMERS
#   "AGENT_DB"."AGENTS"."CUSTOMERS"
#   agent_db.agents.customers AS c
_IDENTIFIER_SEGMENT = r'(?:"[^"]+"|\w+)'
_QUALIFIED_IDENTIFIER = rf'{_IDENTIFIER_SEGMENT}(?:\.{_IDENTIFIER_SEGMENT})*'

_TABLE_REF_PATTERN = re.compile(
    rf'\b(?:FROM|JOIN)\s+({_QUALIFIED_IDENTIFIER})',
    re.IGNORECASE
)


def _last_identifier_segment(qualified_name: str) -> str:
    """
    Given a possibly-dotted/qualified identifier (e.g.
    'AGENT_DB.AGENTS.CUSTOMERS' or '"AGENT_DB"."AGENTS"."CUSTOMERS"'),
    return the final segment (the table name) with any surrounding double
    quotes stripped.
    """
    segments = qualified_name.split('.')
    last = segments[-1].strip()
    if last.startswith('"') and last.endswith('"') and len(last) >= 2:
        last = last[1:-1]
    return last


def validate_sql(sql: str, schema_dict: Dict[str, Set[str]]) -> Tuple[bool, str]:
    """
    Validate SQL query for safety and correctness.
    
    Args:
        sql: SQL query string
        schema_dict: Dictionary mapping table names to sets of column names
    
    Returns:
        Tuple of (is_valid, message)
    """
    sql = clean_sql(sql)
    
    if not sql:
        return False, "Empty SQL"
    
    # Check for multiple statements (only allow single SELECT)
    if ";" in sql[:-1]:  # Allow semicolon at the very end
        return False, "Multiple statements not allowed"
    
    # Check for comments
    if "--" in sql or "/*" in sql or "*/" in sql:
        return False, "Comments not allowed in SQL"
    
    # Convert to upper for keyword checking
    upper_sql = sql.upper()
    
    # Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            return False, f"Forbidden keyword: {keyword}"
    
    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Suspicious pattern detected"
    
    # Must start with SELECT
    if not upper_sql.strip().startswith("SELECT"):
        return False, "Query must start with SELECT"
    
    # Basic structure validation
    if "SELECT" not in upper_sql:
        return False, "Only SELECT queries allowed"
    
    # Extract table names from FROM and JOIN clauses.
    # Supports both bare names (e.g. "customers") and fully-qualified
    # dotted names (e.g. "AGENT_DB.AGENTS.CUSTOMERS" for Snowflake), with
    # or without double-quoted identifier segments. Only the final
    # segment (the actual table name) is validated against schema_dict,
    # which is keyed by bare table names.
    found_tables = set()

    for match in _TABLE_REF_PATTERN.finditer(sql):
        qualified_name = match.group(1)
        table_name = _last_identifier_segment(qualified_name)
        if table_name:
            found_tables.add(table_name.lower())
    
    # Validate tables exist in schema
    schema_tables_lower = {t.lower(): t for t in schema_dict.keys()}
    for table in found_tables:
        if table not in schema_tables_lower:
            return False, f"Unknown table: {table}"
    
    # Check for nested queries that might be suspicious
    open_parens = sql.count('(')
    close_parens = sql.count(')')
    if open_parens != close_parens:
        return False, "Mismatched parentheses"
    
    return True, "VALID"


def extract_tables_from_sql(sql: str) -> Set[str]:
    """
    Extract table names from a SQL query.

    For fully-qualified/dotted table references (e.g.
    "AGENT_DB.AGENTS.CUSTOMERS"), only the final segment ("CUSTOMERS") is
    returned, matching how validate_sql() resolves table names against the
    schema dict.

    Args:
        sql: SQL query string
        
    Returns:
        Set of table names
    """
    sql = clean_sql(sql)
    tables = set()

    for match in _TABLE_REF_PATTERN.finditer(sql):
        qualified_name = match.group(1)
        table_name = _last_identifier_segment(qualified_name)
        if table_name:
            tables.add(table_name)

    return tables


def is_read_only_query(sql: str) -> bool:
    """
    Check if a query is read-only (SELECT only).
    
    Args:
        sql: SQL query string
        
    Returns:
        True if query is read-only
    """
    sql = clean_sql(sql)
    upper_sql = sql.upper()
    
    # Must start with SELECT
    if not upper_sql.strip().startswith("SELECT"):
        return False
    
    # Check for any forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            return False
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("SQL Validator Test")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        ("SELECT * FROM users", {"users": {"id", "name"}}, True),
        ("SELECT id, name FROM users WHERE id = 1", {"users": {"id", "name"}}, True),
        ("DELETE FROM users", {"users": {"id", "name"}}, False),
        ("INSERT INTO users VALUES (1, 'test')", {"users": {"id", "name"}}, False),
        ("DROP TABLE users", {"users": {"id", "name"}}, False),
        ("SELECT * FROM nonexistent", {"users": {"id", "name"}}, False),
        ("```sql\nSELECT * FROM users\n```", {"users": {"id", "name"}}, True),
        # Snowflake fully-qualified table names
        ("SELECT COUNT(CUSTOMER_ID) FROM AGENT_DB.AGENTS.CUSTOMERS", {"CUSTOMERS": {"CUSTOMER_ID"}}, True),
        ('SELECT * FROM "AGENT_DB"."AGENTS"."CUSTOMERS" c JOIN AGENT_DB.AGENTS.ORDERS o ON c.id = o.customer_id',
         {"CUSTOMERS": {"id"}, "ORDERS": {"customer_id"}}, True),
        ("SELECT * FROM AGENT_DB.AGENTS.NONEXISTENT", {"CUSTOMERS": {"id"}}, False),
    ]
    
    for sql, schema, expected in test_cases:
        is_valid, msg = validate_sql(sql, schema)
        status = "✓ PASS" if is_valid == expected else "✗ FAIL"
        print(f"\n{status}: {sql[:50]}...")
        print(f"  Expected: {'Valid' if expected else 'Invalid'}")
        print(f"  Got: {'Valid' if is_valid else 'Invalid'} ({msg})")