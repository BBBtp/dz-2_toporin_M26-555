"""JSON storage helpers; no command parsing or database rules live here."""

import json
import os

from src.primitive_db.constants import table_file


def load_metadata(filepath):
    """Load database schema, or return an empty schema for a new database."""
    try:
        with open(filepath, encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return {}


def save_metadata(filepath, data):
    """Save schema as readable UTF-8 JSON."""
    with open(filepath, "w", encoding="utf-8") as target:
        json.dump(data, target, ensure_ascii=False, indent=2)


def load_table_data(table_name):
    """Load rows of one table, returning an empty list for a new table."""
    try:
        with open(table_file(table_name), encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return []


def save_table_data(table_name, data):
    """Save rows of one table in its own JSON file."""
    os.makedirs(os.path.dirname(table_file(table_name)), exist_ok=True)
    with open(table_file(table_name), "w", encoding="utf-8") as target:
        json.dump(data, target, ensure_ascii=False, indent=2)


def remove_table_data(table_name):
    """Remove a dropped table's file if it exists."""
    try:
        os.remove(table_file(table_name))
    except FileNotFoundError:
        pass
