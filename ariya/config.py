import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    db_path: str = os.getenv("ARIYA_DB_PATH", "./ariya.db")
    host: str = os.getenv("ARIYA_HOST", "127.0.0.1")
    port: int = int(os.getenv("ARIYA_PORT", "8000"))
    default_provider: str = os.getenv("ARIYA_DEFAULT_PROVIDER", "anthropic")
    default_model: str = os.getenv("ARIYA_DEFAULT_MODEL", "claude-opus-4-7")
    mock_mode_env: str = os.getenv("ARIYA_MOCK_MODE", "auto")

    @property
    def mock_mode(self) -> bool:
        if self.mock_mode_env == "true":
            return True
        if self.mock_mode_env == "false":
            return False
        # auto: mock if no keys configured
        return not (self.anthropic_api_key or self.openai_api_key)

settings = Settings()
