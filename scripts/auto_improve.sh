#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

STAMP="$(date +"%Y-%m-%d %H:%M:%S %Z")"
LOG_DIR="$REPO_DIR/output/auto-improve"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run-$(date +"%Y_%m_%d-%H%M%S").log"

{
  echo "[auto-improve] $STAMP"
  echo "repo: $REPO_DIR"
  echo

  # Refuse to run if you have local changes (safety).
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "[git] working tree is not clean. Commit or stash your changes first, then the auto-improve loop can run safely."
    git status --porcelain
    exit 2
  fi

  # Make sure we're on main and up to date.
  git fetch origin
  git checkout main
  git pull --rebase origin main

  # Python env
  if [[ -f "$REPO_DIR/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_DIR/.venv/bin/activate"
  fi

  # Install deps (idempotent)
  python -m pip install -q --upgrade pip
  python -m pip install -q -r requirements.txt
  if [[ -f requirements-dev.txt ]]; then
    python -m pip install -q -r requirements-dev.txt || true
  fi
  if [[ -f requirements-browser.txt ]]; then
    python -m pip install -q -r requirements-browser.txt || true
  fi

  echo "\n[checks] compile"
  python -m py_compile $(find src scripts -name "*.py" -type f | tr '\n' ' ')

  # Lint/format if ruff exists
  if command -v ruff >/dev/null 2>&1; then
    echo "\n[checks] ruff (fix + format)"
    ruff check . --fix || true
    ruff format . || true
    echo "\n[checks] ruff (verify)"
    ruff check .
    ruff format . --check
  else
    echo "\n[checks] ruff not installed; skipping lint/format"
  fi

  # Tests if available
  if command -v pytest >/dev/null 2>&1; then
    echo "\n[checks] pytest"
    pytest -q || true
  else
    echo "\n[checks] pytest not installed; skipping"
  fi

  # Workflow check: generate the Slack digest (headless)
  echo "\n[checks] generate digest (important channels + devs)"
  python3 scripts/dm_daily_digest.py --hours 24 --format html --important --dev-tasks --headless >/dev/null

  # Commit + push if anything changed
  if ! git diff --quiet; then
    echo "\n[git] changes detected; committing"
    git add -A
    git commit -m "chore: auto-improve (${STAMP})" || true
    echo "\n[git] pushing to origin/main"
    git push origin main
  else
    echo "\n[git] no changes"
  fi

  echo "\n[auto-improve] done"
} | tee "$LOG_FILE"
