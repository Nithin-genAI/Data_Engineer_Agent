"""ETL transform generation logic — ported from AI_Data_Agent-reference/agents/etl_analyst.py.

Ports the code-generation half of transform_load_tool (read sample rows for
context -> build pandas-gen prompt -> LLM generates pandas code -> clean) and
STOPS before execution. The reference's etl_tools.execute_code call is NOT
portated here — execution lives in the separate execute_transform tool, and no
sandboxing/safety wrapper is ported (TrueForge's Daytona sandbox is the
isolation layer).

Adapted to the PROJECT.md signature: generate_transform(instructions: str) -> str.
The reference tool took explicit input_file_path/output_folder/output_format
params; here those are conveyed inside the freeform `instructions` string, and a
file path is detected from it to fetch the same head(3) context the reference used.
"""

import os
import re

import pandas as pd

from llm import invoke_llm


def _find_file_path(instructions: str) -> str | None:
    match = re.search(r"[\w./\\\-]+\.(?:csv|json|parquet)", instructions)
    return match.group(0) if match else None


def _read_head(file_path: str) -> str:
    """Ported from ETLTools.transform_load_context: read file, return head(3) as str."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext == ".json":
        df = pd.read_json(file_path, lines=True)
    elif ext == ".parquet":
        df = pd.read_parquet(file_path)
    else:
        return f"Unsupported file format: {ext}"
    return str(df.head(3))


def _clean_code(text: str) -> str:
    """Strip markdown fences. Ported + improved over the reference's
    `response.strip().strip('```').strip().lstrip('python').strip()`."""
    text = text.strip()
    fence = re.match(r"^```(?:python|py)?\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text.strip()


def generate_transform(instructions: str) -> str:
    """Generate pandas code for the given ETL instructions. Return code text only.

    Ports the generation logic of the reference transform_load_tool, then stops.
    """
    file_path = _find_file_path(instructions)
    context = _read_head(file_path) if file_path and os.path.exists(file_path) else ""

    prompt = f"""
            You are a Python Data Analyst who uses Pandas to analyze data.
            You need to provide only the Pandas Code that will help to perform the right ETL operations
            as per the user's instructions. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed
            in a Python environment with Pandas installed.
            Don't write anything else than Pandas Code. \n

            User's instructions: {instructions}\n
            Here's the context (first 3 rows) of the data you will be analyzing: {context}\n
    """

    response = invoke_llm("claude", prompt)

    # Optional cleaning — ported from the reference.
    return _clean_code(response)
