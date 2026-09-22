"""Interactive REPL. Every turn shows what was read from memory and what was
written back to it.

    python -m memory_lab.cli                 # start a chat
    python -m memory_lab.cli --thread day2   # a different conversation
    python -m memory_lab.cli --off working   # ablate a memory system

Slash commands are listed by /help.
"""
from __future__ import annotations

import argparse
import sys

from . import config
from .agent import ALL_MEMORIES, turn
from .consolidate import consolidate
from .display import BOLD, DIM, RESET, heading, show_recall, show_stores, show_writes
from .runtime import lab

HELP = f"""{BOLD}commands{RESET}
  /stores            show all four memory systems
  /recall <query>    query long-term memory without talking to the model
  /off <kind>...     disable memory systems: working episodic semantic procedural
  /on <kind>...      re-enable them
  /thread <id>       switch conversation (clears working memory, keeps the rest)
  /consolidate       run episodic -> semantic consolidation now
  /wipe              erase all long-term memory
  /help  /quit
"""


def working_messages(app, thread_id: str) -> list[dict]:
    snap = app.get_state({"configurable": {"thread_id": thread_id}})
    return (snap.values or {}).get("messages", [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Chat with an agent that has four memory systems.")
    ap.add_argument("--thread", default="session-1")
    ap.add_argument("--off", nargs="*", default=[], choices=list(ALL_MEMORIES))
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)

    enabled = [m for m in ALL_MEMORIES if m not in args.off]
    thread = args.thread

    with lab(args.db) as (memory, app):
        print(f"{BOLD}memory_lab{RESET}  model={config.CHAT_MODEL}  thread={thread}")
        print(f"{DIM}enabled: {', '.join(enabled) or 'none'}   /help for commands{RESET}")
        while True:
            try:
                line = input(f"\n{BOLD}you{RESET} > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line:
                continue

            if line.startswith("/"):
                cmd, _, rest = line[1:].partition(" ")
                rest = rest.strip()
                if cmd in ("quit", "exit", "q"):
                    return 0
                elif cmd == "help":
                    print(HELP)
                elif cmd == "stores":
                    print(show_stores(memory, working_messages(app, thread)))
                elif cmd == "recall":
                    if not rest:
                        print("usage: /recall <query>")
                        continue
                    print(show_recall({
                        "procedural": [{"id": r.id, "text": r.text}
                                       for r in memory.procedural.active()],
                        "semantic": [{"id": f.id, "text": f.text, "score": round(f.score, 3),
                                      "seen_count": f.seen_count, "origin": f.origin}
                                     for f in memory.semantic.recall(rest)],
                        "episodic": [{"id": e.id, "ts": e.ts, "summary": e.summary,
                                      "score": round(e.score, 3),
                                      "age_days": round(e.age_days(), 2)}
                                     for e in memory.episodic.recall(rest)],
                    }))
                elif cmd in ("off", "on"):
                    kinds = [k for k in rest.split() if k in ALL_MEMORIES]
                    if not kinds:
                        print(f"usage: /{cmd} {' | '.join(ALL_MEMORIES)}")
                        continue
                    if cmd == "off":
                        enabled = [m for m in enabled if m not in kinds]
                    else:
                        enabled = [m for m in ALL_MEMORIES if m in enabled or m in kinds]
                    print(f"{DIM}enabled: {', '.join(enabled) or 'none'}{RESET}")
                elif cmd == "thread":
                    if not rest:
                        print(f"current thread: {thread}")
                        continue
                    thread = rest
                    print(f"{DIM}switched to thread {thread} -- working memory is now "
                          f"whatever that thread last held{RESET}")
                elif cmd == "consolidate":
                    result = consolidate(memory, min_episodes=1)
                    if result["status"] == "skipped":
                        print(f"{DIM}{result['reason']}{RESET}")
                    else:
                        print(f"{DIM}read {result['episodes']} episodes{RESET}")
                        print(show_writes({"semantic": result["facts"]}))
                elif cmd == "wipe":
                    memory.wipe()
                    print(f"{DIM}long-term memory erased (working memory untouched){RESET}")
                else:
                    print(f"unknown command: /{cmd}")
                continue

            reply, trace = turn(app, thread, line, enabled)
            print(heading("recalled"))
            print(show_recall(trace.recalled))
            print(heading("sage"))
            print(reply)
            print(heading("written"))
            print(show_writes(trace.written))

    return 0


if __name__ == "__main__":
    sys.exit(main())
