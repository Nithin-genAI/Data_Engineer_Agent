# Data_Agent — TrueForge Harness Rebuild

## What this is
A rebuild of an existing LangGraph multi-agent data system (SQL + ETL) so that
**TrueForge is the agent harness** — routing, HITL approval, and sandboxed
execution all live in TrueForge, not in our own code. Our code only does
generation (NL→SQL, NL→pandas) and raw execution primitives. Built for the
TrueFoundry × Polaris hackathon. Judging criterion: real harness delegation,
not a chat UI bolted on top of our own orchestration.

## Hard rule driving every decision below
If a piece of logic decides *what to do next* (route, approve, sandbox), it
belongs to TrueForge. If it decides *what the answer is* (SQL text, pandas
code), it belongs to our MCP server. Nothing else is allowed to make a
decision.

---

## Folder structure
```
Data_Agent/                    ← root
├── data/                      ← copied verbatim from the old repo's data/ folder
│   ├── extract/                   (ETL tool's landing dir — kept as-is)
│   │   ├── .gitkeep
│   │   └── extracted_data.csv
│   ├── transform/                 (ETL tool's landing dir — kept as-is)
│   │   └── .gitkeep
│   ├── payments.csv
│   ├── ratings.csv
│   ├── rides.csv
│   ├── users.csv
│   └── vehicles.csv
├── mcp-server/                ← our only code — NOT YET CREATED
│   ├── server.py              ← FastMCP entrypoint, registers the 4 tools
│   ├── sql_logic.py           ← generation logic, ported from old repo's sql_analyst.py
│   ├── etl_logic.py           ← generation logic, ported from old repo's etl_analyst.py
│   ├── database.py            ← Postgres connection util, ported from old repo's utils/database.py
│   └── requirements.txt
├── trueforge/                 ← harness runtime — NOT YET CREATED, next step
│                                  run via `npx @truefoundry/trueforge`
│                                  not hand-edited — configured only
└── PROJECT.md                 ← this file
```

**Current status:** `data/` is in place. `mcp-server/` and `trueforge/` do not
exist yet — bringing up TrueForge is the next step, before any tool code is
written.

**Reference-only source:** `anshlambagit/AI_Data_Agent` (old LangGraph repo).
We port generation *logic* out of it. We do not port its router, its safety
check, or its execution wrapping — those are exactly what TrueForge replaces.

---

## The 4 tools (the entire surface our code exposes)

| Tool | Input | Output | Does it decide anything? | TrueForge policy |
|---|---|---|---|---|
| `generate_sql` | `question: str` | SQL query text | No — pure generation | none |
| `execute_sql` | `query: str` | query result rows | No — just runs it | **approval-required** |
| `generate_transform` | `instructions: str` | pandas code text | No — pure generation | none |
| `execute_transform` | `code: str` | execution result | No — just runs it | **sandboxed (Daytona)**, approval-required |

No router tool. No `run_data_pipeline` mega-tool. TrueForge's own agent loop
sees all 4 tool descriptions and decides which to call based on the user's
message — that decision is the harness's job now, not ours.

### What happened to Data Agent / SQL Analyst / ETL Analyst?
They still exist as **generation logic**, not as a runtime orchestrator:
- Old Data Agent's router node → deleted. TrueForge's tool-selection replaces it.
- Old SQL Analyst's curate → schema-fetch → SQL-gen steps → survive inside `generate_sql`, stopped before execution.
- Old SQL Analyst's execution + keyword `is_safe` check → deleted. Replaced by `execute_sql` (no internal safety logic) + TrueForge's approval gate.
- Old ETL Analyst's code-gen steps → survive inside `generate_transform`, stopped before execution.
- Old ETL Analyst's own sandboxing → deleted. Replaced by `execute_transform` running inside TrueForge's Daytona sandbox.

---

## Build order
1. Copy `data/` folder from old repo into new root. Nothing else copied.
2. `npx @truefoundry/trueforge` — bring up harness locally (standalone/SQLite mode).
3. Build `mcp-server/` with the 4 tools above, using `FastMCP`.
4. Register `mcp-server` in TrueForge's MCP config.
5. In TrueForge config, mark `execute_sql` and `execute_transform` as approval-required; confirm `execute_transform` runs in the Daytona sandbox, not a local subprocess.
6. Test in TrueForge's chat UI: ask a data question → confirm tool selection → confirm approval prompt fires before execution → confirm result renders in TrueForge's generative UI.
7. Write short README: architecture diagram + one screenshot of the approval prompt firing.

## Non-goals (explicitly out of scope, don't rebuild these)
- No custom safety/validation logic in our code — TrueForge's approval gate is the safety layer.
- No custom sandboxing — Daytona via TrueForge is the sandbox.
- No session/conversation state in our code — TrueForge's persistent sessions handle it.
- No UI — TrueForge's chat UI + generative UI is the UI.