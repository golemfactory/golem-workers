from golem_reputation.entrypoints.cli.database import database_cli
from golem_reputation.entrypoints.cli.reputation import reputation_cli as cli


cli.add_command(database_cli)


def main():
    cli()


if __name__ == "__main__":
    main()
