.PHONY: dev lint type test precommit install

install:
	python -m pip install -U pip
	pip install -r requirements-dev.txt

dev:
	uvicorn roll4treasure-main.app.main:app --reload --port 8001

lint:
	ruff check .

type:
	mypy .

test:
	pytest

precommit:
	pre-commit install
	pre-commit run --all-files
