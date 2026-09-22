"""The three *persistent* memory stores, each backed by one SQLite table.

Working memory is deliberately absent here: it lives in the LangGraph state and
its checkpointer, because it is scoped to a single thread and dies with it.
That asymmetry is the first thing worth noticing.

    EpisodicStore   -- what happened, and when. Append-only, retrieved by
                       similarity *blended with recency*.
    SemanticStore   -- what is true, timeless. Deduplicated on write, retrieved
                       by similarity alone.
    ProceduralStore -- how to behave. A handful of rules, retrieved wholesale
                       and injected into the system prompt.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config, llm

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT NOT NULL,
    ts          TEXT NOT NULL,
    user_said   TEXT NOT NULL,
    agent_said  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    consolidated INTEGER NOT NULL DEFAULT 0,
    embedding   BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    origin      TEXT NOT NULL,           -- 'turn' or 'consolidation'
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    seen_count  INTEGER NOT NULL DEFAULT 1,
    embedding   BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    evidence    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.MEMORY_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------------------------------
# Episodic
# --------------------------------------------------------------------------

@dataclass
class Episode:
    id: int
    thread_id: str
    ts: str
    user_said: str
    agent_said: str
    summary: str
    score: float = 0.0

    def age_days(self) -> float:
        then = datetime.fromisoformat(self.ts)
        return max((datetime.now(timezone.utc) - then).total_seconds() / 86400.0, 0.0)


class EpisodicStore:
    """Append-only log of things that happened, with timestamps.

    Never deduplicated: two identical conversations on different days are two
    different memories. That is the defining property of episodic memory.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record(self, thread_id: str, user_said: str, agent_said: str, summary: str) -> int:
        vec = llm.embed(f"{summary}\n{user_said}")
        cur = self.conn.execute(
            "INSERT INTO episodes (thread_id, ts, user_said, agent_said, summary, embedding)"
            " VALUES (?,?,?,?,?,?)",
            (thread_id, _now(), user_said, agent_said, summary, _to_blob(vec)),
        )
        self.conn.commit()
        return cur.lastrowid

    def recall(self, query: str, k: int = None, exclude_thread: str | None = None) -> list[Episode]:
        """Similarity blended with recency, the way human episodic recall works.

        A merely-similar memory from today can outrank a very-similar one from
        last month. Tune with RECENCY_WEIGHT.
        """
        k = k or config.EPISODIC_TOP_K
        rows = self.conn.execute("SELECT * FROM episodes").fetchall()
        if not rows:
            return []
        qv = llm.embed(query)
        scored: list[Episode] = []
        for row in rows:
            if exclude_thread and row["thread_id"] == exclude_thread:
                continue
            ep = Episode(
                id=row["id"], thread_id=row["thread_id"], ts=row["ts"],
                user_said=row["user_said"], agent_said=row["agent_said"],
                summary=row["summary"],
            )
            sim = float(qv @ _from_blob(row["embedding"]))
            freshness = 1.0 / (1.0 + ep.age_days())
            ep.score = sim + config.RECENCY_WEIGHT * freshness
            scored.append(ep)
        scored.sort(key=lambda e: e.score, reverse=True)
        return scored[:k]

    def all(self) -> list[Episode]:
        rows = self.conn.execute("SELECT * FROM episodes ORDER BY id").fetchall()
        return [
            Episode(id=r["id"], thread_id=r["thread_id"], ts=r["ts"],
                    user_said=r["user_said"], agent_said=r["agent_said"], summary=r["summary"])
            for r in rows
        ]

    def unconsolidated(self) -> list[Episode]:
        rows = self.conn.execute(
            "SELECT * FROM episodes WHERE consolidated = 0 ORDER BY id"
        ).fetchall()
        return [
            Episode(id=r["id"], thread_id=r["thread_id"], ts=r["ts"],
                    user_said=r["user_said"], agent_said=r["agent_said"], summary=r["summary"])
            for r in rows
        ]

    def backdate(self, episode_id: int, days: float) -> None:
        """Shift an episode into the past. Only used by the demo scripts, so a
        multi-day narrative can be replayed in a few seconds."""
        row = self.conn.execute(
            "SELECT ts FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        if row is None:
            return
        ts = datetime.fromisoformat(row["ts"]) - timedelta(days=days)
        self.conn.execute(
            "UPDATE episodes SET ts = ? WHERE id = ?",
            (ts.isoformat(timespec="seconds"), episode_id),
        )
        self.conn.commit()

    def mark_consolidated(self, ids: list[int]) -> None:
        self.conn.executemany(
            "UPDATE episodes SET consolidated = 1 WHERE id = ?", [(i,) for i in ids]
        )
        self.conn.commit()


# --------------------------------------------------------------------------
# Semantic
# --------------------------------------------------------------------------

@dataclass
class Fact:
    id: int
    text: str
    origin: str
    seen_count: int
    updated_at: str
    score: float = 0.0


class SemanticStore:
    """Timeless statements, stripped of the episode that produced them.

    Writes are deduplicated: learning the same fact twice bumps a counter
    rather than creating a second copy. Nothing here carries a timestamp that
    matters to retrieval.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _nearest(self, vec: np.ndarray) -> tuple[sqlite3.Row | None, float]:
        rows = self.conn.execute("SELECT * FROM facts").fetchall()
        best, best_sim = None, -1.0
        for row in rows:
            sim = float(vec @ _from_blob(row["embedding"]))
            if sim > best_sim:
                best, best_sim = row, sim
        return best, best_sim

    def upsert(self, text: str, origin: str = "turn") -> tuple[int, bool]:
        """Returns (fact_id, was_new)."""
        vec = llm.embed(text)
        near, sim = self._nearest(vec)
        if near is not None and sim >= config.FACT_DEDUP_THRESHOLD:
            self.conn.execute(
                "UPDATE facts SET seen_count = seen_count + 1, updated_at = ? WHERE id = ?",
                (_now(), near["id"]),
            )
            self.conn.commit()
            return near["id"], False
        cur = self.conn.execute(
            "INSERT INTO facts (text, origin, created_at, updated_at, embedding)"
            " VALUES (?,?,?,?,?)",
            (text, origin, _now(), _now(), _to_blob(vec)),
        )
        self.conn.commit()
        return cur.lastrowid, True

    def recall(self, query: str, k: int = None) -> list[Fact]:
        k = k or config.SEMANTIC_TOP_K
        rows = self.conn.execute("SELECT * FROM facts").fetchall()
        if not rows:
            return []
        qv = llm.embed(query)
        facts = []
        for row in rows:
            f = Fact(id=row["id"], text=row["text"], origin=row["origin"],
                     seen_count=row["seen_count"], updated_at=row["updated_at"])
            f.score = float(qv @ _from_blob(row["embedding"]))
            facts.append(f)
        facts.sort(key=lambda f: f.score, reverse=True)
        return facts[:k]

    def all(self) -> list[Fact]:
        rows = self.conn.execute("SELECT * FROM facts ORDER BY id").fetchall()
        return [
            Fact(id=r["id"], text=r["text"], origin=r["origin"],
                 seen_count=r["seen_count"], updated_at=r["updated_at"])
            for r in rows
        ]


# --------------------------------------------------------------------------
# Procedural
# --------------------------------------------------------------------------

@dataclass
class Rule:
    id: int
    text: str
    evidence: str
    updated_at: str


class ProceduralStore:
    """Learned behaviour, held as a small set of rules.

    Note what is *missing*: no embeddings and no similarity search. Procedural
    memory is small and always relevant, so it is loaded wholesale into the
    system prompt every turn. Retrieving it "when relevant" would defeat it --
    an agent that only remembers to be concise when asked about concision has
    not learned anything.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, text: str, evidence: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO rules (text, evidence, created_at, updated_at) VALUES (?,?,?,?)",
            (text, evidence, _now(), _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def revise(self, rule_id: int, text: str, evidence: str) -> None:
        self.conn.execute(
            "UPDATE rules SET text = ?, evidence = ?, updated_at = ? WHERE id = ?",
            (text, evidence, _now(), rule_id),
        )
        self.conn.commit()

    def retire(self, rule_id: int) -> None:
        self.conn.execute("UPDATE rules SET active = 0 WHERE id = ?", (rule_id,))
        self.conn.commit()

    def active(self) -> list[Rule]:
        rows = self.conn.execute(
            "SELECT * FROM rules WHERE active = 1 ORDER BY id"
        ).fetchall()
        return [Rule(id=r["id"], text=r["text"], evidence=r["evidence"],
                     updated_at=r["updated_at"]) for r in rows]


@dataclass
class Memory:
    """Handle bundling the three persistent stores over one connection."""
    conn: sqlite3.Connection
    episodic: EpisodicStore
    semantic: SemanticStore
    procedural: ProceduralStore

    @classmethod
    def open(cls, path: Path | None = None) -> "Memory":
        conn = connect(path)
        return cls(conn, EpisodicStore(conn), SemanticStore(conn), ProceduralStore(conn))

    def close(self) -> None:
        self.conn.close()

    def wipe(self) -> None:
        self.conn.executescript(
            "DELETE FROM episodes; DELETE FROM facts; DELETE FROM rules;"
        )
        self.conn.commit()
