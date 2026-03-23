from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    app_name: str = "Clinical Data Reconciliation Engine"
    app_api_key: str = os.getenv("APP_API_KEY", "demo-key")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    llm_cache_ttl_seconds: int = int(os.getenv("LLM_CACHE_TTL_SECONDS", "3600"))


settings = Settings()
