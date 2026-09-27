"""Parse the small command language used by the interactive database."""

import shlex

from src.primitive_db.constants import ID_COLUMN
from src.primitive_db.core import column_types, convert_value


def tokenize(command):
    """Split command syntax while preserving quotes around literal values."""
    tokens = []
    current = []
    quote = None
    escaped = False

    def finish_token():
        if current:
            tokens.append("".join(current))
            current.clear()

    for character in command:
        if quote is not None:
            current.append(character)
            if escaped:
                escaped = False
            elif character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = None
        elif character in ("'", '"'):
            quote = character
            current.append(character)
        elif character in "=(),":
            finish_token()
            tokens.append(character)
        elif character.isspace():
            finish_token()
        else:
            current.append(character)
    if quote is not None:
        raise ValueError("Незакрытая кавычка в команде.")
    finish_token()
    return tokens


def decode_value(token):
    """Remove shell-style quoting from one literal without losing punctuation."""
    values = shlex.split(token)
    if len(values) != 1:
        raise ValueError(f"Некорректное значение: {token}")
    return values[0]


def parse_values(tokens):
    """Parse a parenthesized, comma-separated list of values."""
    if len(tokens) < 3 or tokens[0] != "(" or tokens[-1] != ")":
        raise ValueError("Ожидался список значений в круглых скобках.")
    values = []
    expect_value = True
    for token in tokens[1:-1]:
        if expect_value:
            if token in (",", "(", ")"):
                raise ValueError("Некорректный список значений.")
            values.append(decode_value(token))
        elif token != ",":
            raise ValueError("Разделите значения запятыми.")
        expect_value = not expect_value
    if not values or expect_value:
        raise ValueError("Некорректный список значений.")
    return values


def parse_assignment(tokens, schema):
    """Parse column = value and convert value to the declared type."""
    if len(tokens) != 3 or tokens[1] != "=":
        raise ValueError("Ожидалось условие вида столбец = значение.")
    column, _, raw_value = tokens
    if column not in schema:
        raise KeyError(column)
    return {column: convert_value(decode_value(raw_value), schema[column])}


def parse_where(tokens, metadata, table_name):
    """Parse a typed where condition for an existing table."""
    if not tokens or tokens[0].lower() != "where":
        raise ValueError("Ожидалось условие where.")
    return parse_assignment(tokens[1:], column_types(metadata, table_name))


def parse_set(tokens, metadata, table_name):
    """Parse a typed set assignment and reject edits to the primary key."""
    if not tokens or tokens[0].lower() != "set":
        raise ValueError("Ожидалось условие set.")
    assignment = parse_assignment(tokens[1:], column_types(metadata, table_name))
    if ID_COLUMN in assignment:
        raise ValueError("Столбец ID изменять нельзя.")
    return assignment
