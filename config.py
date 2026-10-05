import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Security & Admin Access Control
    ADMIN_LOCK_ENABLED = True
    ALLOWED_PROVIDERS = {"openai", "gemini", "anthropic", "ollama"}

    OUTPUT_DIR = Path("output")

    @classmethod
    def get_api_key(cls, provider: str = None) -> str:
        provider = (provider or cls.DEFAULT_PROVIDER).lower()
        if provider == "openai":
            return cls.OPENAI_API_KEY
        elif provider == "gemini":
            return cls.GEMINI_API_KEY
        elif provider == "anthropic":
            return cls.ANTHROPIC_API_KEY
        return ""

    @classmethod
    def sanitize_provider(cls, provider: str) -> str:
        clean_p = (provider or "").lower().strip()
        return clean_p if clean_p in cls.ALLOWED_PROVIDERS else cls.DEFAULT_PROVIDER
