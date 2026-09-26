"""FastMCP entrypoint — registers the 4 data-agent tools and serves them over SSE.

This is the entire surface our project exposes to TrueForge. No router tool is
registered: TrueForge's own agent loop reads these tool descriptions and decides
which to call. Per PROJECT.md:
  - generate_sql / generate_transform : pure generation, no policy.
  - execute_sql / execute_transform   : raw execution, no internal safety or
    sandboxing — TrueForge's approval gate and Daytona sandbox are those layers.

Transport: SSE over HTTP (TrueForge's MCP manifest only accepts `remote` /
`truefoundry` URL types — no stdio — so the server must expose a URL).
"""

import contextlib
import io
import os
import traceback

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from sql_logic import generate_sql as _generate_sql
from etl_logic import generate_transform as _generate_transform
from database import DatabaseUtil

load_dotenv()

# Generated pandas code refers to data files by project-relative paths (e.g.
# "data/payments.csv"), but this process is launched from mcp-server/. Execute
# from the project root so those paths resolve. This is path resolution only —
# no sandboxing or policy, which stay TrueForge's job.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

mcp = FastMCP("data-agent")


@mcp.tool()
def generate_sql(question: str) -> str:
    """Convert a natural-language data question into a Postgres SQL query.

    Returns the SQL query text only — it is NOT executed. Generation only.
    """
    return _generate_sql(question)


@mcp.tool()
def execute_sql(query: str) -> str:
    """Execute a SQL query against Postgres and return the result rows as text.

    Raw execution only — no internal safety/keyword check. TrueForge's approval
    gate is the safety layer.
    """
    db = DatabaseUtil()
    return db.execute_sql(query)


@mcp.tool()
def generate_transform(instructions: str) -> str:
    """Convert natural-language ETL instructions into pandas code.

    Returns the pandas code text only — it is NOT executed. Generation only.
    """
    return _generate_transform(instructions)


@mcp.tool()
def execute_transform(code: str) -> str:
    """Execute the given Python/pandas code and return its stdout/output.

    Raw execution only — no sandboxing or safety wrapper. TrueForge's Daytona
    sandbox is the isolation layer.
    """
    buf = io.StringIO()
    glob = {"__name__": "__main__"}
    try:
        with (
            contextlib.chdir(PROJECT_ROOT),
            contextlib.redirect_stdout(buf),
            contextlib.redirect_stderr(buf),
        ):
            exec(code, glob)
        out = buf.getvalue().strip()
        return out if out else "Code executed successfully."
    except Exception as e:
        return f"Failed to execute code: {e}\n{traceback.format_exc()}"


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", "8765"))
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="sse")
