"""Interactive loop and dispatch for database commands."""

from src.primitive_db.constants import COMMAND_PROMPT, META_FILE
from src.primitive_db.core import (
    column_types,
    create_table,
    delete,
    drop_table,
    insert,
    select,
    update,
)
from src.primitive_db.decorators import handle_db_errors
from src.primitive_db.parser import (
    parse_assignment,
    parse_values,
    parse_where,
    tokenize,
)
from src.primitive_db.utils import (
    load_metadata,
    load_table_data,
    remove_table_data,
    save_metadata,
    save_table_data,
)


def print_help():
    """Show all supported table and record commands."""
    print("\n***Примитивная база данных***")
    print("create_table <таблица> <столбец:тип> ... — создать таблицу")
    print("list_tables — показать все таблицы")
    print("drop_table <таблица> — удалить таблицу")
    print('insert into <таблица> values ("строка", 28, true) — добавить запись')
    print("select from <таблица> [where <столбец> = <значение>] — выборка")
    print("update <таблица> set <столбец> = <значение> where ... — обновление")
    print("delete from <таблица> where <столбец> = <значение> — удаление")
    print("info <таблица> — структура и количество записей")
    print("help — справка; exit — выход\n")


def welcome():
    """Print the greeting and help at program start."""
    print("DB project is running!")
    print_help()


def read_command():
    """Read one nonempty command, using prompt when installed."""
    try:
        import prompt
    except ImportError:
        return input(COMMAND_PROMPT)
    return prompt.string(COMMAND_PROMPT)


def print_rows(columns, rows):
    """Show query results as a PrettyTable, with a minimal offline fallback."""
    try:
        from prettytable import PrettyTable
    except ImportError:
        print(" | ".join(columns))
        for row in rows:
            print(" | ".join(str(row[column]) for column in columns))
        return
    table = PrettyTable()
    table.field_names = columns
    for row in rows:
        table.add_row([row[column] for column in columns])
    print(table)


def _create_table(args, metadata):
    if len(args) < 2:
        raise ValueError("Укажите имя таблицы и хотя бы один столбец.")
    table_name = args[0]
    if create_table(metadata, table_name, args[1:]) is None:
        return
    save_metadata(META_FILE, metadata)
    save_table_data(table_name, [])
    print(
        f'Таблица "{table_name}" успешно создана со столбцами: '
        + ", ".join(metadata[table_name])
    )


def _drop_table(args, metadata):
    if len(args) != 1:
        raise ValueError("Укажите одно имя таблицы.")
    table_name = args[0]
    if drop_table(metadata, table_name) is None:
        return
    save_metadata(META_FILE, metadata)
    remove_table_data(table_name)
    print(f'Таблица "{table_name}" успешно удалена.')


def _insert(args, metadata):
    if len(args) < 6 or args[0].lower() != "into" or args[2].lower() != "values":
        raise ValueError("Используйте: insert into <таблица> values (...).")
    table_name = args[1]
    values = parse_values(args[3:])
    current = load_table_data(table_name)
    changed = insert(metadata, table_name, values, current)
    if changed is None:
        return
    save_table_data(table_name, changed)
    print(
        f'Запись с ID={changed[-1]["ID"]} успешно добавлена в таблицу "{table_name}".'
    )


def _select(args, metadata):
    if len(args) < 2 or args[0].lower() != "from":
        raise ValueError("Используйте: select from <таблица> [where ...].")
    table_name = args[1]
    columns = list(column_types(metadata, table_name))
    if len(args) == 2:
        condition = None
    else:
        condition = parse_where(args[2:], metadata, table_name)
    rows = select(load_table_data(table_name), condition)
    if rows is not None:
        print_rows(columns, rows)


def _update(args, metadata):
    if len(args) < 9 or args[1].lower() != "set":
        raise ValueError("Используйте: update <таблица> set ... where ...")
    table_name = args[0]
    where_index = next(
        (index for index, token in enumerate(args) if token.lower() == "where"),
        -1,
    )
    if where_index < 0:
        raise ValueError("Ожидалось условие where.")
    schema = column_types(metadata, table_name)
    changes = parse_assignment(args[2:where_index], schema)
    if "ID" in changes:
        raise ValueError("Столбец ID изменять нельзя.")
    condition = parse_where(args[where_index:], metadata, table_name)
    current = load_table_data(table_name)
    changed = update(current, changes, condition)
    if changed is None:
        return
    save_table_data(table_name, changed)
    count = sum(old != new for old, new in zip(current, changed, strict=True))
    print(f'В таблице "{table_name}" обновлено записей: {count}.')


def _delete(args, metadata):
    if len(args) < 6 or args[0].lower() != "from":
        raise ValueError("Используйте: delete from <таблица> where ...")
    table_name = args[1]
    condition = parse_where(args[2:], metadata, table_name)
    current = load_table_data(table_name)
    changed = delete(current, condition)
    if changed is None:
        return
    save_table_data(table_name, changed)
    print(f'Из таблицы "{table_name}" удалено записей: {len(current) - len(changed)}.')


def _info(args, metadata):
    if len(args) != 1:
        raise ValueError("Укажите одно имя таблицы.")
    table_name = args[0]
    columns = column_types(metadata, table_name)
    print(f"Таблица: {table_name}")
    print("Столбцы: " + ", ".join(f"{name}:{kind}" for name, kind in columns.items()))
    print(f"Количество записей: {len(load_table_data(table_name))}")


@handle_db_errors
def execute_command(raw_command, metadata):
    """Execute one command; return False only when the user asks to exit."""
    args = tokenize(raw_command)
    if not args:
        return True
    command = args.pop(0).lower()
    if command == "exit":
        if args:
            raise ValueError("Команда exit не принимает аргументы.")
        return False
    if command == "help":
        print_help()
    elif command == "create_table":
        _create_table(args, metadata)
    elif command == "drop_table":
        _drop_table(args, metadata)
    elif command == "list_tables":
        if args:
            raise ValueError("Команда list_tables не принимает аргументы.")
        for table_name in metadata:
            print(f"- {table_name}")
    elif command == "insert":
        _insert(args, metadata)
    elif command == "select":
        _select(args, metadata)
    elif command == "update":
        _update(args, metadata)
    elif command == "delete":
        _delete(args, metadata)
    elif command == "info":
        _info(args, metadata)
    else:
        print(f"Функции {command} нет. Попробуйте снова.")
    return True


def run():
    """Run the read/execute loop until exit or end-of-input."""
    welcome()
    while True:
        metadata = load_metadata(META_FILE)
        try:
            command = read_command()
        except (EOFError, KeyboardInterrupt):
            print("\nРабота завершена.")
            return
        if execute_command(command, metadata) is False:
            print("Работа завершена.")
            return
