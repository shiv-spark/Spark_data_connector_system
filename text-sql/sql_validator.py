import re

from sqlglot import parse_one, exp


FORBIDDEN_SQL_NODES = (
    exp.Delete,
    exp.Insert,
    exp.Update,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Merge,
)

FORBIDDEN_SQL_KEYWORDS = [
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
    "COPY",
]


def clean_sql(sql: str) -> str:
    """Clean SQL output from LLM, removing markdown and fixing common errors."""
    if not sql:
        return ""

    # Remove markdown code blocks
    sql = (
        sql.strip()
        .replace("```sql", "")
        .replace("```", "")
        .strip()
    )
    
    # Fix common LLM errors where column descriptions are appended as column names
    # Pattern: "TABLE.COLUMN word" -> "TABLE.COLUMN" where "word" is a description
    # Common description words that get appended: code, name, text, description, etc.
    
    # First, fix "is the" and "is a" patterns that appear after column names
    # Pattern: "COLUMN is the/a ..." -> "COLUMN"
    sql = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+is\s+(?:the|a)\s+[A-Za-z_][A-Za-z0-9_]*',
        r'\1',
        sql,
        flags=re.IGNORECASE
    )
    
    # Description words that commonly get appended as column aliases
    description_words = r'(?:code|name|description|text|string|value|id|date|time|amount|price|cost|type|status|number)'
    
    # Fix patterns like "COUPONS.CODE code" or "COUPONS.NAME name"
    # Match: word.word or DB.SCHEMA.TABLE.COLUMN followed by space and description word
    sql = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s+' + description_words + r'\b',
        r'\1',
        sql,
        flags=re.IGNORECASE
    )
    
    # Clean up any double spaces that might have been created
    sql = re.sub(r'\s+', ' ', sql)
    
    return sql


def validate_sql(sql: str, schema_dict: dict):
    sql = clean_sql(sql)

    if not sql:
        return False, "Empty SQL"

    if ";" in sql[:-1]:
        return False, "Multiple statements not allowed"

    if "--" in sql or "/*" in sql or "*/" in sql:
        return False, "Comments not allowed"

    upper_sql = sql.upper()

    for keyword in FORBIDDEN_SQL_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            upper_sql
        ):
            return (
                False,
                f"Forbidden keyword: {keyword}"
            )

    try:
        tree = parse_one(
            sql,
            dialect="snowflake"
        )

    except Exception as e:
        return False, f"Parse Error: {e}"

    root_select = tree.find(exp.Select)

    if root_select is None and not isinstance(tree, exp.Select):
        return False, "Only SELECT queries allowed"

    for node in tree.walk():

        if isinstance(
            node,
            FORBIDDEN_SQL_NODES
        ):
            return (
                False,
                f"Forbidden operation: {type(node).__name__}"
            )

    tables = {
        t.name
        for t in tree.find_all(exp.Table)
        if t.name
    }

    if not tables:
        return False, "No tables found"

    for table in tables:

        if table not in schema_dict:
            return (
                False,
                f"Unknown table: {table}"
            )

    return True, "VALID"