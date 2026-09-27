"""Reusable error handling, confirmation, timing, and caching."""

import time
from functools import wraps


def handle_db_errors(func):
    """Print expected database errors and leave unsuccessful calls as None."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            print("Ошибка: Файл данных не найден.")
        except KeyError as error:
            print(f"Ошибка: Таблица или столбец {error} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")
        return None

    return wrapper


def confirm_action(action_name, validate=None):
    """Validate, then require an explicit y before a destructive action."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if validate is not None:
                validate(*args, **kwargs)
            answer = input(f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: ')
            if answer.strip().lower() != "y":
                print("Операция отменена.")
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_time(func):
    """Report a function's elapsed monotonic time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.monotonic()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд")

    return wrapper


def create_cacher():
    """Return a closure that memoizes values supplied by a callable."""
    results = {}

    def cache_result(key, value_func):
        if key not in results:
            results[key] = value_func()
        return results[key]

    return cache_result
