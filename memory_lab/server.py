"""HTTP front door for the demos.

Each demo is run as its own subprocess and its stdout streamed to the browser
line by line over SSE. Running them out-of-process rather than importing them
keeps the demos honest: what the web page shows is exactly what the terminal
shows, ANSI codes and all, and a demo that hangs cannot take the server with it.

    .venv/bin/python -m memory_lab.server
"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import config

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT / "demo"


@dataclass(frozen=True)
class Demo:
    id: str
    number: int
    title: str
    kind: str
    tagline: str
    watch_for: str
    script: str
    minutes: str


DEMOS: tuple[Demo, ...] = (
    Demo(
        id="working", number=1, title="The window that forgets", kind="working",
        tagline="Tell the agent a name, bury it under six turns of filler, ask again.",
        watch_for="The name falls out of the window with no eviction event. Then a "
                  "new thread starts empty even though the conversation was minutes ago.",
        script="01_working_memory.py", minutes="~1 min",
    ),
    Demo(
        id="episodic", number=2, title="What happened, and when", kind="episodic",
        tagline="Four seeded sessions over three weeks, queried three different ways.",
        watch_for="\"What did we do last time?\" shares almost no wording with any "
                  "episode. Recency, not similarity, is what retrieves it.",
        script="02_episodic.py", minutes="~1 min",
    ),
    Demo(
        id="semantic", number=3, title="What is true, minus the occasion", kind="semantic",
        tagline="The same exam date, stated twice in different words.",
        watch_for="One fact with a seen-count, two separate episodes. Same input, "
                  "opposite write policy. Ends with the question asked with semantic "
                  "memory off, then on.",
        script="03_semantic.py", minutes="~2 min",
    ),
    Demo(
        id="procedural", number=4, title="How to behave", kind="procedural",
        tagline="Answer length measured before feedback, after it, and with the rule ablated.",
        watch_for="Roughly 1400 -> 150 -> 2000 characters. Then the feedback is "
                  "retracted and the reflector revises the rule instead of appending.",
        script="04_procedural.py", minutes="~2 min",
    ),
    Demo(
        id="consolidation", number=5, title="Episodes becoming facts", kind="semantic",
        tagline="Six sessions, none of which states the pattern that all six show.",
        watch_for="The same question asked before and after consolidation. The "
                  "episodes survive the pass untouched.",
        script="05_consolidation.py", minutes="~2 min",
    ),
)

BY_ID = {d.id: d for d in DEMOS}

app = FastAPI(title="memory_lab")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5180", "http://127.0.0.1:5180"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/demos")
def list_demos() -> dict:
    return {"demos": [asdict(d) for d in DEMOS]}


@app.get("/api/health")
def health() -> dict:
    """Does the thing these demos actually depend on answer?"""
    try:
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=4)
        resp.raise_for_status()
        installed = {m["name"] for m in resp.json().get("models", [])}
    except requests.RequestException as exc:
        return {
            "ok": False,
            "base_url": config.OLLAMA_BASE_URL,
            "detail": f"No answer from Ollama at {config.OLLAMA_BASE_URL}. "
                      f"Check OLLAMA_BASE_URL in .env. ({exc.__class__.__name__})",
        }

    def present(name: str) -> bool:
        return name in installed or f"{name}:latest" in installed

    missing = [m for m in (config.CHAT_MODEL, config.EMBED_MODEL) if not present(m)]
    return {
        "ok": not missing,
        "base_url": config.OLLAMA_BASE_URL,
        "chat_model": config.CHAT_MODEL,
        "embed_model": config.EMBED_MODEL,
        "detail": "" if not missing
                  else f"Ollama is up but missing: {', '.join(missing)}. "
                       f"Pull them with: ollama pull {missing[0]}",
    }


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@app.get("/api/run/{demo_id}")
async def run(demo_id: str, request: Request) -> StreamingResponse:
    demo = BY_ID.get(demo_id)

    async def stream():
        if demo is None:
            yield _sse("error", {"detail": f"No demo called {demo_id!r}."})
            return

        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", str(DEMO_DIR / demo.script),
            cwd=str(ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        yield _sse("start", {"demo": demo.id, "pid": proc.pid})
        try:
            assert proc.stdout is not None
            while True:
                if await request.is_disconnected():
                    proc.terminate()
                    yield _sse("done", {"code": None, "cancelled": True})
                    return
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"   # nothing printed yet; hold the connection
                    continue
                if not raw:
                    break
                yield _sse("line", {"text": raw.decode("utf-8", "replace").rstrip("\n")})
            code = await proc.wait()
            yield _sse("done", {"code": code, "cancelled": False})
        finally:
            if proc.returncode is None:
                proc.kill()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8077, log_level="warning")


if __name__ == "__main__":
    main()
