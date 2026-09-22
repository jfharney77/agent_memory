"""PROCEDURAL MEMORY -- how to behave, learned from feedback.

The other three systems supply *content* for an answer. Procedural memory
changes the *shape* of it: length, tone, format, the habits a user corrects you
into. In this project it is a short list of rules, rewritten by a reflection
pass that runs after every turn and usually decides to do nothing.

Two things about it are deliberately unlike the others:

  * no embeddings, no similarity search. The rules are loaded wholesale into
    every system prompt. An agent that only remembered to be concise when the
    question was about concision would not have learned anything.
  * writes are edits, not appends. The reflector can revise or retire a rule,
    because behaviour that is no longer wanted has to be removable. Compare
    episodic memory, which may never rewrite the past.

Run: python demo/04_procedural.py
"""
from _common import BOLD, DIM, RESET, fresh_lab, note, say, title


def length(text: str) -> str:
    return f"{len(text)} chars, {len(text.split())} words"


def main() -> None:
    title("4. PROCEDURAL MEMORY")

    with fresh_lab("procedural") as (memory, app):
        note("--- Baseline: no rules yet. ---")
        before = say(app, "mon", "Explain what enthalpy is.",
                     enabled=["working", "procedural"], show=("reply",))
        print(f"\n{DIM}baseline length: {length(before)}{RESET}")

        note("\n--- The user pushes back on the FORM of the answer, not its content. ---")
        say(app, "mon", "That's far too long. Three sentences maximum from now on, "
                        "and skip the bullet lists.",
            enabled=["working", "procedural"], show=("reply", "writes"))

        print(f"\n{BOLD}rules now held:{RESET}")
        for r in memory.procedural.active():
            print(f"  r{r.id}  {r.text}")
            print(f"       {DIM}evidence: {r.evidence[:70]}{RESET}")

        note("\n--- A brand new thread, so working memory cannot be the explanation.\n"
             "A different question entirely, so semantic retrieval cannot be either. ---")
        after = say(app, "wed", "Explain what Gibbs free energy is.",
                    enabled=["working", "procedural"], show=("recall", "reply"))
        print(f"\n{DIM}with the rule: {length(after)}{RESET}")

        note("\n--- Control: same question, same thread policy, procedural memory off. ---")
        control = say(app, "thu", "Explain what Gibbs free energy is.",
                      enabled=["working"], show=("reply",))
        print(f"\n{DIM}rule disabled: {length(control)}{RESET}")

        print(f"\n{BOLD}baseline      {RESET} {length(before)}")
        print(f"{BOLD}with rule     {RESET} {length(after)}")
        print(f"{BOLD}rule disabled {RESET} {length(control)}")

        note("\n--- Feedback can also retract. Watch the reflector edit, not append. ---")
        say(app, "wed", "Actually, go back to giving me full detail -- I was wrong, "
                        "the short answers aren't helping me study.",
            enabled=["working", "procedural"], show=("writes",))
        print(f"\n{BOLD}rules now held:{RESET}")
        for r in memory.procedural.active():
            print(f"  r{r.id}  {r.text}")
        if not memory.procedural.active():
            print(f"  {DIM}none -- the rule was retired{RESET}")

        note("If the surviving rules above contradict each other, that is not a bug\n"
             "in the demo -- it is the characteristic failure of procedural memory,\n"
             "and worth seeing. A rule set grows by accretion and nothing reconciles\n"
             "it unless you write that step. Real systems add a periodic pass that\n"
             "merges and prunes rules, the same way consolidate.py does for facts.")

    note("\nTakeaway: procedural memory is the only one that makes the agent behave\n"
         "differently rather than know more. It is also the one most worth keeping\n"
         "small -- every rule is paid for on every single turn.")


if __name__ == "__main__":
    main()
