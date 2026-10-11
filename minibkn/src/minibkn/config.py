"""Application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="MINIBKN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MiniBKN"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite+aiosqlite:///./data/minibkn.db"
    data_dir: Path = Path("./data")
    log_level: str = "INFO"
    api_key: str = ""
    authorization_enabled: bool = False
    authorization_policy_file: Path | None = None
    embedding_provider: str = "token_hashing"
    embedding_dimensions: int = Field(default=128, ge=32, le=4096)
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_api_key_file: Path | None = None
    embedding_batch_size: int = Field(default=32, ge=1, le=128)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    embedding_cache_entries: int = Field(default=10000, ge=0, le=1000000)
    embedding_failover_enabled: bool = True
    api_base_url: str = "http://127.0.0.1:8000"
    llm_provider: str = "extractive"
    llm_api_key: str = ""
    llm_api_key_file: Path | None = None
    llm_base_url: str = ""
    llm_model: str = ""
    document_knowledge_provider: str = "disabled"
    document_knowledge_degrade_when_disabled: bool = True
    lightrag_endpoint_map_file: Path | None = None
    lightrag_api_key: str = ""
    lightrag_api_key_file: Path | None = None
    lightrag_query_mode: str = "mix"
    lightrag_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    evaluation_results_dir: Path = Path("./evals/results")

    def prepare_directories(self) -> None:
        """Create writable local directories required by the application."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
