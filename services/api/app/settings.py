from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://halfspace:halfspace@localhost:5432/halfspace"
    redis_url: str = "redis://localhost:6379/0"
    stats_bomb_data_url: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    competition_ids: str = ""
    openai_api_key: str = ""
    openai_base_url: str | None = None
    search_llm_model: str = "gpt-4o-mini"
    search_embedding_model: str = "text-embedding-3-small"
    search_embedding_dimensions: int = 256
    search_cross_encoder: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    search_cache_ttl_seconds: int = 900
    search_cache_similarity: float = 0.92
    search_rrf_k: int = 60
    search_candidate_limit: int = 50
    search_cost_input_per_million: float = 0.15
    search_cost_output_per_million: float = 0.60
    search_embedding_cost_per_million: float = 0.02
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    otel_enabled: bool = False
    scout_max_rows: int = 200
    scout_statement_timeout_ms: int = 3000
    scout_max_rounds: int = 2
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")


settings = Settings()
