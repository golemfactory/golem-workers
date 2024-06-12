from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    yagna_appkey: str

    golem_registry_stats: bool = True

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8'
    )
