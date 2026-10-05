# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`memory_lab` is a teaching project: one LangGraph agent ("Sage", a study assistant) wired to four
distinct memory systems, each independently ablatable so the failure mode of a missing system is
observable. The agent is not the point — the four stores and their conflicting write/read policies
are. `README.md` explains the pedagogy; this file covers the mechanics.

Everything runs against a local Ollama. No network calls leave the machine.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fix OLLAMA_BASE_URL (WSL: grep nameserver /etc/resolv.conf)

.venv/bin/python demo/run_all.py        # all five demos, several minutes
.venv/bin/python demo/run_all.py 3      # just demo 3 (args are demo numbers)
.venv/bin/python demo/03_semantic.py    # equivalently, run one directly

.venv/bin/python -m memory_lab.cli
.venv/bin/python -m memory_lab.cli --thread tuesday --off semantic --db /tmp/scratch.db

./start.sh        # backend + React app; open http://localhost:5180
./stop.sh         # kills both process groups, clears .run/*.pid
```

Required models: `ollama pull qwen2.5` (chat) and `ollama pull granite-embedding:30m` (384-dim
embeddings).

The Python side has no test suite or linter. The demos *are* the regression tests: each one is a
scripted narrative with an expected qualitative outcome stated in its module docstring (e.g. demo 04
expects answer length to go ~1200 → 200 → 1800 chars). Changing memory behaviour means re-running
the affected demo and checking the narrative still holds. Outcomes are LLM-generated and therefore
not bit-stable — judge them by shape, not by exact text.

The frontend has no tests either, but it does have a linter and a build, and both are expected to
stay clean:

```bash
cd frontend && npm run lint && npm run build
```

## Architecture

### The graph

`memory_lab/agent.py` builds `recall → respond → remember → reflect`, compiled with a
`SqliteSaver` checkpointer. The nodes bracket the single user-facing model call:

- `recall` reads semantic + episodic + procedural. Working memory has no read step because it is
  already in the graph state.
- `respond` assembles a layered system prompt (persona, then rules, then facts, then episodes) and
  calls the model.
- `remember` makes **one** JSON call producing both the episode summary and the semantic facts,
  because both are read off the same exchange.
- `reflect` gets its own pass — it is looking for a complaint about *form*, not content, and
  usually finds nothing.

So one turn costs up to three LLM calls. That is why the demos take minutes.

`Memory` is closed over by `build_agent` rather than stored in state: SQLite connections are not
checkpointable. `enabled: list[str]` in state is the ablation switch; every node intersects it with
`ALL_MEMORIES` before touching anything.

### The four stores

Working memory is the `messages` key in `AgentState`, bounded by the `window()` reducer
(`WORKING_MEMORY_TURNS * 2` messages) and persisted per `thread_id` by the checkpointer. It is the
only system that lives in graph state.

The other three are in `memory_lab/stores.py`, one SQLite table each over a single connection
bundled by the `Memory` dataclass. Their policies are deliberately incompatible, and edits that
blur the distinctions defeat the project:

| store | writes | reads |
|---|---|---|
| `EpisodicStore` | append-only, never merged | `sim + RECENCY_WEIGHT * 1/(1+age_days)` |
| `SemanticStore` | upsert; nearest neighbour ≥ `FACT_DEDUP_THRESHOLD` bumps `seen_count` instead | similarity only, time ignored |
| `ProceduralStore` | edits in place: add / revise / retire | `active()` — **all** rules, no embeddings, no search |

Procedural memory having no retrieval at all is intentional: rules are always relevant, and an
agent that only recalls "be concise" when asked about concision has learned nothing.

### Two databases, two lifetimes

`runtime.lab()` opens `memory.db` (the three persistent stores) and `memory_checkpoints.db`
(working memory), derived by name in both `config.py` and `runtime.py`. Deleting every checkpoint
leaves the agent still knowing who you are — that asymmetry is the demonstration.

### Consolidation

`consolidate.py` is the offline episodic → semantic pass: it reads rows with `consolidated = 0`,
asks for patterns only visible across the batch, upserts them with `origin="consolidation"`, and
marks the episodes digested. Default `min_episodes=3`; the CLI's `/consolidate` passes 1.

### The web app

`memory_lab/server.py` (FastAPI, port **8077**) and `frontend/` (Vite + React, port **5180**).
Three endpoints: `/api/demos` (static metadata, one `Demo` dataclass per script), `/api/health`
(does Ollama answer, are both models pulled), and `/api/run/{id}` (SSE).

Demos run as **subprocesses**, not imports. Two reasons, both load-bearing: the page then shows
exactly what the terminal shows, and a wedged demo cannot take the server down. `asyncio`
subprocess + `request.is_disconnected()` means closing the tab terminates the run; a 1-second
`readline` timeout emits an SSE keep-alive so the connection survives the quiet stretches while a
local model thinks.

ANSI codes are deliberately *not* stripped server-side. `frontend/src/ansi.js` parses the handful
the demos emit (0/1/2, 32/33/35/36) back into spans so the browser keeps the CLI's colour coding —
green semantic, magenta episodic, and so on. If you add a colour to `display.py`, add it there too.

Ports are pinned and `strictPort` is set. This machine runs dozens of dev servers; 8000 and 5173
were both occupied during development. `start.sh` refuses to start when either port is taken rather
than reporting success while a foreign process answers the health check — that failure happened and
the guard is why it cannot happen silently again. Each service starts under `setsid` so `stop.sh`
can kill the whole group; npm → vite → node means killing the parent alone orphans the process
holding the port.

### Embeddings

`llm.embed` unit-normalises, so cosine similarity is a plain dot product (`qv @ vec`) and vectors
are stored as raw float32 blobs. Retrieval is `SELECT *` plus numpy over every row — fine at this
scale, and noted in the README as a deliberate omission.

## Conventions

- All prompts live in `prompts.py`, all tunables in `config.py` (env-overridable via `.env`). Do not
  inline either into the nodes.
- `llm.chat_json` returns `None` when the model wanders off JSON; callers use `... or {}` and
  tolerate missing keys. Keep new LLM-parsing code equally defensive — these are small local models.
- Comments here carry the teaching load and explain *why a policy differs from its neighbour*, not
  what the line does. Match that register.
- `EpisodicStore.backdate()` exists only so demos can replay a three-week narrative in seconds.
- Demo scripts import via `_common.py`, which puts the repo root on `sys.path` and gives each demo
  a throwaway database under `demo/.sandbox/` (wiped per run).
- Adding a demo means: the script in `demo/`, an entry in `run_all.DEMOS`, and an entry in
  `server.DEMOS` (whose `watch_for` is the one place the expected outcome is stated for a reader
  who will not open the source).
- The frontend has no state manager and no UI library, and does not need either. Keep it that way.

## Where things stand (2026-10-05)

Complete and verified end to end. Nothing is half-finished or stubbed.

- Four memory systems, five demos, CLI, consolidation pass — all run against local Ollama
  (`qwen2.5` + `granite-embedding:30m` at `172.30.48.1:11434`).
- Web app verified in a real browser, not just by building: clicking Run streams the output in,
  colours render, Stop kills the subprocess, start/stop cycle leaves no orphans.
- Demo 04's measured numbers on this hardware were 1409 → 145 → 2077 chars (baseline → learned
  rule → rule ablated). Demo 05 consolidated six episodes into two cross-episode facts.
- Pushed to `git@github.com:jfharney77/agent_memory.git`, two commits. **The remote is SSH on
  purpose** — the HTTPS token in `~/.config/gh/hosts.yml` is expired, so `gh` commands and HTTPS
  pushes will fail until `gh auth login` is re-run. SSH works.

### Known rough edges, in the order worth fixing

1. **Procedural rules accumulate contradictions.** Demo 04 can end holding both "keep answers
   detailed" and "keep explanations concise". This is called out honestly in the demo as the
   characteristic failure of the store, not hidden — but a periodic reconciliation pass over
   `rules`, the equivalent of what `consolidate.py` does for facts, is the obvious next feature.
2. **Nothing ever forgets.** No decay, no eviction, no supersession. If the user says their exam
   moved, both the old and new fact persist and both get retrieved. Fixing this properly means
   versioned facts, not an overwrite.
3. **Retrieval is `SELECT *` + numpy.** Fine to a few thousand rows. A real index is the point at
   which this stops being a teaching project.
4. **One user, no namespacing.** LangGraph's `BaseStore` gives `(user_id, kind)` namespaces for
   free if this ever needs to be multi-tenant.

All four are listed in `README.md` under "What this deliberately leaves out", so they are
documented omissions rather than oversights. Do not quietly fix one without updating that section.
