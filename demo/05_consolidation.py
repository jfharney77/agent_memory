"""CONSOLIDATION -- episodic memory becoming semantic memory.

The writer that runs on each turn can only see that turn, so it can only record
what was said outright. Some of the most useful things about a user are never
said outright: they are patterns, visible only across a stack of episodes.

That is what consolidation is for. It reads the episodes not yet digested and
writes back the few generalisations that no single episode could have produced.
The biological analogy is doing the work here -- this is roughly what sleep is
thought to do with the day's experiences -- but the engineering reason is
simpler: retrieval over five hundred episodes is expensive and noisy, while
retrieval over the dozen facts they imply is cheap and sharp.

Run: python demo/05_consolidation.py
"""
from _common import BOLD, DIM, RESET, fresh_lab, note, say, title

from memory_lab.consolidate import consolidate
from memory_lab.display import show_stores

# Six sessions. No single one says "this user keeps confusing sign conventions",
# but all six together do.
SESSIONS = [
    (25, "Worked a piston compression problem; the user wrote W positive for work "
         "done ON the gas and got the energy balance backwards."),
    (19, "Reviewed heat pump COP. The user's answer was right but took three tries "
         "on which direction heat flowed."),
    (14, "Free expansion problem: the user said entropy decreased. Corrected the "
         "sign and walked through why."),
    (9,  "The user asked for more worked examples instead of derivations, saying "
         "the algebra is where they lose the thread."),
    (5,  "Carnot efficiency problem. The user flipped Tc and Th in the ratio."),
    (2,  "Refrigerator cycle problem; the user again took work into the system as "
         "positive and had to redo the balance."),
]


def main() -> None:
    title("5. CONSOLIDATION: EPISODIC -> SEMANTIC")

    with fresh_lab("consolidation") as (memory, app):
        note("Seeding six past sessions over about a month.")
        for days_ago, summary in SESSIONS:
            ep_id = memory.episodic.record(f"day-{30 - int(days_ago)}", "(question omitted)",
                                           "(reply omitted)", summary)
            memory.episodic.backdate(ep_id, days_ago)
            print(f"  {DIM}ep{ep_id} [{days_ago:>2}d ago]{RESET} {summary[:72]}")

        print(f"\n{BOLD}semantic memory before consolidation:{RESET} "
              f"{len(memory.semantic.all())} facts")

        note("\n--- Ask a question that no single episode answers. Episodic memory\n"
             "only returns three episodes, and the pattern spans six. ---")
        say(app, "day-30", "Be honest -- what is my actual weak spot?",
            enabled=["working", "episodic"])

        note("\n--- Now consolidate. One pass over the whole undigested batch. ---")
        result = consolidate(memory, min_episodes=3)
        print(f"{DIM}read {result['episodes']} episodes{RESET}")
        for f in result["facts"]:
            mark = "+new" if f["new"] else "=dup"
            print(f"  {mark} f{f['id']}  {f['text']}")

        print(show_stores(memory))
        note("The episodes are untouched -- consolidation does not destroy the\n"
             "record, it summarises it. Each is now flagged consolidated so the\n"
             "next pass skips it.")

        note("\n--- Same question again, this time with semantic memory on. ---")
        say(app, "day-31", "Be honest -- what is my actual weak spot?",
            enabled=["working", "episodic", "semantic"])

    note("\nTakeaway: the two long-term stores are not rivals, they are a pipeline.\n"
         "Episodes come in raw and specific; consolidation distils the stable part\n"
         "into facts that retrieve cheaply. Without it, semantic memory only ever\n"
         "contains what the user stated explicitly.")


if __name__ == "__main__":
    main()
