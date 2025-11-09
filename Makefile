# Makefile

# ------- Configurable vars -------
HOST ?= 127.0.0.1
PORT ?= 8000
UVICORN ?= uvicorn
APP ?= app.main:create_app
ALEMBIC ?= alembic

# Always prefer venv binaries
export PATH := /opt/r4t/.venv/bin:$(PATH)

.DEFAULT_GOAL := help

.PHONY: help dev lint type test precommit install check-health format fmt check fix clean \
        db-upgrade db-downgrade db-current db-revision db-reset db

help:
	@echo "Targets:"
	@echo "  install        - install dev deps + pre-commit"
	@echo "  dev            - run uvicorn in reload mode"
	@echo "  lint           - ruff check (alembic/ excluded)"
	@echo "  format|fmt     - ruff format (alembic/ excluded)"
	@echo "  fix            - ruff check --fix + format"
	@echo "  type           - mypy (cache in /tmp)"
	@echo "  test           - pytest -q"
	@echo "  check          - lint + type + test"
	@echo "  check-health   - curl /healthz + /readyz against $(HOST):$(PORT)"
	@echo "  db             - alembic upgrade head"
	@echo "  db-upgrade     - alembic upgrade head"
	@echo "  db-downgrade   - alembic downgrade -1"
	@echo "  db-current     - alembic current"
	@echo "  db-revision    - make db-revision msg='message'"
	@echo "  db-reset       - drop sessions/card_assets; re-apply migrations"
	@echo "  clean          - remove caches"

# ------- Setup -------
install:
	python -m pip install -U pip
	pip install -r requirements-dev.txt
	pre-commit install

# ------- Development -------
dev:
	$(UVICORN) $(APP) --factory --host $(HOST) --port $(PORT) --reload

# ------- Code Quality -------
lint:
	ruff check --fix --no-cache . --exclude alembic/

format fmt:
	ruff format --no-cache . --exclude alembic/

fix:
	ruff check --fix --no-cache . --exclude alembic/
	ruff format --no-cache . --exclude alembic/

type:
	MYPY_CACHE_DIR=/tmp/mypy_cache mypy .

test:
	pytest -q -p no:cacheprovider

check:
	$(MAKE) lint
	$(MAKE) type
	$(MAKE) test

precommit:
	pre-commit run --all-files

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache /tmp/mypy_cache

# ------- Health Check -------
check-health:
	curl -fsS http://$(HOST):$(PORT)/healthz && echo
	curl -fsS http://$(HOST):$(PORT)/readyz && echo

# ------- Database Migrations -------
db-upgrade db:
	$(ALEMBIC) upgrade head

db-downgrade:
	$(ALEMBIC) downgrade -1

db-current:
	$(ALEMBIC) current

db-revision:
	@test -n "$(msg)" || (echo "Usage: make db-revision msg='your message'"; exit 1)
	$(ALEMBIC) revision -m "$(msg)"

# ------- Database Reset -------
db-reset:
	@echo "⚠️  This will drop and recreate Alembic-managed tables!"
	@test -n "$$DATABASE_URL" || (echo "Error: DATABASE_URL is not set."; exit 1)
	psql "$$DATABASE_URL" -c "DROP TABLE IF EXISTS sessions CASCADE;" || true
	psql "$$DATABASE_URL" -c "DROP TABLE IF EXISTS card_assets CASCADE;" || true
	$(ALEMBIC) downgrade base
	$(ALEMBIC) upgrade head
