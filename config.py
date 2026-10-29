import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")))
    username: str = field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    password_hash: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD_HASH", ""))
    origins: tuple[str, ...] = field(default_factory=lambda: tuple(x.strip().rstrip("/") for x in os.getenv("APP_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip()))
    secure_cookie: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true")
    api_base: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"))
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    models: tuple[str, ...] = field(default_factory=lambda: tuple(x.strip() for x in os.getenv("CHAT_MODELS", "gpt-4.1-mini,gpt-4.1").split(",") if x.strip()))
    image_base: str = field(default_factory=lambda: os.getenv("IMAGE_BASE_URL", "https://api.openai.com/v1").rstrip("/"))
    image_key: str = field(default_factory=lambda: os.getenv("IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY", ""))
    image_model: str = field(default_factory=lambda: os.getenv("IMAGE_MODEL", "gpt-image-1"))
    max_output_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_OUTPUT_TOKENS", "4096")))
    session_hours: int = 24
    context_chars: int = 60000

    def validate(self):
        if not self.password_hash.startswith("scrypt:"):
            raise RuntimeError("Configure ADMIN_PASSWORD_HASH using scripts/configure.py first.")
        if not self.origins or "*" in self.origins or not self.models:
            raise RuntimeError("Explicit APP_ORIGINS and at least one CHAT_MODELS entry are required.")
        if not 1 <= self.max_output_tokens <= 32768:
            raise RuntimeError("MAX_OUTPUT_TOKENS must be between 1 and 32768.")
