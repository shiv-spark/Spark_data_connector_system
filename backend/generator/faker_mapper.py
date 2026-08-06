


import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import json
import re
from faker import Faker
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


SYSTEM_PROMPT = """
You are a Faker code generation expert.

Given a list of columns with their data types and hints, return a JSON object where:
  - each key   = column name (exactly as given)
  - each value = a valid single-line Python expression using the `fake` object

Rules:
  - Use ONLY these Faker methods (fake.<method>):
      fake.name(), fake.first_name(), fake.last_name(), fake.user_name(),
      fake.email(), fake.phone_number(), fake.city(), fake.state(),
      fake.country(), fake.address(), fake.postcode(), fake.company(),
      fake.job(), fake.date_of_birth(), fake.date_this_year(),
      fake.date_time_this_year(), fake.date_this_decade(),
      fake.sentence(), fake.text(), fake.url(), fake.ipv4(),
      fake.uuid4(), fake.boolean(),
      fake.random_int(min=X, max=Y),
      fake.pyfloat(min_value=X, max_value=Y, right_digits=2),
      fake.random_element(elements=["a", "b", "c"])

  - For NUMBER columns: use fake.random_int() or fake.pyfloat()
  - For DATE columns:   use fake.date_this_year() or fake.date_of_birth()
  - For TEXT columns:   use the most appropriate string provider
  - For ID/PK columns:  use fake.uuid4() or fake.random_int(min=1, max=99999)
  - For domain-specific columns (status, plan, gender, category):
      use fake.random_element(elements=[...]) with realistic choices

Return ONLY valid JSON. No explanation, no markdown, no code fences.

Example input:
[
  {"column": "USER_NAME",  "data_type": "TEXT",   "hint": "Indian full name"},
  {"column": "PLAN_TYPE",  "data_type": "TEXT",   "hint": "telecom plan type"},
  {"column": "AMOUNT",     "data_type": "NUMBER", "hint": "order total in rupees"},
  {"column": "ORDER_DATE", "data_type": "DATE",   "hint": "recent order date"}
]

Example output:
{
  "USER_NAME":  "fake.name()",
  "PLAN_TYPE":  "fake.random_element(elements=['Prepaid', 'Postpaid', 'Enterprise'])",
  "AMOUNT":     "fake.pyfloat(min_value=100, max_value=50000, right_digits=2)",
  "ORDER_DATE": "fake.date_this_year()"
}
"""


def build_dynamic_faker_mapping(columns: list[dict], locale: str = "en_IN") -> dict:
    """
    Asks the LLM to map each column to the best Faker expression.

    Args:
        columns : list of dicts with keys: column, data_type, hint
                  e.g. [{"column": "USER_NAME", "data_type": "TEXT", "hint": "Indian full name"}]
        locale  : Faker locale string e.g. "en_IN", "en_US"

    Returns:
        dict of { column_name: callable } where each callable returns a fake value
    """

    print(f"[faker_mapper] Asking LLM to map {len(columns)} columns → Faker expressions...")

    payload = json.dumps(columns, indent=2)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Locale: {locale}\n\nColumns:\n{payload}"}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        expr_map = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[faker_mapper] JSON parse error: {e}\nRaw:\n{raw}")
        raise

    print(f"[faker_mapper] LLM returned expressions for: {list(expr_map.keys())}")

    # Build executable callables from the expression strings
    fake = Faker(locale)
    callable_map = {}

    for col, expr in expr_map.items():
        try:
            # Wrap in lambda so each call generates a fresh value
            callable_map[col] = _make_callable(expr, fake)
            # Quick smoke test
            test_val = callable_map[col]()
            print(f"  {col:30} → {expr:55} sample: {test_val}")
        except Exception as e:
            print(f"  [faker_mapper] WARNING: failed to build callable for '{col}': {e}")
            print(f"                 Expression was: {expr}")
            print(f"                 Falling back to fake.bothify('???-####')")
            callable_map[col] = lambda: fake.bothify("???-####")

    return callable_map


def _make_callable(expr: str, fake: Faker):
    """
    Converts a Faker expression string like 'fake.name()' into a callable.
    Uses eval in a restricted namespace containing only `fake` and `random`.
    """
    import random

    namespace = {"fake": fake, "random": random}

    # Validate expression only uses allowed identifiers (safety check)
    if any(danger in expr for danger in ["import", "exec", "open", "os.", "sys."]):
        raise ValueError(f"Unsafe expression rejected: {expr}")

    # Return a lambda that evaluates the expression fresh each call
    return lambda: eval(expr, {"__builtins__": {}}, namespace)


if __name__ == "__main__":
    # Test with a realistic mixed set of columns
    test_columns = [
        {"column": "USER_ID",       "data_type": "NUMBER", "hint": "unique user ID"},
        {"column": "USER_NAME",     "data_type": "TEXT",   "hint": "Indian full name"},
        {"column": "EMAIL",         "data_type": "TEXT",   "hint": "email address"},
        {"column": "MOBILE_NO",     "data_type": "TEXT",   "hint": "Indian mobile number"},
        {"column": "CITY",          "data_type": "TEXT",   "hint": "Indian city"},
        {"column": "PLAN_TYPE",     "data_type": "TEXT",   "hint": "telecom plan: prepaid or postpaid"},
        {"column": "DATA_USAGE_GB", "data_type": "NUMBER", "hint": "monthly data usage in GB"},
        {"column": "RECHARGE_AMT",  "data_type": "NUMBER", "hint": "recharge amount in rupees"},
        {"column": "JOINED_DATE",   "data_type": "DATE",   "hint": "date customer joined"},
        {"column": "IS_ACTIVE",     "data_type": "TEXT",   "hint": "active status: YES or NO"},
    ]

    mapping = build_dynamic_faker_mapping(test_columns, locale="en_IN")

    print("\n── Generating 3 sample rows ──")
    for i in range(3):
        row = {col["column"]: mapping[col["column"]]() for col in test_columns}
        print(row)