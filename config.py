"""Central configuration for the Entity Scraper.

All settings are read from environment variables (optionally loaded from a
``.env`` file).  Sensible defaults mean the application runs with zero setup.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (does nothing if the file is missing).
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JSON_DIR = DATA_DIR / "json"
DB_PATH = DATA_DIR / "entities.db"

# Make sure the storage folders exist on import.
DATA_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Runtime configuration assembled from the environment."""

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Search backend
    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "duckduckgo").strip().lower()
    # ddgs engine selection. "auto" lets ddgs pick a working engine and rotate
    # on failure (most reliable); or set a comma-separated list to aggregate.
    DDGS_BACKEND: str = os.getenv("DDGS_BACKEND", "auto")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "").strip()
    GOOGLE_CSE_ID: str = os.getenv("GOOGLE_CSE_ID", "").strip()
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "").strip()

    # Optional LLM assist layer.  This is disabled unless a key is supplied.
    # The defaults target OpenAI-compatible chat/completions APIs.
    LLM_ENABLED: bool = _as_bool(os.getenv("LLM_ENABLED"), True)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai-compatible").strip()
    LLM_API_KEY: str = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_CHAT_URL: str = os.getenv("LLM_CHAT_URL", f"{LLM_BASE_URL}/chat/completions")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1-mini").strip()
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "45"))
    LLM_MAX_PAGE_CHARS: int = int(os.getenv("LLM_MAX_PAGE_CHARS", "9000"))

    # Scraping behaviour
    DEFAULT_REGION: str = os.getenv("DEFAULT_REGION", "SA").strip().upper()
    MAX_PAGES_PER_SITE: int = int(os.getenv("MAX_PAGES_PER_SITE", "6"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))
    REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY", "0.5"))
    RESPECT_ROBOTS: bool = _as_bool(os.getenv("RESPECT_ROBOTS"), True)

    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 EntityScraper/1.0"
    )

    # Paths (as strings for convenience)
    DB_PATH: str = str(DB_PATH)
    JSON_DIR: str = str(JSON_DIR)

    @classmethod
    def available_backends(cls) -> dict[str, bool]:
        """Report which backends are actually usable given current keys."""
        return {
            "duckduckgo": True,  # always available, no key required
            "google": bool(cls.GOOGLE_API_KEY and cls.GOOGLE_CSE_ID),
            "serpapi": bool(cls.SERPAPI_KEY),
        }

    @classmethod
    def available_llm(cls) -> dict[str, str | bool]:
        return {
            "enabled": bool(cls.LLM_ENABLED and cls.LLM_API_KEY),
            "provider": cls.LLM_PROVIDER,
            "model": cls.LLM_MODEL,
        }


config = Config()
