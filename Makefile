# =============================================================================
# BAKY Developer CLI
# All commands run inside Docker containers. No local Python/Node required.
#
# Services:
#   web     — Django app          http://localhost:8010
#   db      — PostgreSQL 16       localhost:5433
#   mailpit — Email testing UI    http://localhost:8026
# =============================================================================

.PHONY: up down build restart migrate makemigrations test lint shell dbshell \
        createsuperuser seed logs manage e2e validate clean

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart

clean:
	docker compose down -v

# ---------------------------------------------------------------------------
# Django management
# ---------------------------------------------------------------------------

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

shell:
	docker compose exec web python manage.py shell

dbshell:
	docker compose exec db psql -U baky -d baky

createsuperuser:
	docker compose exec web python manage.py createsuperuser

seed:
	docker compose exec web python manage.py seed_all

manage:
	docker compose exec web python manage.py $(CMD)

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

test:
	docker compose exec web pytest --ignore=tests/e2e $(ARGS)

coverage:  ## Run tests with coverage report
	docker compose exec web pytest --cov=apps --cov-report=term-missing $(ARGS)

lint:
	docker compose exec web ruff check .
	docker compose exec web ruff format --check .
	docker compose exec web djlint templates/ --lint
	docker compose exec web djlint templates/ --check

e2e:
	docker compose exec web pytest tests/e2e/ -v --tb=short

validate: lint test e2e

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

logs:
	docker compose logs -f
