from typing import Dict, Sequence

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from golem_workers.models import ImportableContext


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    global_contexts: Sequence[ImportableContext] = Field(default_factory=list)

    yagna_appkey: str

    golem_registry_stats: bool = True

    logging_config: Dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "loggers": {
            "golem_workers": {
                "level": "DEBUG",
            },
        },
    }
