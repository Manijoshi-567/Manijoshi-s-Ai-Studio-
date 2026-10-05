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

    # Vercel serverless functions can only write to /tmp
    OUTPUT_DIR = Path("/tmp/output") if os.getenv("VERCEL") else Path("output")

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
    def get_available_provider(cls, requested_provider: str = None) -> str:
        """Returns the best available provider based on configured API keys."""
        req = (requested_provider or "").lower().strip()
        if req and req in cls.ALLOWED_PROVIDERS:
            # If requested provider has a key, use it
            if req == "ollama" or cls.get_api_key(req):
                return req

        # Check if the configured default has a key
        if cls.DEFAULT_PROVIDER in cls.ALLOWED_PROVIDERS and cls.get_api_key(cls.DEFAULT_PROVIDER):
            return cls.DEFAULT_PROVIDER

        # Otherwise find ANY configured provider key
        if cls.GEMINI_API_KEY:
            return "gemini"
        if cls.OPENAI_API_KEY:
            return "openai"
        if cls.ANTHROPIC_API_KEY:
            return "anthropic"

        return req if req in cls.ALLOWED_PROVIDERS else cls.DEFAULT_PROVIDER

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """Returns the appropriate default model for the given provider."""
        p = (provider or "").lower()
        if p == "gemini":
            return "gemini-1.5-flash"
        elif p == "anthropic":
            return "claude-3-5-sonnet-20241022"
        elif p == "ollama":
            return "llama3"
        return "gpt-4o-mini"

    @classmethod
    def sanitize_provider(cls, provider: str) -> str:
        clean_p = (provider or "").lower().strip()
        if clean_p == "auto":
            return cls.get_available_provider()
        return clean_p if clean_p in cls.ALLOWED_PROVIDERS else cls.get_available_provider()
