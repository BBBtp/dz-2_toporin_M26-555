.PHONY: install project run build publish package-install lint test

POETRY ?= poetry

install:
	$(POETRY) install

project:
	$(POETRY) run project

run:
	$(POETRY) run database

build:
	$(POETRY) build

publish:
	$(POETRY) publish --dry-run

package-install:
	python3 -m pip install dist/*.whl

lint:
	$(POETRY) run ruff check .

test:
	$(POETRY) run python -m unittest discover -s tests -v
