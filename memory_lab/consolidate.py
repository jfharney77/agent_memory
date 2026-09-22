"""Episodic -> semantic consolidation.

Run this between sessions. It reads the episodes the agent has not yet digested
and writes back the generalisations that are only visible across several of
them. This is the step that keeps semantic memory from being a pile of trivia:
facts stated once get stored by the writer during the turn, but patterns that
emerge over a week can only be found by looking at the week.
"""
from __future__ import annotations

from typing import Any

from . import llm, prompts
from .stores import Memory


def consolidate(memory: Memory, min_episodes: int = 3) -> dict[str, Any]:
    episodes = memory.episodic.unconsolidated()
    if len(episodes) < min_episodes:
        return {
            "status": "skipped",
            "reason": f"only {len(episodes)} new episodes, need {min_episodes}",
            "facts": [],
        }

    batch = "\n".join(f"[{e.ts[:10]}] {e.summary}" for e in episodes)
    parsed = llm.chat_json([
        {"role": "system", "content": prompts.CONSOLIDATOR},
        {"role": "user", "content": batch},
    ]) or {}

    recorded = []
    for text in (parsed.get("facts") or []):
        if not isinstance(text, str) or not text.strip():
            continue
        fid, is_new = memory.semantic.upsert(text.strip(), origin="consolidation")
        recorded.append({"id": fid, "text": text.strip(), "new": is_new})

    memory.episodic.mark_consolidated([e.id for e in episodes])
    return {"status": "ok", "episodes": len(episodes), "facts": recorded}
