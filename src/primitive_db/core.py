"""Table schema and CRUD business rules."""

import json

from src.primitive_db.constants import ID_COLUMN, VALID_TYPES
from src.primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from src.primitive_db.utils import load_table_data

_cached_select = create_cacher()


def schema_for(metadata, table_name):
    """Return a table schema or signal an unknown table."""
    if table_name not in metadata:
        raise KeyError(table_name)
    return metadata[table_name]


def column_types(metadata, table_name):
    """Return a mapping from column names to declared data types."""
    return dict(column.split(":", 1) for column in schema_for(metadata, table_name))


def convert_value(value, data_type):
    """Convert one user value according to its declared column type."""
    if data_type == "str":
        if not isinstance(value, str):
            raise ValueError(f"Ожидалась строка, получено: {value}")
        return value
    if data_type == "int":
        if isinstance(value, bool):
            raise ValueError(f"Ожидалось целое число, получено: {value}")
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Ожидалось целое число, получено: {value}") from error
    if data_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError(f"Ожидалось true или false, получено: {value}")
    raise ValueError(f"Неподдерживаемый тип: {data_type}")


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Validate and add a new table schema with an automatic ID column."""
    if not table_name.isidentifier():
        raise ValueError(f"Некорректное имя таблицы: {table_name}")
    if table_name in metadata:
        raise ValueError(f'Таблица "{table_name}" уже существует.')
    if not columns:
        raise ValueError("Нужно указать хотя бы один столбец.")
    parsed = []
    names = {ID_COLUMN}
    for column in columns:
        if not isinstance(column, str) or column.count(":") != 1:
            raise ValueError(f"Некорректное значение: {column}")
        name, data_type = column.split(":", 1)
        if not name.isidentifier() or name in names:
            raise ValueError(f"Некорректное имя столбца: {name}")
        if data_type not in VALID_TYPES:
            raise ValueError(f"Некорректное значение: {data_type}")
        names.add(name)
        parsed.append(f"{name}:{data_type}")
    metadata[table_name] = [f"{ID_COLUMN}:int", *parsed]
    return metadata


@handle_db_errors
@confirm_action("удаление таблицы", validate=schema_for)
def drop_table(metadata, table_name):
    """Remove an existing table from metadata after confirmation."""
    del metadata[table_name]
    return metadata


@handle_db_errors
@log_time
def insert(metadata, table_name, values, table_data=None):
    """Validate a complete row, generate its ID, and return new table data."""
    schema = column_types(metadata, table_name)
    if table_data is None:
        table_data = load_table_data(table_name)
    user_columns = list(schema.items())[1:]
    if len(values) != len(user_columns):
        raise ValueError(
            f"Ожидалось {len(user_columns)} значений, получено {len(values)}"
        )
    next_id = max((row[ID_COLUMN] for row in table_data), default=0) + 1
    row = {ID_COLUMN: next_id}
    for (column, data_type), value in zip(user_columns, values, strict=True):
        row[column] = convert_value(value, data_type)
    return [*table_data, row]


@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Return all rows or rows matching the typed condition; cache equal queries."""
    key = json.dumps([table_data, where_clause], sort_keys=True, ensure_ascii=False)

    def find_rows():
        return [
            row.copy()
            for row in table_data
            if where_clause is None
            or all(row.get(column) == value for column, value in where_clause.items())
        ]

    return [row.copy() for row in _cached_select(key, find_rows)]


@handle_db_errors
def update(table_data, set_clause, where_clause):
    """Update matching rows and return fresh data without mutating the input."""
    if not where_clause or not set_clause:
        raise ValueError("Нужны условия set и where.")
    result = []
    for row in table_data:
        updated = row.copy()
        if all(row.get(column) == value for column, value in where_clause.items()):
            updated.update(set_clause)
        result.append(updated)
    return result


@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Delete matching rows after confirmation, returning fresh table data."""
    if not where_clause:
        raise ValueError("Для удаления необходимо условие where.")
    return [
        row.copy()
        for row in table_data
        if not all(row.get(column) == value for column, value in where_clause.items())
    ]
