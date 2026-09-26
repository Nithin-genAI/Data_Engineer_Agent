"""LLM picker — ported from AI_Data_Agent-reference/utils/llm_pick.py.

Why the `openai` SDK when we run on Fireworks?
----------------------------------------------
Fireworks serves an **OpenAI-compatible** API: same /chat/completions route, same
request/response JSON, same bearer-token auth. The `openai` SDK lets you override
`base_url`, so pointing it at Fireworks works with no code change. The package name
describes the *protocol* it speaks, not the company it talks to — swap
OPENAI_BASE_URL and it drives any compatible endpoint (OpenAI, Fireworks, Azure,
a local vLLM proxy).

`OpenAI()` reads OPENAI_API_KEY and OPENAI_BASE_URL straight from the environment,
which is why neither appears anywhere in this file.

Model names
-----------
Model ids must be whatever the *endpoint* understands. Against Fireworks that means
`accounts/fireworks/models/<name>`; a bare `gpt-...` id would 404. Defaults below
match the values in .env.example so an unconfigured run fails the same way a
misconfigured one does, instead of silently reaching for a different provider.
"""

import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None

_LEVEL_MODELS = {
    "low": os.environ.get("TF_MODEL_LOW", "accounts/fireworks/models/glm-5p2"),
    "medium": os.environ.get("TF_MODEL_MEDIUM", "accounts/fireworks/models/kimi-k3"),
    "high": os.environ.get("TF_MODEL_HIGH", "accounts/fireworks/models/kimi-k3"),
    "claude": os.environ.get("TF_MODEL_CLAUDE", "accounts/fireworks/models/minimax-m3"),
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
