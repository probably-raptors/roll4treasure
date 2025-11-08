# Makefile

# ------- Configurable vars -------
HOST ?= 127.0.0.1
PORT ?= 8000
UVICORN ?= uvicorn
APP ?= app.main:create_app

.PHONY: dev lint type test precommit install check-health format

install:
	python -m pip install -U pip
	pip install -r requirements-dev.txt
	pre-commit install

dev:
	  --factory --host  --port  --reload

lint:
	ruff check .

format:
	ruff format .

type:
	mypy .

test:
	pytest -q

precommit:
	pre-commit run --all-files

check-health:
	curl -sS http://127.0.0.1:8000/healthz && echo
	curl -sS http://127.0.0.1:8000/readyz && echo
