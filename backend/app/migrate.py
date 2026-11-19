"""Apply versioned migrations, including the pre-Alembic development database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import engine


def upgrade_database() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    tables = set(inspect(engine).get_table_names())
    legacy = {"products", "hotspots", "workflows", "agent_events"}
    if "alembic_version" not in tables and legacy.issubset(tables):
        command.stamp(config, "0001_initial")
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade_database()
