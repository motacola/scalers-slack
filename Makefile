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

validate-config:  ## Validate configuration files and environment
	python3 scripts/validate_config.py

health-check:  ## Run browser automation health check
	python3 scripts/browser_health_check.py --config config/config.json

daily-digest:  ## Generate daily digest (HTML)
	python3 scripts/dm_daily_digest.py --hours 24 --format html --important --open

my-tasks:  ## Check your personal tasks
	python3 scripts/check_my_tasks.py

setup-browser:  ## Setup browser storage state for automation
	python3 scripts/create_storage_state.py

pre-commit:  ## Run pre-commit hooks on all files
	pre-commit run --all-files

setup-env:  ## Create .env from example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please edit it with your API keys."; \
	else \
		echo ".env already exists. Skipping."; \
	fi

setup:  ## Complete project setup (env + browser + validation)
	@echo "🚀 Setting up Scalers Slack automation..."
	@make setup-env
	@echo "\n📦 Installing dependencies..."
	@make dev-install
	@echo "\n✅ Setup complete! Run 'make validate-config' to check your configuration."

ci:  ## Run all CI checks (tests, linting, type checking)
	@echo "Running CI checks..."
	@make test
	@make lint
	@echo "✅ All CI checks passed!"

watch-test:  ## Run tests in watch mode
	pytest-watch

typecheck:  ## Run type checking only
	mypy src

security-check:  ## Run comprehensive security scan
	python3 scripts/security_scan.py

security-quick:  ## Run quick security scan (bandit only)
	bandit -r src/ -c .bandit -f screen

update-deps:  ## Update all dependencies
	pip install --upgrade pip
	pip install --upgrade -r requirements.txt
	pip install --upgrade -r requirements-dev.txt
	pip install --upgrade -r requirements-browser.txt

list-todos:  ## List all TODO/FIXME comments in code
	@echo "📝 TODO items:"
	@grep -r "TODO\|FIXME" src/ scripts/ --color=always || echo "No TODOs found!"

benchmark:  ## Run performance benchmarks
	@echo "⏱️  Running benchmarks..."
	@python3 -m pytest tests/ -k benchmark -v
