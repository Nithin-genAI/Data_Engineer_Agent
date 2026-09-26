"""SQL generation logic — ported from AI_Data_Agent-reference/agents/sql_analyst.py.

Ports the curate -> schema-fetch -> SQL-generation nodes and STOPS before
execution. The reference repo's is_safe_sql judge node and the execute/represent
nodes are NOT ported here — TrueForge's approval gate replaces is_safe, and
execution lives in the separate execute_sql tool.
"""

import re

from database import DatabaseUtil
from llm import invoke_llm


def _clean_sql(text: str) -> str:
    """Strip markdown fences / leading 'SQL' if the LLM wrapped the query."""
    text = text.strip()
    fence = re.match(r"^```(?:sql|SQL)?\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text.strip()


def generate_sql(question: str) -> str:
    """Curate the question, fetch the Postgres schema, generate SQL. Return text only.

    Ports (in order): curate_ques -> prompt_query_context -> generate_sql
    from the reference sql_analyst graph, then stops.
    """
    # 1. curate_ques (low LLM) — ported verbatim
    curated_question = invoke_llm("low", f"Curate the following question: {question}")

    # 2. prompt_query_context — fetch schema, build prompt (ported verbatim)
    obj = DatabaseUtil()
    schema_info = obj.schema_details("public")

    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language
    query into Postgres SQL query that can be executed on the database. You are provided
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.

    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}

    """

    # 3. generate_sql (medium LLM) — ported verbatim
    generated_sql_query = invoke_llm("medium", prompt)

    # Return SQL text only, cleaned so it is ready to execute.
    return _clean_sql(generated_sql_query)
