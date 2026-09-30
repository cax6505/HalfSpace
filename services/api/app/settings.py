from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://halfspace:halfspace@localhost:5432/halfspace"
    redis_url: str = "redis://localhost:6379/0"
    stats_bomb_data_url: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    competition_ids: str = ""
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")


settings = Settings()
