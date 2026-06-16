"""
Configuration module for the Convers conversation simulator.
Loads environment variables and defines application-wide constants.
"""

import os
from dotenv import load_dotenv

# Load .env from the project root (one level up from backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Model Settings ────────────────────────────────────────────────────────────
DEFAULT_MODEL: str = "llama-3.3-70b-versatile"

# ── Session Settings ──────────────────────────────────────────────────────────
SESSION_TIMEOUT: int = 3600        # seconds before a session is considered expired
MAX_HISTORY: int = 20              # max number of messages retained per session
