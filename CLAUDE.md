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
```

Required models: `ollama pull qwen2.5` (chat) and `ollama pull granite-embedding:30m` (384-dim
embeddings).

There is no test suite, linter, or build step. The demos *are* the regression tests: each one is a
scripted narrative with an expected qualitative outcome stated in its module docstring (e.g. demo 04
expects answer length to go ~1200 → 200 → 1800 chars). Changing memory behaviour means re-running
the affected demo and checking the narrative still holds. Outcomes are LLM-generated and therefore
not bit-stable — judge them by shape, not by exact text.

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
