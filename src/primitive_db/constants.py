"""Named settings shared across database modules."""

import os

META_FILE = "db_meta.json"
DATA_DIR = "data"
VALID_TYPES = ("int", "str", "bool")
ID_COLUMN = "ID"
COMMAND_PROMPT = "Введите команду: "


def table_file(table_name):
    """Return a safe path to a table's data file."""
    if not table_name.isidentifier():
        raise ValueError(f"Некорректное имя таблицы: {table_name}")
    return os.path.join(DATA_DIR, f"{table_name}.json")
