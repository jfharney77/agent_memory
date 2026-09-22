"""Terminal formatting. No dependencies, just ANSI."""
from __future__ import annotations

from typing import Any

DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
COLORS = {
    "working": "\033[36m",     # cyan
    "episodic": "\033[35m",    # magenta
    "semantic": "\033[32m",    # green
    "procedural": "\033[33m",  # yellow
}


def tag(kind: str) -> str:
    return f"{COLORS.get(kind, '')}{kind:<10}{RESET}"


def heading(text: str) -> str:
    return f"\n{BOLD}{text}{RESET}\n{DIM}{'-' * len(text)}{RESET}"


def show_recall(recalled: dict[str, Any]) -> str:
    lines = []
    for kind in ("procedural", "semantic", "episodic"):
        items = recalled.get(kind)
        if items is None:
            continue
        if not items:
            lines.append(f"  {tag(kind)} {DIM}nothing relevant{RESET}")
            continue
        for it in items:
            if kind == "episodic":
                detail = (f"{DIM}[{it['ts'][:10]}, {it['age_days']:.1f}d ago, "
                          f"score {it['score']}]{RESET} {it['summary']}")
            elif kind == "semantic":
                seen = f", seen x{it['seen_count']}" if it["seen_count"] > 1 else ""
                detail = f"{DIM}[score {it['score']}{seen}]{RESET} {it['text']}"
            else:
                detail = it["text"]
            lines.append(f"  {tag(kind)} {detail}")
    return "\n".join(lines) or f"  {DIM}(all long-term memory disabled){RESET}"


def show_writes(written: dict[str, Any]) -> str:
    lines = []
    ep = written.get("episodic")
    if ep:
        lines.append(f"  {tag('episodic')} +ep{ep['id']}  {ep['summary']}")
    for f in written.get("semantic") or []:
        mark = "+new" if f["new"] else "=dup"
        lines.append(f"  {tag('semantic')} {mark} f{f['id']}  {f['text']}")
    for op in written.get("procedural") or []:
        lines.append(f"  {tag('procedural')} {op['op']} r{op['id']}  {op.get('text', '')}")
    return "\n".join(lines) or f"  {DIM}nothing new worth keeping{RESET}"


def show_stores(memory, working: list[dict] | None = None) -> str:
    out = []
    if working is not None:
        out.append(heading(f"WORKING  ({len(working)} messages in this thread's window)"))
        for m in working:
            body = m["content"].replace("\n", " ")
            out.append(f"  {tag('working')} {m['role']:<9} {body[:90]}")
        if not working:
            out.append(f"  {DIM}empty{RESET}")

    rules = memory.procedural.active()
    out.append(heading(f"PROCEDURAL  ({len(rules)} active rules, all injected every turn)"))
    for r in rules:
        out.append(f"  {tag('procedural')} r{r.id}  {r.text}")
        out.append(f"             {DIM}learned from: {r.evidence[:80]}{RESET}")
    if not rules:
        out.append(f"  {DIM}empty{RESET}")

    facts = memory.semantic.all()
    out.append(heading(f"SEMANTIC  ({len(facts)} facts, deduplicated, no timestamps used)"))
    for f in facts:
        extra = f"seen x{f.seen_count}" if f.seen_count > 1 else f.origin
        out.append(f"  {tag('semantic')} f{f.id}  {f.text} {DIM}({extra}){RESET}")
    if not facts:
        out.append(f"  {DIM}empty{RESET}")

    eps = memory.episodic.all()
    out.append(heading(f"EPISODIC  ({len(eps)} episodes, append-only, timestamped)"))
    for e in eps:
        out.append(f"  {tag('episodic')} ep{e.id} {DIM}[{e.ts[:10]} thread={e.thread_id}]{RESET} {e.summary}")
    if not eps:
        out.append(f"  {DIM}empty{RESET}")
    return "\n".join(out)
