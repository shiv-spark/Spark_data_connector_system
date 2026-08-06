import time
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from text_sql.snowflake_config import (
    MODEL_NAME,
    MAX_RETRIES,
    BLOCK_PATTERNS,
    ANALYTICS_HINTS,
)
from text_sql.snowflake_sql_validator import (
    clean_sql,
    validate_sql,
)


SQL_PROMPT = """
You are an expert Snowflake SQL engineer.

Schema:
{schema}

CRITICAL RULES:
- Return exactly one Snowflake SELECT query
- Output only raw SQL, no explanations, no markdown
- For table names use fully qualified names: database.schema.table (e.g., AGENT_DB.agents.ORDERS)
- Use only the tables and columns listed in the schema above
- Read-only queries only (SELECT statements only)
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL
- Prefer explicit JOIN syntax
- Fully qualify columns when more than one table is used (e.g., AGENT_DB.agents.ORDERS.ORDER_ID)
- If the user asks for top N, use ORDER BY and LIMIT N

COLUMN NAME RULES (VERY IMPORTANT):
- Use ONLY the exact column names as shown in the schema (the text before the parenthesis)
- Column descriptions after "|" are NOT part of the column name - ignore them
- Example: "- CODE (VARCHAR, NOT NULL) | The discount code" means column name is CODE, not "CODE code"
- Never add column descriptions or meanings as aliases or column names
- Never use spaces in column references

SNOWFLAKE SYNTAX RULES:
- Use DATEDIFF(day, start_date, end_date) for date differences - ALWAYS include the date part (day, month, year, etc.)
- For date differences in days: DATEDIFF(day, start_date, end_date)
- Never use DATEDIFF(end_date, start_date) without the date part
- Use proper Snowflake functions: DATE_TRUNC, DATE_PART, CURRENT_DATE, etc.
- Cast data types explicitly when needed using :: syntax (e.g., column::DATE)

If the request is ambiguous but still answerable, produce the safest reasonable SELECT query.

User Request:
{question}
"""



RESULT_SUMMARY_PROMPT = """
You are a business analyst.

User Question:
{question}

SQL:
{sql}

Result:
{result}

Provide:
1. Short conversational answer.
2. Key insight.
3. Mention row count if relevant.

Keep response under 100 words.
"""

class SQLAgent:

    def __init__(self, schema_text, schema_dict):
        self.schema_text = schema_text
        self.schema_dict = schema_dict

        self.llm = ChatGroq(
            model_name=MODEL_NAME,
            temperature=0
        )

        self.prompt = (
            ChatPromptTemplate.from_template(
                SQL_PROMPT
            )
        )

    def screen_input(self, question):

        q = question.strip().lower()

        if not q:
            return False, "Empty question"

        for pattern in BLOCK_PATTERNS:

            if re.search(pattern, q):
                return (
                    False,
                    f"Blocked pattern: {pattern}"
                )

        return True, "SAFE"


    def _extract_response(self, response):
        content = getattr(response, "content", "")

        if isinstance(content, str):
            return content.strip()

        return ""

    def generate_sql(self, question):

        for attempt in range(1, MAX_RETRIES + 1):

            try:

                messages = (
                    self.prompt.format_messages(
                        schema=self.schema_text,
                        question=question
                    )
                )

                start = time.time()

                response = self.llm.invoke(messages)

                usage_metadata = getattr(response, "usage_metadata", {})

                response_metadata = getattr(response, "response_metadata", {})

                elapsed = round(time.time() - start,2)

                print(f"LLM call took {elapsed}s")

                sql = clean_sql(self._extract_response(response))

                if sql:
                    # return sql
                    return {
                            "sql": sql,
                            "prompt_tokens": usage_metadata.get(
                                "input_tokens",
                                0
                            ),
                            "completion_tokens": usage_metadata.get(
                                "output_tokens",
                                0
                            ),
                            "total_tokens": usage_metadata.get(
                                "total_tokens",
                                0
                            ),
                            "llm_latency": elapsed
                        }

            except Exception as e:
                print(
                    f"Attempt {attempt} failed: {e}"
                )

        return ""
    

    def summarize_result(self, question, sql, result):

        prompt = ChatPromptTemplate.from_template(RESULT_SUMMARY_PROMPT)

        messages = prompt.format_messages(
            question=question,
            sql=sql,
            result=result
        )

        response = self.llm.invoke(messages)

        return self._extract_response(response)

    def run(self, question):

        ok, msg = self.screen_input(question)

        if not ok:
            return {
                "success": False,
                "message": f"This request is not supported.\nReason: {msg}"
            }

        generation = self.generate_sql(question)

        if not generation:
            return {
                "success": False,
                "message": "Failed to generate SQL"
            }

        sql = generation["sql"]

        if not sql:
            return {
                "success": False,
                "message": "Unable to generate SQL for this request."
            }

        ok, msg = validate_sql(sql, self.schema_dict)

        if not ok:
            return {
                "success": False,
                "message": f"Generated SQL failed validation.\nReason: {msg}"
            }

        return {
            "success": True,
            "sql": sql,
            "message": "SQL generated successfully.",
            "prompt_tokens": generation["prompt_tokens"],
            "completion_tokens": generation["completion_tokens"],
            "total_tokens": generation["total_tokens"],
            "llm_latency": generation["llm_latency"]
        }