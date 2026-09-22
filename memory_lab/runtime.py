"""Opening the lab: one SQLite file for long-term memory, one for checkpoints."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from . import config
from .agent import build_agent
from .stores import Memory


@contextmanager
def lab(db: Path | None = None):
    """Yields (memory, app).

    Working memory is persisted by the checkpointer keyed on thread_id; the
    other three live in the memory database. Two files, because they have
    genuinely different lifetimes -- you can delete every checkpoint and the
    agent still knows who you are.
    """
    db = Path(db or config.MEMORY_DB)
    ckpt_path = db.with_name(db.stem + "_checkpoints.db")
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    memory = Memory.open(db)
    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    try:
        saver = SqliteSaver(conn)
        yield memory, build_agent(memory, saver)
    finally:
        conn.close()
        memory.close()
