"""The LangGraph agent, wired to four memory systems.

    recall  ->  respond  ->  remember  ->  reflect

Each node touches a different memory system, and every one of them can be
switched off independently so you can watch what breaks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph

from . import config, llm, prompts
from .stores import Memory

MemoryKind = Literal["working", "episodic", "semantic", "procedural"]
ALL_MEMORIES: tuple[MemoryKind, ...] = ("working", "episodic", "semantic", "procedural")


def window(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Reducer for WORKING memory.

    Working memory is not a log. It is a fixed-size window that forgets by
    construction -- which is exactly why an agent needs the other three.
    """
    merged = (existing or []) + (incoming or [])
    limit = config.WORKING_MEMORY_TURNS * 2
    return merged[-limit:]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict], window]   # working memory
    user_input: str
    reply: str
    enabled: list[str]
    # Populated by recall(), kept in state purely so the CLI can show its work.
    recalled: dict[str, Any]
    written: dict[str, Any]


@dataclass
class Trace:
    """What each memory system contributed on the last turn."""
    recalled: dict[str, Any] = field(default_factory=dict)
    written: dict[str, Any] = field(default_factory=dict)


def build_agent(memory: Memory, checkpointer: SqliteSaver):
    """Compile the graph. `memory` is closed over rather than kept in state,
    because SQLite connections are not checkpointable."""

    def recall(state: AgentState) -> AgentState:
        """Read from long-term memory. Working memory needs no read step --
        it is already sitting in the state."""
        on = set(state.get("enabled", ALL_MEMORIES))
        query = state["user_input"]
        out: dict[str, Any] = {}

        if "semantic" in on:
            out["semantic"] = [
                {"id": f.id, "text": f.text, "score": round(f.score, 3),
                 "seen_count": f.seen_count, "origin": f.origin}
                for f in memory.semantic.recall(query)
                if f.score > 0.35
            ]
        if "episodic" in on:
            out["episodic"] = [
                {"id": e.id, "ts": e.ts, "summary": e.summary,
                 "score": round(e.score, 3), "age_days": round(e.age_days(), 2)}
                for e in memory.episodic.recall(query)
                if e.score > 0.35
            ]
        if "procedural" in on:
            out["procedural"] = [
                {"id": r.id, "text": r.text} for r in memory.procedural.active()
            ]
        return {"recalled": out}

    def respond(state: AgentState) -> AgentState:
        on = set(state.get("enabled", ALL_MEMORIES))
        r = state.get("recalled", {})

        system = [prompts.PERSONA]

        if r.get("procedural"):
            system.append(
                "Rules you have learned from this user's feedback. Follow them:\n"
                + "\n".join(f"- {x['text']}" for x in r["procedural"])
            )
        if r.get("semantic"):
            system.append(
                "What you know about this user:\n"
                + "\n".join(f"- {x['text']}" for x in r["semantic"])
            )
        if r.get("episodic"):
            system.append(
                "Past sessions with this user, most relevant first. These really\n"
                "happened -- treat them as fact, and use them to answer anything\n"
                "about what you have already covered together. Never claim you\n"
                "have no record of past conversations while this list is here:\n"
                + "\n".join(f"- [{x['ts'][:10]}] {x['summary']}" for x in r["episodic"])
            )

        history = state.get("messages", []) if "working" in on else []
        msgs = (
            [{"role": "system", "content": "\n\n".join(system)}]
            + history
            + [{"role": "user", "content": state["user_input"]}]
        )
        reply = llm.chat(msgs)
        return {
            "reply": reply,
            "messages": [
                {"role": "user", "content": state["user_input"]},
                {"role": "assistant", "content": reply},
            ],
        }

    def remember(state: AgentState) -> AgentState:
        """One LLM call produces both the episodic summary and the semantic
        facts, because both are read off the same exchange."""
        on = set(state.get("enabled", ALL_MEMORIES))
        written: dict[str, Any] = {}
        if not ({"episodic", "semantic"} & on):
            return {"written": written}

        exchange = f"User: {state['user_input']}\nAssistant: {state['reply']}"
        parsed = llm.chat_json([
            {"role": "system", "content": prompts.WRITER},
            {"role": "user", "content": exchange},
        ]) or {}

        summary = (parsed.get("summary") or "").strip()
        facts = [f.strip() for f in (parsed.get("facts") or []) if isinstance(f, str) and f.strip()]

        thread_id = get_config()["configurable"]["thread_id"]
        if "episodic" in on:
            if not summary:
                summary = f"The user asked: {state['user_input'][:120]}"
            ep_id = memory.episodic.record(thread_id, state["user_input"], state["reply"], summary)
            written["episodic"] = {"id": ep_id, "summary": summary}

        if "semantic" in on:
            recorded = []
            for text in facts:
                fid, is_new = memory.semantic.upsert(text, origin="turn")
                recorded.append({"id": fid, "text": text, "new": is_new})
            written["semantic"] = recorded

        return {"written": written}

    def reflect(state: AgentState) -> AgentState:
        """Procedural memory only updates on feedback about *how* to answer,
        which is why it gets its own pass over the exchange."""
        on = set(state.get("enabled", ALL_MEMORIES))
        written = dict(state.get("written", {}))
        if "procedural" not in on:
            return {"written": written}

        existing = memory.procedural.active()
        rules_txt = "\n".join(f"{r.id}: {r.text}" for r in existing) or "(none yet)"
        parsed = llm.chat_json([
            {"role": "system", "content": prompts.REFLECTOR},
            {"role": "user", "content":
                f"Existing rules:\n{rules_txt}\n\nExchange:\nUser: {state['user_input']}"
                f"\nAssistant: {state['reply']}"},
        ]) or {}

        applied = []
        for op in (parsed.get("operations") or [])[:2]:
            if not isinstance(op, dict):
                continue
            kind, text = op.get("op"), (op.get("text") or "").strip()
            evidence = (op.get("evidence") or state["user_input"])[:300]
            try:
                if kind == "add" and text:
                    rid = memory.procedural.add(text, evidence)
                    applied.append({"op": "add", "id": rid, "text": text})
                elif kind == "revise" and text and op.get("id") is not None:
                    memory.procedural.revise(int(op["id"]), text, evidence)
                    applied.append({"op": "revise", "id": int(op["id"]), "text": text})
                elif kind == "retire" and op.get("id") is not None:
                    memory.procedural.retire(int(op["id"]))
                    applied.append({"op": "retire", "id": int(op["id"])})
            except (ValueError, TypeError):
                continue

        if applied:
            written["procedural"] = applied
        return {"written": written}

    g = StateGraph(AgentState)
    g.add_node("recall", recall)
    g.add_node("respond", respond)
    g.add_node("remember", remember)
    g.add_node("reflect", reflect)
    g.add_edge(START, "recall")
    g.add_edge("recall", "respond")
    g.add_edge("respond", "remember")
    g.add_edge("remember", "reflect")
    g.add_edge("reflect", END)
    return g.compile(checkpointer=checkpointer)


def turn(app, thread_id: str, user_input: str,
         enabled: list[str] | None = None) -> tuple[str, Trace]:
    """Run one turn. Returns the reply and what memory did."""
    result = app.invoke(
        {"user_input": user_input, "enabled": list(enabled or ALL_MEMORIES)},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["reply"], Trace(result.get("recalled", {}), result.get("written", {}))
