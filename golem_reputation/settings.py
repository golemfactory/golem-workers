import os
from pathlib import Path
from typing import Optional

import appdirs

APPLICATION_NAME = "golem_reputation"
APPLICATION_AUTHOR = "golemfactory"

DEFAULT_DATADIR = Path(
    os.getenv(
        "GOLEM_REPUTATION_DATADIR", appdirs.user_data_dir(APPLICATION_NAME, APPLICATION_AUTHOR)
    )
)


def get_datadir(datadir: Optional[Path] = None) -> Path:
    if not datadir:
        datadir = DEFAULT_DATADIR
    datadir.mkdir(parents=True, exist_ok=True)
    return datadir


def get_reputation_db_config(datadir: Optional[Path] = None):
    db_dir = get_datadir(datadir) / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    migrations_dir = Path(__file__).parent / "migrations"

    db_file = db_dir / "reputation.sqlite3"

    models_path = "golem_reputation.models"

    tortoise_config = {
        "connections": {
            "default": f"sqlite://{db_file.resolve()}",
        },
        "apps": {
            "models": {
                "models": [models_path, "aerich.models"],
                "default_connection": "default",
            }
        },
    }
    aerich_config = {
        "tortoise_config": tortoise_config,
        "location": str(migrations_dir.resolve()),
        "app": "models",
    }
    return {"db": tortoise_config, "migrations": aerich_config}
