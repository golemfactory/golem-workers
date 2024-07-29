from pathlib import Path

import click

from golem_reputation.settings import DEFAULT_DATADIR


def with_datadir(cli_func):
    return click.option(
        "--datadir",
        type=Path,
        help=f"Ray on Golem's data directory. By default, uses a system data directory: {DEFAULT_DATADIR}",
    )(cli_func)
