# Contributing Guide

Thank you for your interest in contributing to Scalers Slack Automation!

## Quick Start

```bash
# Clone the repository
git clone https://github.com/motacola/scalers-slack.git
cd scalers-slack

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-browser.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest

# Run linting
ruff check .
mypy src
```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes
- Write code following the style guide below
- Add tests for new features
- Update documentation as needed
- Run linters and tests locally

### 3. Commit
```bash
git add -A
git commit -m "feat: add new feature"
```

**Commit Message Format**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests
- `chore`: Changes to build process or auxiliary tools

### 4. Push and Create PR
```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Style

### Python Style
- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 120 characters
- Use `ruff` for linting (auto-fixed by pre-commit)

### Documentation
- Add docstrings to all public functions/classes
- Use Google-style docstrings
- Update ARCHITECTURE.md for significant changes
- Keep README.md current

### Testing
- Write tests for all new code
- Aim for >80% code coverage
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

## Project Structure

```
src/           - Core library code
scripts/       - Executable utilities
tests/         - Test files
docs/          - Documentation
config/        - Configuration files
```

See `docs/ARCHITECTURE.md` for detailed architecture.

## Adding New Features

### New Script
1. Create in `scripts/`
2. Add docstring with usage examples
3. Use `argparse` for CLI arguments
4. Add to `scripts/README.md`
5. Add tests

### New Module
1. Create in `src/`
2. Add comprehensive docstrings
3. Add type hints
4. Write tests in `tests/`
5. Update `docs/ARCHITECTURE.md`

### New LLM Provider
1. Create class in `src/llm_client.py`
2. Inherit from `LLMClient`
3. Implement abstract methods
4. Add to factory function
5. Update `docs/LLM_INTEGRATION.md`
6. Add tests

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_task_processor.py

# With coverage
pytest --cov=src --cov-report=html

# Verbose
pytest -v
```

## Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:
- Ruff linting and formatting
- MyPy type checking
- Security checks (Bandit)
- JSON/YAML validation

To run manually:
```bash
pre-commit run --all-files
```

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag: `git tag v0.2.0`
4. Push: `git push --tags`

## Getting Help

- **Issues**: Check existing GitHub issues
- **Documentation**: See `docs/` directory
- **Questions**: Open a GitHub discussion

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
