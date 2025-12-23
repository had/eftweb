# Default recipe to display help
default:
    @just --list

# Start the development server
server:
    FLASK_APP=launcher.py FLASK_ENV=development uv run flask run

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
