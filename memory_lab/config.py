"""Environment-driven settings. Everything runs against local Ollama."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:latest")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "granite-embedding:30m")

MEMORY_DB = Path(os.getenv("MEMORY_DB", ROOT / "memory.db"))
CHECKPOINT_DB = MEMORY_DB.with_name(MEMORY_DB.stem + "_checkpoints.db")

# Working memory: how many recent messages the agent carries inside one thread.
# Deliberately small so you can watch it overflow.
WORKING_MEMORY_TURNS = int(os.getenv("WORKING_MEMORY_TURNS", "6"))

# Two facts closer than this cosine distance are treated as the same fact.
FACT_DEDUP_THRESHOLD = float(os.getenv("FACT_DEDUP_THRESHOLD", "0.88"))

# Retrieval budgets, per turn.
SEMANTIC_TOP_K = int(os.getenv("SEMANTIC_TOP_K", "5"))
EPISODIC_TOP_K = int(os.getenv("EPISODIC_TOP_K", "3"))

# Episodic recall blends similarity with recency: score = sim + RECENCY_WEIGHT * freshness
RECENCY_WEIGHT = float(os.getenv("RECENCY_WEIGHT", "0.15"))
