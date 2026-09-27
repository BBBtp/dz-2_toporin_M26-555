"""Behavioral checks for table management, CRUD, parsing, and persistence."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from src.primitive_db import core, engine, parser, utils
from src.primitive_db.decorators import create_cacher


class DatabaseTests(unittest.TestCase):
    """Run each storage test in an isolated temporary working directory."""

    def setUp(self):
        self.previous_directory = os.getcwd()
        self.temp_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temp_directory.name)

    def tearDown(self):
        os.chdir(self.previous_directory)
        self.temp_directory.cleanup()

    def test_create_and_drop_table(self):
        metadata = {}
        self.assertIs(
            core.create_table(metadata, "users", ["name:str", "age:int"]), metadata
        )
        self.assertEqual(metadata["users"], ["ID:int", "name:str", "age:int"])
        self.assertIsNone(core.create_table(metadata, "users", ["name:str"]))
        self.assertIsNone(core.create_table(metadata, "bad/name", ["name:str"]))
        self.assertIsNone(core.create_table(metadata, "bad", ["name:float"]))
        with patch("builtins.input", return_value="n"):
            self.assertIsNone(core.drop_table(metadata, "users"))
        self.assertIn("users", metadata)
        with patch("builtins.input", return_value="y"):
            self.assertIs(core.drop_table(metadata, "users"), metadata)
        self.assertNotIn("users", metadata)

    def test_missing_table_is_reported_without_confirmation(self):
        output = io.StringIO()
        unexpected_prompt = patch(
            "builtins.input", side_effect=AssertionError("unexpected prompt")
        )
        with (
            unexpected_prompt as ask,
            contextlib.redirect_stdout(output),
        ):
            self.assertIsNone(core.drop_table({}, "missing"))
        ask.assert_not_called()
        self.assertIn("missing", output.getvalue())

    def test_json_storage(self):
        self.assertEqual(utils.load_metadata("missing.json"), {})
        utils.save_metadata("db_meta.json", {"users": ["ID:int"]})
        self.assertEqual(utils.load_metadata("db_meta.json"), {"users": ["ID:int"]})
        self.assertEqual(utils.load_table_data("users"), [])
        utils.save_table_data("users", [{"ID": 1}])
        self.assertEqual(utils.load_table_data("users"), [{"ID": 1}])
        utils.remove_table_data("users")
        self.assertEqual(utils.load_table_data("users"), [])

    def test_insert_select_update_delete_and_id(self):
        metadata = {"users": ["ID:int", "name:str", "age:int", "active:bool"]}
        first = core.insert(metadata, "users", ["Sergei", "28", "true"], [])
        self.assertEqual(
            first[0], {"ID": 1, "name": "Sergei", "age": 28, "active": True}
        )
        second = core.insert(metadata, "users", ["Anna", "29", "false"], first)
        self.assertEqual(core.select(second, {"age": 28}), [first[0]])
        changed = core.update(second, {"age": 30}, {"name": "Sergei"})
        self.assertEqual(changed[0]["age"], 30)
        self.assertEqual(second[0]["age"], 28)
        self.assertEqual(core.select(changed, {"age": 28}), [])
        with patch("builtins.input", return_value="y"):
            remaining = core.delete(changed, {"ID": 1})
        self.assertEqual(len(remaining), 1)
        next_data = core.insert(metadata, "users", ["Nina", 20, True], remaining)
        self.assertEqual(next_data[-1]["ID"], 3)

    def test_invalid_values_leave_input_unchanged(self):
        metadata = {"users": ["ID:int", "age:int", "active:bool"]}
        original = [{"ID": 1, "age": 20, "active": True}]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(
                core.insert(metadata, "users", ["oops", "true"], original)
            )
            self.assertIsNone(core.insert(metadata, "users", [21], original))
        self.assertEqual(len(original), 1)

    def test_parsing_quoted_values_and_typed_conditions(self):
        metadata = {"users": ["ID:int", "name:str", "age:int", "active:bool"]}
        tokens = parser.tokenize('insert into users values ("Sergei Ivanov", 28, true)')
        self.assertEqual(
            parser.parse_values(tokens[4:]), ["Sergei Ivanov", "28", "true"]
        )
        self.assertEqual(
            parser.parse_where(["where", "age", "=", "28"], metadata, "users"),
            {"age": 28},
        )
        self.assertEqual(
            parser.parse_where(["where", "active", "=", "false"], metadata, "users"),
            {"active": False},
        )

    def test_quoted_punctuation_is_a_value_not_a_separator(self):
        for literal in (",", "()", "=", "a,b"):
            with self.subTest(literal=literal):
                tokens = parser.tokenize(f'insert into items values ("{literal}")')
                self.assertEqual(parser.parse_values(tokens[4:]), [literal])

    def test_quoted_keyword_in_update(self):
        metadata = {}
        with contextlib.redirect_stdout(io.StringIO()):
            engine.execute_command("create_table users name:str", metadata)
            engine.execute_command('insert into users values ("Sergei")', metadata)
            engine.execute_command(
                'update users set name = "where" where ID = 1', metadata
            )
            engine.execute_command('insert into users values (",")', metadata)
            engine.execute_command("create_table where where:str", metadata)
            engine.execute_command('insert into where values ("before")', metadata)
            engine.execute_command(
                'update where set where = "where" where ID = 1', metadata
            )
        self.assertEqual(utils.load_table_data("users")[0]["name"], "where")
        self.assertEqual(utils.load_table_data("users")[1]["name"], ",")
        self.assertEqual(utils.load_table_data("where")[0]["where"], "where")

    def test_cacher_calls_source_once(self):
        cache = create_cacher()
        calls = []

        def calculate():
            calls.append(1)
            return 42

        self.assertEqual(cache("answer", calculate), 42)
        self.assertEqual(cache("answer", calculate), 42)
        self.assertEqual(len(calls), 1)

    def test_full_command_sequence_and_confirmation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            metadata = {}
            engine.execute_command("create_table users name:str age:int", metadata)
            self.assertTrue(os.path.exists("db_meta.json"))
            engine.execute_command('insert into users values ("Sergei", 28)', metadata)
            self.assertEqual(len(utils.load_table_data("users")), 1)
            engine.execute_command("update users set age = 29 where ID = 1", metadata)
            self.assertEqual(utils.load_table_data("users")[0]["age"], 29)
            engine.execute_command("select from users where age = 29", metadata)
            with patch("builtins.input", return_value="n"):
                engine.execute_command("delete from users where ID = 1", metadata)
            self.assertEqual(len(utils.load_table_data("users")), 1)
            with patch("builtins.input", return_value="y"):
                engine.execute_command("delete from users where ID = 1", metadata)
            self.assertEqual(utils.load_table_data("users"), [])
            with patch("builtins.input", return_value="y"):
                engine.execute_command("drop_table users", metadata)
            self.assertEqual(utils.load_metadata("db_meta.json"), {})


if __name__ == "__main__":
    unittest.main()
