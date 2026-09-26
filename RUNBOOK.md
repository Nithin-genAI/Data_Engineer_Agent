# RUNBOOK — starting Data_Agent from scratch

Everything you need to bring the project up in a **VS Code terminal**, in order.
Three processes must be running: **Postgres**, the **MCP server**, and **TrueForge**.

Open three terminals in VS Code (`` Ctrl+` `` then the `+` icon) — one per process,
so you can see each one's logs. Or use one, with `&`/`nohup`.

---

## Prerequisites (one time)

| Need | Check | Fix |
|---|---|---|
| Node **≥ 22** | `node --version` | `.nvmrc` pins 22 — run `nvm use` in the project root |
| Python 3.12 | `python3 --version` | — |
| Postgres 16 | `pg_isready` | `brew install postgresql@16` |

> **Node 20 will segfault TrueForge** (exit 139, native `better-sqlite3` ABI
> mismatch). If TrueForge dies instantly, you're on the wrong Node.

---

## Terminal 1 — Postgres

```bash
brew services start postgresql@16
pg_isready                      # → /tmp:5432 - accepting connections
```

First time only — create the database and load the CSVs:

```bash
psql -d postgres -c 'CREATE DATABASE data_agent_db;'
cd /Users/ramesh/Desktop/Data_Agent/mcp-server
source .venv/bin/activate
python feed_db.py               # creates tables, loads data/, prints row counts
```

Expected: `users 10,000 · vehicles 3,000 · rides 20,000 · payments 16,073 · ratings 12,000`

---

## Terminal 2 — MCP server (our code)

```bash
cd /Users/ramesh/Desktop/Data_Agent/mcp-server
source .venv/bin/activate
python server.py
```

Listens on **http://127.0.0.1:8765/sse**. Healthy log looks like:

```
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

Check it independently:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN | grep -q LISTEN && echo "mcp: listening"
```

> Don't health-check `/sse` with `curl` + `&&`. SSE is a long-lived *stream*, so curl
> prints `200` and then exits non-zero when `--max-time` cuts it off — which looks like a
> failure and breaks `&&` chains. Check the listener instead, or add `|| true`.

> **Restart this server after changing `server.py` or `.env`.** Python doesn't hot-reload,
> and a stale process is the #1 cause of confusing failures — you'll edit code, see no
> change, and blame the code.

---

## Terminal 3 — TrueForge (the harness)

```bash
cd /Users/ramesh/Desktop/Data_Agent
source ~/.nvm/nvm.sh && nvm use          # reads .nvmrc → v22
OUTBOUND_URL_ALLOWED_HOSTS='["127.0.0.1"]' npx @truefoundry/trueforge
```

`OUTBOUND_URL_ALLOWED_HOSTS` is **required** — TrueForge's SSRF guard blocks loopback by
default, and without it MCP registration fails with `Outbound URL blocked for host 127.0.0.1`.

Then open **http://localhost:8790/** and pick the `data-agent` agent.

Config (MCP registration, provider, agent) persists in TrueForge's local SQLite, so you
register **once** and it survives restarts.

---

## Health check — all three at once

```bash
pg_isready
lsof -nP -iTCP:8765 -sTCP:LISTEN | grep -q LISTEN && echo "mcp  :8765 -> listening"
curl -s -o /dev/null -w "tf   :8790 -> %{http_code}\n" --max-time 5 http://localhost:8790/
```

---

## Re-registering from scratch (only if TrueForge's DB is wiped)

**1. Model provider**

```bash
curl -X POST http://localhost:8790/api/v1/settings/model-providers \
  -H 'Content-Type: application/json' -d '{
  "name": "fireworks",
  "manifest": {
    "auth": {"api_key": "fw_YOUR_KEY"},
    "models": [
      {"model_id": "accounts/fireworks/models/glm-5p2",  "name": "glm-5p2"},
      {"model_id": "accounts/fireworks/models/kimi-k3",  "name": "kimi-k3"},
      {"model_id": "accounts/fireworks/models/minimax-m3","name": "minimax-m3"}
    ]
  }}'
```

> Only register models that are **actually deployed** on your Fireworks account —
> an undeployed id fails later with `Unknown model … provider not configured`.

**2. MCP server**

```bash
curl -X POST http://localhost:8790/api/v1/settings/mcp-servers \
  -H 'Content-Type: application/json' -d '{
  "manifest": {
    "type": "remote",
    "name": "data-agent",
    "url": "http://127.0.0.1:8765/sse",
    "description": "NL->SQL and NL->pandas generation plus raw execution primitives"
  }}'
```

**3. Agent — this is where the approval policy lives**

```bash
curl -X POST http://localhost:8790/api/v1/agents \
  -H 'Content-Type: application/json' -d '{
  "name": "data-agent",
  "description": "SQL + ETL data analyst backed by the data-agent MCP server.",
  "manifest": {
    "model": {"name": "fireworks/glm-5p2", "params": {"reasoning_effort": "none"}},
    "instructions": "You are a data analyst with SQL and pandas/ETL tools. For a data question, generate SQL with generate_sql, then execute it with execute_sql. For an ETL task, generate pandas code with generate_transform, then execute it with execute_transform. Always generate first, then execute. Execution tools require human approval which will be prompted automatically.",
    "mcp_servers": [{
      "name": "data-agent",
      "enable_tools": ["@all"],
      "preload": false,
      "require_approval_for_tools": ["execute_sql", "execute_transform"]
    }],
    "config": {"sandbox": {"enabled": false}}
  }}'
```

Two things that are easy to get wrong:

- `require_approval_for_tools` goes on the **agent**, not on the MCP registration. It's
  the only surface that actually gates execution.
- `preload: false` makes TrueForge discover tools at runtime via `list_tools` →
  `get_tool_info` → `call_tool`.

**4. Verify the policy is really active** — don't trust the 2xx:

```bash
curl -s http://localhost:8790/api/v1/agents | python3 -m json.tool | grep -A3 require_approval
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to API: Connect Timeout Error` | Transient network drop reaching Fireworks | Retry. Confirm with the curl in *Verifying Fireworks* below. |
| `No such file or directory: 'data/x.csv'` | Stale MCP server (path fix landed later) | Restart Terminal 2 |
| `Outbound URL blocked for host 127.0.0.1` | SSRF guard | Set `OUTBOUND_URL_ALLOWED_HOSTS='["127.0.0.1"]'` and restart TrueForge |
| `Unknown model … provider not configured` | Model id not registered/deployed | Re-register provider with deployed ids only |
| TrueForge exits **139** | Node < 22 | `nvm use` (reads `.nvmrc`) |
| `user message cannot be sent while approvals are pending` | A stuck approval on that session | Start a **new session** |
| `[]` from a SQL question | Threshold/value not in the data | See *Data traps* in README.md |

### Verifying Fireworks

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" --max-time 20 \
  -X POST https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_KEY" -H "Content-Type: application/json" \
  -d '{"model":"accounts/fireworks/models/glm-5p2","max_tokens":5,
       "messages":[{"role":"user","content":"hi"}]}'
```

### Killing and restarting cleanly

```bash
pkill -f "server.py"                                        # MCP server
lsof -nP -iTCP:8765 -sTCP:LISTEN                            # confirm it's gone
cd /Users/ramesh/Desktop/Data_Agent/mcp-server && source .venv/bin/activate && python server.py
```

---

## Ports

| Service | Port |
|---|---|
| TrueForge UI + API | 8790 |
| MCP server (SSE) | 8765 |
| Postgres | 5432 |
