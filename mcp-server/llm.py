"""LLM picker — ported from AI_Data_Agent-reference/utils/llm_pick.py.

The reference used LangChain (ChatOpenAI / ChatAnthropic). We don't pull in
LangChain or LangGraph here — TrueForge is the orchestrator now — so this is a
thin rewrite over the raw OpenAI Python SDK. Point OPENAI_BASE_URL at any
OpenAI-compatible gateway (OpenAI, Azure, a local proxy, etc.).

Level -> model mapping defaults to the reference repo's model names and is
overridable per level via env vars.
"""

import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None

_LEVEL_MODELS = {
    "low": os.environ.get("TF_MODEL_LOW", "gpt-5.6-luna"),
    "medium": os.environ.get("TF_MODEL_MEDIUM", "gpt-5.6-terra"),
    "high": os.environ.get("TF_MODEL_HIGH", "gpt-5.6-sol"),
    "claude": os.environ.get("TF_MODEL_CLAUDE", "claude-sonnet-5"),
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # OpenAI() reads OPENAI_API_KEY and OPENAI_BASE_URL from the env.
        _client = OpenAI()
    return _client


def invoke_llm(level: str, prompt: str) -> str:
    """Invoke the LLM mapped to `level` with `prompt` and return the text."""
    model = _LEVEL_MODELS.get(level.lower())
    if not model:
        raise ValueError(f"Unsupported level: {level}")
    resp = _get_client().chat.completions.create(
        model=model,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""
