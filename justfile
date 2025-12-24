# Default recipe to display help
default:
    @just --list

# Start the development server
server:
    FLASK_APP=launcher.py FLASK_ENV=development uv run flask run --port 5001

# Start the server with custom host and port
serve host="0.0.0.0" port="5001":
    FLASK_APP=launcher.py uv run python launcher.py

# Run database migrations (upgrade to latest)
migrate-up:
    FLASK_APP=launcher.py uv run flask db upgrade

# Rollback database migration by one step
migrate-down:
    FLASK_APP=launcher.py uv run flask db downgrade

# Create a new migration
migrate-create message:
    FLASK_APP=launcher.py uv run flask db migrate -m "{{message}}"

# Show current migration status
migrate-status:
    FLASK_APP=launcher.py uv run flask db current

# Show migration history
migrate-history:
    FLASK_APP=launcher.py uv run flask db history

# Initialize the database (first time setup)
db-init:
    FLASK_APP=launcher.py uv run flask db init

# Run tests
test:
    uv run pytest

# Lint code with ruff
lint:
    uv run ruff check .

# Fix linting issues automatically
lint-fix:
    uv run ruff check --fix .

# Format code with black
format:
    uv run black .

# Type check with mypy
typecheck:
    uv run mypy .

# Run all checks (lint, format check, typecheck)
check:
    uv run ruff check .
    uv run black --check .
    uv run mypy .

# Install dependencies
install:
    uv sync

# Frontend development server
frontend-dev:
    cd frontend && pnpm dev

# Frontend preview build
frontend-preview:
    cd frontend && pnpm preview

# Build frontend for production
frontend-build:
    cd frontend && pnpm build

# Lint frontend code
frontend-lint:
    cd frontend && pnpm lint

# Format frontend code
frontend-format:
    cd frontend && pnpm format

# Combined lint (backend + frontend)
lint-all:
    uv run ruff check .
    cd frontend && pnpm lint

# Fix linting issues (backend + frontend)
lint-fix-all:
    uv run ruff check --fix .
    cd frontend && pnpm lint

# Combined format (backend + frontend)
format-all:
    uv run black .
    cd frontend && pnpm format

# Run both backend and frontend dev servers concurrently
run:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    just server & just frontend-dev
