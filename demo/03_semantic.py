"""SEMANTIC MEMORY -- what is true, with the occasion stripped off.

A semantic memory is a standalone statement: "The user has a thermodynamics
exam on October 14th." It carries no trace of the conversation that produced
it, and that is the point -- it is meant to be true tomorrow too.

Two consequences, both visible below:

  * writes are deduplicated. Being told the same thing twice should not double
    the size of what you know, so a near-identical fact bumps a counter
    instead of inserting a row. Compare with episodic memory, where the second
    telling is genuinely a second event.
  * retrieval ignores time entirely. A fact learned three weeks ago outranks a
    fact learned today if it matches the question better.

Run: python demo/03_semantic.py
"""
from _common import BOLD, DIM, RESET, fresh_lab, note, say, title

from memory_lab.display import show_stores


def main() -> None:
    title("3. SEMANTIC MEMORY")

    with fresh_lab("semantic") as (memory, app):
        note("--- A turn in one thread. Watch the writer split the exchange into\n"
             "an episode (an occasion) and facts (durable statements). ---")
        say(app, "monday",
            "I'm John, a mechanical engineer. I'm back in school part time and my "
            "thermodynamics final is on October 14th.",
            enabled=["working", "episodic", "semantic"])

        note("\n--- A different thread, days later. Working memory is empty, but the\n"
             "facts are still there. ---")
        say(app, "friday", "How much time do I have left to prepare?",
            enabled=["working", "semantic"])

        note("\n--- Tell it the same thing a second time, worded differently. ---")
        say(app, "friday", "Just to be clear, my thermo exam is October 14.",
            enabled=["working", "episodic", "semantic"], show=("writes",))

        print(show_stores(memory))
        note("The exam date appears once, with a 'seen xN' counter, rather than once\n"
             "per telling -- that is FACT_DEDUP_THRESHOLD in config.py doing its job.\n"
             "The episode log, right below it, kept every telling as a separate row,\n"
             "because two separate things happened. Same input, opposite write policy.")

        note("\n--- The A/B. Same question, semantic memory off. ---")
        reply_off = say(app, "saturday", "What am I preparing for, and when?",
                        enabled=["working"], show=("reply",))
        note("--- Same question, semantic memory on. ---")
        reply_on = say(app, "sunday", "What am I preparing for, and when?",
                       enabled=["working", "semantic"], show=("recall", "reply"))

        print(f"\n{BOLD}without semantic memory:{RESET} {DIM}{reply_off[:120]}...{RESET}")
        print(f"{BOLD}with semantic memory:   {RESET} {DIM}{reply_on[:120]}...{RESET}")

    note("\nTakeaway: semantic memory is the agent's model of you. It is small,\n"
         "deduplicated, timeless, and it is what makes a fresh conversation not\n"
         "start from zero. Demo 04 next: memory that changes behaviour rather\n"
         "than supplying content.")


if __name__ == "__main__":
    main()
