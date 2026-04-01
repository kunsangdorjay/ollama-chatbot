import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_prefix: str = "/api"
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
    allow_origins: list[str] = None

    def __post_init__(self):
        if self.allow_origins is None:
            object.__setattr__(self, "allow_origins", ["*"])


settings = Settings()
