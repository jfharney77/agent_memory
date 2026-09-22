"""Run every demo in order.

    python demo/run_all.py            # all five
    python demo/run_all.py 3 4        # just those

Expect a few minutes on a local 7B model -- each turn costs up to three LLM
calls (respond, write, reflect).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEMOS = {
    1: "01_working_memory",
    2: "02_episodic",
    3: "03_semantic",
    4: "04_procedural",
    5: "05_consolidation",
}


def main(argv: list[str]) -> int:
    wanted = [int(a) for a in argv] if argv else sorted(DEMOS)
    for n in wanted:
        if n not in DEMOS:
            print(f"no demo {n}; choose from {sorted(DEMOS)}")
            return 1
        importlib.import_module(DEMOS[n]).main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
