"""Shared scaffolding for the demo scripts.

Each demo gets its own throwaway database so it can be run in any order and
tells a self-contained story.
"""
from __future__ import annotations

import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory_lab.agent import turn  # noqa: E402
from memory_lab.display import BOLD, DIM, RESET, heading, show_recall, show_writes  # noqa: E402
from memory_lab.runtime import lab  # noqa: E402

SANDBOX = Path(__file__).resolve().parent / ".sandbox"


@contextmanager
def fresh_lab(name: str):
    """A clean database, wiped on every run so demos are reproducible."""
    SANDBOX.mkdir(exist_ok=True)
    for p in SANDBOX.glob(f"{name}*"):
        p.unlink()
    with lab(SANDBOX / f"{name}.db") as pair:
        yield pair


def title(text: str) -> None:
    print(f"\n{BOLD}{'=' * 72}\n{text}\n{'=' * 72}{RESET}")


def note(text: str) -> None:
    print(f"\n{DIM}{text}{RESET}")


def say(app, thread: str, text: str, enabled=None, show=("recall", "reply", "writes")) -> str:
    """One turn, narrated."""
    if show:
        print(f"\n{BOLD}[{thread}] you >{RESET} {text}")
    reply, trace = turn(app, thread, text, enabled)
    if "recall" in show:
        print(heading("recalled from memory"))
        print(show_recall(trace.recalled))
    if "reply" in show:
        print(heading("sage"))
        print(reply)
    if "writes" in show:
        print(heading("written to memory"))
        print(show_writes(trace.written))
    return reply


def clean() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
