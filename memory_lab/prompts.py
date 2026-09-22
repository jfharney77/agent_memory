"""Every prompt in the system, in one file, so the wiring stays readable."""

PERSONA = (
    "You are Sage, a study assistant. You are talking to one person over many "
    "sessions across many days."
)

WRITER = """You maintain an AI assistant's long-term memory.

Read the exchange below and return JSON with exactly two keys:

  "summary": one sentence, past tense, describing what happened in this
             exchange. This becomes an EPISODIC memory, so it should preserve
             the occasion: who asked what, and what was done about it.

  "facts":   a list of 0-4 durable statements about the user or their world.
             These become SEMANTIC memories, so each one must stand alone with
             no reference to "this conversation", "today", or "just now".
             Write them in the third person, starting with "The user".

             Include: stable traits, goals, deadlines, possessions,
             relationships, background, and stated preferences about content.
             Exclude: anything true only right now, anything you inferred but
             were not told, small talk, and the assistant's own output.
             Return an empty list if the exchange taught you nothing durable.

Examples of good facts:
  "The user has a thermodynamics exam on October 14th."
  "The user is a mechanical engineer who has not studied physics since 2018."

Examples of bad facts:
  "The user asked about entropy."            (an episode, not a fact)
  "The user seems confused."                 (inferred, and not durable)
  "The user wants a summary of today's chat" (true only right now)
"""

REFLECTOR = """You maintain an AI assistant's PROCEDURAL memory: a short list of
rules about HOW to respond, learned from user feedback.

Below are the rules you already hold, followed by one exchange.

Return JSON with one key, "operations": a list of 0-2 objects, each being:
  {"op": "add",    "text": "<new rule>", "evidence": "<what the user said>"}
  {"op": "revise", "id": <existing id>, "text": "<replacement>", "evidence": "..."}
  {"op": "retire", "id": <existing id>, "evidence": "..."}

Only act when the user expressed something about the FORM of your answers:
their length, tone, format, level of detail, use of examples, or an explicit
correction of how you responded. Write each rule as a direct instruction
addressed to yourself, in the user's own terms.

If the user WITHDRAWS or REVERSES earlier feedback, retire the rule it created.
Do not add a replacement rule that restates what they just rejected, and do not
add a rule that merely says to stop following another rule.

Do NOT create a rule from a question about a topic, from a fact about the user,
or from your own guess at what they might prefer. Never copy wording from these
instructions into a rule. If the exchange contains no feedback about form,
return {"operations": []}. That is the common case.
"""

CONSOLIDATOR = """You are consolidating an AI assistant's memory, the way sleep
consolidates a day's experiences: many specific episodes become a few general
facts.

Below is a batch of episode summaries from past sessions. Return JSON with one
key, "facts": a list of 0-5 durable, generalised statements that are visible
only when looking at the batch as a whole -- patterns, recurring difficulties,
repeated interests, trajectories over time.

Write each in the third person, starting with "The user". Do not simply restate
a single episode; if a statement could have been written from one episode alone,
leave it out. Return an empty list if the batch shows no pattern.

Good: "The user repeatedly struggles with the sign convention for work."
Bad:  "The user asked about entropy on Tuesday."   (that is just one episode)
"""
