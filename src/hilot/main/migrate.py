import logging
from argparse import Namespace

from alembic.config import CommandLine, Config

from .config.loader import load_config
from .config.schemas import MigrateSchema


def main() -> None:
    # show the applied migrations
    logging.basicConfig()
    logging.getLogger("alembic").setLevel(logging.INFO)

    command_line: CommandLine = CommandLine(prog="hilot-migrate")
    options: Namespace = command_line.parser.parse_args()

    # argparse leaves `cmd` unset when no command is given
    if not hasattr(options, "cmd"):
        command_line.parser.error("too few arguments")

    schema: MigrateSchema = load_config(schema=MigrateSchema)

    config: Config = Config(cmd_opts=options)
    config.set_main_option("script_location", "hilot.infrastructure.database.sql:migrations")
    config.attributes["database_url"] = schema.database.url

    command_line.run_cmd(config, options)


if __name__ == "__main__":
    main()
