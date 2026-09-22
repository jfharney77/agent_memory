# memory_lab

Four kinds of agent memory, in one LangGraph agent, each one switchable so you
can watch what breaks when it is missing.

The agent is a study assistant called Sage. The interesting part is not Sage;
it is the four stores behind it and the fact that they disagree about what
memory is for.

## The four systems

|              | holds                       | lifetime            | write policy                | read policy                        |
|--------------|-----------------------------|---------------------|-----------------------------|------------------------------------|
| **working**  | the current conversation    | one thread          | append, drop the oldest     | all of it, always                  |
| **episodic** | what happened, and when     | forever             | append-only, never merged   | similarity blended with recency    |
| **semantic** | what is true about the user | forever             | upsert, near-duplicates merge | similarity, time ignored         |
| **procedural** | how to behave             | until contradicted  | edit in place: add/revise/retire | all of it, always             |

Those last two columns are the whole lesson. Episodic and semantic memory can
be built from the very same exchange, and they still differ in every decision
that follows, because they answer different questions:

- *"What were we doing last Tuesday?"* — only episodic memory can answer this.
  Semantic memory deliberately threw the occasion away.
- *"When is my exam?"* — semantic memory answers instantly. Episodic memory
  would have to retrieve the conversation where you mentioned it and hope it
  ranked highly.
- *"Stop giving me bullet lists"* — neither. That is procedural memory, and if
  you file it as a fact it will only surface when you ask about bullet lists,
  which is exactly when you no longer need it.

## The graph

```
START ─> recall ─> respond ─> remember ─> reflect ─> END
          │          │           │           │
          │          │           │           └── procedural: did the user
          │          │           │               correct HOW I answer?
          │          │           └── episodic: log the occasion
          │          │               semantic: extract durable facts
          │          └── working memory (state) + retrieved context
          └── read semantic + episodic + procedural
```

`recall` and `remember`/`reflect` bracket the model call. Working memory needs
no read step — it is already in the graph state, persisted per `thread_id` by
LangGraph's SQLite checkpointer. The other three live in `memory.db`, which is
why you can delete every checkpoint and Sage still knows who you are.

Two LLM calls do the writing. `remember` produces the episode summary and the
semantic facts in one JSON call, since both are read off the same exchange.
`reflect` gets its own pass because it is looking for something different — a
complaint about form — and usually finds nothing.

## Setup

Needs a running Ollama. Nothing else phones home.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # then check OLLAMA_BASE_URL
.venv/bin/ollama --version    # (or wherever your Ollama lives)
```

From WSL, Ollama on the Windows host is usually at the nameserver address:

```bash
grep nameserver /etc/resolv.conf     # -> 172.30.48.1, so http://172.30.48.1:11434
```

Models used, both small:

```bash
ollama pull qwen2.5              # chat
ollama pull granite-embedding:30m  # 384-dim embeddings
```

## The demos

Run them in order; each one is a self-contained story with its own throwaway
database.

```bash
.venv/bin/python demo/run_all.py        # all five, a few minutes
.venv/bin/python demo/run_all.py 3      # just the semantic one
```

1. **`01_working_memory.py`** — tell Sage a name, bury it under six turns of
   filler, ask again. Then switch threads and watch even the recent turns
   vanish. Working memory is a window, not a record.
2. **`02_episodic.py`** — four seeded sessions over three weeks. Shows why
   retrieval scores `similarity + recency`: *"what did we do last time?"* has
   almost no lexical overlap with anything, so recency has to carry it.
3. **`03_semantic.py`** — the same exam date, stated twice in different words,
   becomes one fact with a counter and two separate episodes. Ends with an A/B:
   the same question with semantic memory off, then on.
4. **`04_procedural.py`** — measures answer length before feedback, after
   feedback, and with the learned rule disabled. On a local 7B that is roughly
   1200 → 200 → 1800 characters. Then retracts the feedback and watches the
   reflector revise rather than append.
5. **`05_consolidation.py`** — six sessions, none of which says "this user
   keeps confusing sign conventions", consolidated into a fact that does.

## The web app

Same five demos, launched by a button, output streamed into the page as it is
produced.

```bash
./start.sh        # then open http://localhost:5180
./stop.sh
```

The demos are run as subprocesses and their stdout is piped to the browser over
SSE, ANSI codes intact — the page parses them back into the same colour coding
the terminal uses, so what you see in the browser is exactly what the terminal
shows. A demo that hangs cannot take the server with it, and Stop kills the
subprocess rather than just hiding the output.

The header reports whether Ollama is actually reachable and whether both models
are pulled, since that is the only way these demos can fail for reasons that
have nothing to do with memory.

Ports are pinned: backend 8077, frontend 5180. Both are deliberately off the
defaults, which tend to be occupied.

## The REPL

```bash
.venv/bin/python -m memory_lab.cli
.venv/bin/python -m memory_lab.cli --thread tuesday --off semantic
```

Every turn prints what was recalled and what was written. Slash commands:

```
/stores            all four systems, side by side
/recall <query>    query long-term memory without invoking the model
/off <kind>...     ablate: working episodic semantic procedural
/on <kind>...      restore
/thread <id>       new conversation; working memory resets, the rest persists
/consolidate       run the episodic -> semantic pass now
/wipe              erase long-term memory
```

The fastest way to feel the difference: tell it something about yourself,
`/thread` somewhere new, ask about it (it knows), then `/off semantic` and ask
again (it does not).

## Layout

```
memory_lab/
  config.py       every tunable, with the knobs that matter at the top
  llm.py          Ollama chat / JSON chat / embeddings, ~80 lines
  stores.py       the three persistent stores, one SQLite table each
  prompts.py      all four prompts in one file
  agent.py        the graph: recall -> respond -> remember -> reflect
  consolidate.py  episodic -> semantic
  runtime.py      opens the two databases
  cli.py          the REPL
  server.py       FastAPI: lists the demos, runs one, streams its stdout
  display.py      ANSI formatting
demo/             the five scripted narratives
frontend/         React app: a button per demo, output streamed in below it
  src/ansi.js     turns the demos' terminal colours back into spans
  src/Output.jsx  the streaming log panel
start.sh          runs both halves
```

## Knobs worth turning

In `.env` or `config.py`:

- `WORKING_MEMORY_TURNS` (6) — shrink to 2 and demo 01 falls apart in one turn.
- `FACT_DEDUP_THRESHOLD` (0.88) — drop to 0.7 and unrelated facts start merging;
  raise to 0.97 and every rephrasing becomes a new row.
- `RECENCY_WEIGHT` (0.15) — set to 0 for pure similarity and re-run demo 02;
  *"what did we do last time?"* stops working.
- `SEMANTIC_TOP_K` / `EPISODIC_TOP_K` — the retrieval budget, i.e. how much of
  the context window memory is allowed to spend.

## What this deliberately leaves out

Worth knowing about, skipped to keep the code readable:

- **Forgetting.** Nothing here ever decays or evicts. A real system needs a
  policy, and "never delete" is a policy with a cost.
- **Conflict resolution.** If you say your exam moved, the old fact stays and
  both get retrieved. Demo 04 shows the same problem for rules. Fixing it well
  means versioned facts with supersession, not just an overwrite.
- **Provenance and trust.** Facts record `origin` but nothing weighs a directly
  stated fact above an inferred one.
- **Scale.** Retrieval loads every row and does the dot products in numpy. Fine
  to a few thousand memories, then you want a real vector index.
- **Namespacing.** One user. LangGraph's `BaseStore` gives you `(user_id, kind)`
  namespaces for free if you want the production version of this.
