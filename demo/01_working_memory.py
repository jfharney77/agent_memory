"""WORKING MEMORY -- the window that forgets.

Working memory is the message list carried inside one run of the graph. In
LangGraph it is just state, persisted per `thread_id` by the checkpointer.

Two properties make it different from everything else in this project:

  1. It is bounded. `window()` in agent.py keeps only the last N turns, so old
     detail falls out silently -- there is no eviction event to handle.
  2. It is scoped to a thread. Start a new conversation and it is simply gone.

Both are on purpose. Working memory is cheap, immediate, and disposable. The
other three systems exist to survive exactly these two failures.

Run: python demo/01_working_memory.py
"""
from _common import DIM, RESET, fresh_lab, note, say, title

from memory_lab import config
from memory_lab.cli import working_messages

LONGTERM_OFF = ["working"]   # only working memory is enabled


def main() -> None:
    title("1. WORKING MEMORY")
    note(f"Long-term memory is switched off for this demo. Window size is "
         f"{config.WORKING_MEMORY_TURNS} turns ({config.WORKING_MEMORY_TURNS * 2} messages).")

    with fresh_lab("working") as (memory, app):
        note("\n--- Within one thread, the agent follows a reference back a turn. ---")
        say(app, "morning", "My lab partner's name is Priya.",
            enabled=LONGTERM_OFF, show=("reply",))
        say(app, "morning", "What did I just tell you her name was?",
            enabled=LONGTERM_OFF, show=("reply",))

        note("\n--- Now fill the window past its limit with unrelated turns. ---")
        filler = [
            "Convert 300 kelvin to celsius.",
            "What is the SI unit of pressure?",
            "Define an adiabatic process in one line.",
            "What does R equal in the ideal gas law?",
            "Is enthalpy a state function?",
            "One line: what is a reversible process?",
        ]
        for q in filler:
            print(f"{DIM}  ... {q}{RESET}")
            say(app, "morning", q, enabled=LONGTERM_OFF, show=())

        msgs = working_messages(app, "morning")
        print(f"\n{DIM}window now holds {len(msgs)} messages; the oldest survivor is:{RESET}")
        print(f"  {msgs[0]['role']}: {msgs[0]['content'][:80]}")

        note("\n--- Ask again. Priya has fallen out of the window. ---")
        say(app, "morning", "What was my lab partner's name?",
            enabled=LONGTERM_OFF, show=("reply",))

        note("\n--- And a new thread starts with nothing at all. ---")
        say(app, "afternoon", "What was my lab partner's name?",
            enabled=LONGTERM_OFF, show=("reply",))

    note("\nTakeaway: working memory is a sliding window, not a record. "
         "Anything you need tomorrow has to be written somewhere else -- "
         "which is demo 02, 03 and 04.")


if __name__ == "__main__":
    main()
