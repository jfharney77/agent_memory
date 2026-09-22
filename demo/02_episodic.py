"""EPISODIC MEMORY -- what happened, and when.

An episode is a record of an occasion: this person asked this, on this day, and
this is what we did about it. Three design choices follow from that:

  * append-only. The same question asked twice is two memories, not one.
  * timestamped, and the timestamp is used at retrieval time. Scoring blends
    similarity with recency, so a fair match from yesterday can beat a great
    match from last month.
  * summarised, not verbatim. Storing the raw transcript would retrieve badly;
    a one-line "what happened" embeds much closer to how people ask about it.

This is the memory that answers "what were we doing last time?" -- a question
semantic memory cannot answer, because it has thrown the occasion away.

Run: python demo/02_episodic.py
"""
from _common import DIM, RESET, fresh_lab, note, say, title

from memory_lab.display import show_recall

# Seeded directly into the store so the demo runs fast and the dates are exact.
HISTORY = [
    (21, "day-1", "Explained the first law of thermodynamics using a piston example.",
     "Can you walk me through the first law?"),
    (14, "day-8", "Worked through a Carnot cycle efficiency problem and found an "
     "arithmetic slip in the user's temperature conversion.",
     "Why is my Carnot efficiency over 100%?"),
    (2, "day-20", "Reviewed entropy change for an irreversible expansion; the user "
     "got the sign backwards twice.",
     "Does entropy go down in a free expansion?"),
    (0.2, "day-22", "Listed what to revise in the final week before the exam.",
     "What should I focus on this week?"),
]


def main() -> None:
    title("2. EPISODIC MEMORY")

    with fresh_lab("episodic") as (memory, app):
        note("Seeding four past sessions, spread over three weeks.")
        for days_ago, thread, summary, asked in HISTORY:
            ep_id = memory.episodic.record(thread, asked, "(reply omitted)", summary)
            memory.episodic.backdate(ep_id, days_ago)
            print(f"  {DIM}ep{ep_id} [{days_ago:>4.1f}d ago]{RESET} {summary[:70]}")

        note("\n--- Retrieval is similarity blended with recency. ---")
        for query in ["I'm confused about entropy signs again",
                      "remind me about the first law",
                      "what did we do last time?"]:
            print(f"\n{DIM}query:{RESET} {query}")
            print(show_recall({"episodic": [
                {"id": e.id, "ts": e.ts, "summary": e.summary,
                 "score": round(e.score, 3), "age_days": round(e.age_days(), 2)}
                for e in memory.episodic.recall(query)]}))

        note("\nNotice the third query. 'what did we do last time?' has almost no\n"
             "lexical overlap with any episode -- recency is doing the work, which\n"
             "is the whole reason the score is not pure cosine similarity.")

        note("\n--- Now with the agent. Only episodic memory is on. ---")
        say(app, "day-23", "What have I been getting wrong lately?",
            enabled=["working", "episodic"])

    note("\nTakeaway: episodic memory preserves occasions. It is what lets an agent\n"
         "say 'you had this same trouble two days ago' -- a claim that requires\n"
         "knowing there were two separate times, which is precisely what semantic\n"
         "memory discards. Demo 03 next.")


if __name__ == "__main__":
    main()
