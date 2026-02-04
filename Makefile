.PHONY: help install dev-install test lint format clean health-check

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -r requirements.txt

dev-install:  ## Install all dependencies (dev + browser)
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -r requirements-browser.txt
	pip install pre-commit
	pre-commit install

test:  ## Run test suite
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=src --cov-report=html --cov-report=term

lint:  ## Run all linters
	ruff check .
	mypy src

format:  ## Auto-format code
	ruff format .
	ruff check . --fix

clean:  ## Remove generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.mypy_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.ruff_cache' -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage

validate-config:  ## Validate configuration file
	python -m src.engine --validate-config

health-check:  ## Run browser automation health check
	python scripts/browser_health_check.py --config config/config.json

daily-digest:  ## Generate daily digest (HTML)
	python scripts/dm_daily_digest.py --hours 24 --format html --important --open

my-tasks:  ## Check your personal tasks
	python scripts/check_my_tasks.py

pre-commit:  ## Run pre-commit hooks on all files
	pre-commit run --all-files

setup-env:  ## Create .env from example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please edit it with your API keys."; \
	else \
		echo ".env already exists. Skipping."; \
	fi
