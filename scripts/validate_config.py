#!/usr/bin/env python3
"""
Configuration Validation Script
Validates all required configuration files, environment variables, and API tokens.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


class ConfigValidator:
    """Validates project configuration."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.project_root = Path(__file__).parent.parent

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(f"❌ ERROR: {message}")

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(f"⚠️  WARNING: {message}")

    def add_success(self, message: str) -> None:
        """Print a success message."""
        print(f"✅ {message}")

    def validate_env_file(self) -> bool:
        """Validate .env file exists and has required variables."""
        print("\n📄 Checking .env file...")

        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env.example"

        if not env_file.exists():
            self.add_error(f".env file not found at {env_file}")
            if env_example.exists():
                print(f"   💡 Copy {env_example} to {env_file} and fill in your values")
            return False

        self.add_success(f".env file found at {env_file}")

        # Check for required environment variables
        required_vars = {
            "SLACK_BOT_TOKEN": "Slack Bot OAuth Token",
            "NOTION_API_KEY": "Notion Integration Token",
        }

        optional_vars = {
            "OPENAI_API_KEY": "OpenAI API Key (for LLM features)",
            "ANTHROPIC_API_KEY": "Anthropic API Key (for Claude LLM)",
        }

        # Read .env file
        env_vars = {}
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

        # Check required variables
        all_required_present = True
        for var, description in required_vars.items():
            if var not in env_vars or not env_vars[var]:
                self.add_error(f"Missing or empty required variable: {var} ({description})")
                all_required_present = False
            else:
                self.add_success(f"{var} is set")

        # Check optional variables
        for var, description in optional_vars.items():
            if var not in env_vars or not env_vars[var]:
                self.add_warning(f"Optional variable not set: {var} ({description})")
            else:
                self.add_success(f"{var} is set (optional)")

        return all_required_present

    def validate_config_json(self) -> bool:
        """Validate config/config.json file."""
        print("\n📄 Checking config/config.json...")

        config_file = self.project_root / "config" / "config.json"

        if not config_file.exists():
            self.add_error(f"config.json not found at {config_file}")
            return False

        self.add_success(f"config.json found at {config_file}")

        # Load and validate JSON
        try:
            with open(config_file) as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.add_error(f"Invalid JSON in config.json: {e}")
            return False

        self.add_success("config.json is valid JSON")

        # Validate required fields
        required_fields = {
            "slack": ["workspace_url", "excluded_channels"],
            "notion": ["database_id", "user_mapping"],
            "browser": ["headless", "storage_state_path"],
        }

        all_fields_present = True
        for section, fields in required_fields.items():
            if section not in config:
                self.add_error(f"Missing section in config.json: {section}")
                all_fields_present = False
                continue

            for field in fields:
                if field not in config[section]:
                    self.add_error(f"Missing field in config.json: {section}.{field}")
                    all_fields_present = False
                else:
                    self.add_success(f"config.json has {section}.{field}")

        # Validate Notion database ID format (32 hex chars)
        if "notion" in config and "database_id" in config["notion"]:
            db_id = config["notion"]["database_id"]
            if not re.match(r"^[a-f0-9]{32}$", db_id.replace("-", "")):
                self.add_warning(
                    f"Notion database_id format looks unusual: {db_id} "
                    "(expected 32 hex characters, possibly with dashes)"
                )

        # Check if storage state path exists
        if "browser" in config and "storage_state_path" in config["browser"]:
            storage_path = self.project_root / config["browser"]["storage_state_path"]
            if not storage_path.exists():
                self.add_warning(
                    f"Browser storage state file not found: {storage_path}\n"
                    "   💡 Run 'scalers-setup' or 'python scripts/create_storage_state.py' to create it"
                )
            else:
                self.add_success(f"Browser storage state file exists: {storage_path}")

        return all_fields_present

    def validate_directories(self) -> bool:
        """Validate required directories exist."""
        print("\n📁 Checking required directories...")

        required_dirs = [
            "config",
            "src",
            "scripts",
            "tests",
            "output",
            ".cache/browser",
        ]

        all_exist = True
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                if dir_name == "output" or dir_name.startswith(".cache"):
                    # These can be auto-created
                    self.add_warning(f"Directory will be created on first run: {dir_name}")
                else:
                    self.add_error(f"Required directory missing: {dir_name}")
                    all_exist = False
            else:
                self.add_success(f"Directory exists: {dir_name}")

        return all_exist

    def validate_api_tokens(self) -> bool:
        """Validate API token formats (without making API calls)."""
        print("\n🔑 Validating API token formats...")

        all_valid = True

        # Check Slack token format
        slack_token = os.getenv("SLACK_BOT_TOKEN", "")
        if slack_token:
            if slack_token.startswith("xoxb-"):
                self.add_success("SLACK_BOT_TOKEN format is correct (xoxb-...)")
            else:
                self.add_warning(
                    "SLACK_BOT_TOKEN doesn't start with 'xoxb-' (expected for bot tokens)\n"
                    "   💡 Make sure you're using a Bot User OAuth Token, not a User OAuth Token"
                )
                all_valid = False

        # Check Notion token format
        notion_token = os.getenv("NOTION_API_KEY", "")
        if notion_token:
            if notion_token.startswith("secret_"):
                self.add_success("NOTION_API_KEY format is correct (secret_...)")
            elif notion_token.startswith("ntn_"):
                self.add_success("NOTION_API_KEY format is correct (ntn_...)")
            else:
                self.add_warning(
                    "NOTION_API_KEY doesn't start with 'secret_' or 'ntn_'\n"
                    "   💡 Notion tokens usually start with 'secret_' or 'ntn_'"
                )
                all_valid = False

        # Check OpenAI token format (if present)
        openai_token = os.getenv("OPENAI_API_KEY", "")
        if openai_token:
            if openai_token.startswith("sk-"):
                self.add_success("OPENAI_API_KEY format is correct (sk-...)")
            else:
                self.add_warning("OPENAI_API_KEY doesn't start with 'sk-' (expected format)")

        # Check Anthropic token format (if present)
        anthropic_token = os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_token:
            if anthropic_token.startswith("sk-ant-"):
                self.add_success("ANTHROPIC_API_KEY format is correct (sk-ant-...)")
            else:
                self.add_warning("ANTHROPIC_API_KEY doesn't start with 'sk-ant-' (expected format)")

        return all_valid

    def validate_dependencies(self) -> bool:
        """Check if required Python packages are installed."""
        print("\n📦 Checking Python dependencies...")

        required_packages = {
            "requests": "HTTP library",
            "jsonschema": "JSON validation",
        }

        optional_packages = {
            "playwright": "Browser automation",
            "openai": "OpenAI LLM support",
            "anthropic": "Anthropic Claude LLM support",
        }

        all_required_installed = True

        # Check required packages
        for package, description in required_packages.items():
            try:
                __import__(package)
                self.add_success(f"{package} is installed ({description})")
            except ImportError:
                self.add_error(f"Required package not installed: {package} ({description})")
                print(f"   💡 Install with: pip install {package}")
                all_required_installed = False

        # Check optional packages
        for package, description in optional_packages.items():
            try:
                __import__(package)
                self.add_success(f"{package} is installed ({description})")
            except ImportError:
                self.add_warning(f"Optional package not installed: {package} ({description})")
                if package == "playwright":
                    print("   💡 Install with: pip install -r requirements-browser.txt")
                else:
                    print(f"   💡 Install with: pip install {package}")

        return all_required_installed

    def generate_fixes(self) -> None:
        """Generate suggestions for fixing common issues."""
        if not self.errors and not self.warnings:
            return

        print("\n💡 Suggested Fixes:")
        print("=" * 60)

        if any(".env file not found" in e for e in self.errors):
            print("\n1. Create .env file:")
            print("   cp .env.example .env")
            print("   # Then edit .env and fill in your API tokens")

        if any("config.json not found" in e for e in self.errors):
            print("\n2. Create config directory and config.json:")
            print("   mkdir -p config")
            print("   # Copy a template or create config.json with required fields")

        if any("Required package not installed" in e for e in self.errors):
            print("\n3. Install required dependencies:")
            print("   pip install -r requirements.txt")

        if any("Optional package not installed" in w for w in self.warnings):
            print("\n4. Install optional dependencies (for full functionality):")
            print("   pip install -r requirements-dev.txt")
            print("   pip install -r requirements-browser.txt")

        if any("storage state file not found" in w.lower() for w in self.warnings):
            print("\n5. Create browser storage state:")
            print("   python scripts/create_storage_state.py")
            print("   # Or use: scalers-setup (if package is installed)")

    def run(self) -> int:
        """Run all validations and return exit code."""
        print("🔍 Scalers Slack Configuration Validator")
        print("=" * 60)

        # Load .env file if it exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_file)
            except ImportError:
                print("⚠️  python-dotenv not installed, skipping .env loading")
                print("   Environment variables must be set manually\n")

        # Run all validations
        self.validate_env_file()
        self.validate_config_json()
        self.validate_directories()
        self.validate_api_tokens()
        self.validate_dependencies()

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Validation Summary")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                print(f"   {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                print(f"   {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All validations passed! Configuration is valid.")
            print("\n🚀 You're ready to run:")
            print("   python scripts/dm_daily_digest.py")
            print("   # Or: scalers-digest (if package is installed)")
            return 0
        elif not self.errors:
            print("\n✅ No critical errors found!")
            print("⚠️  Some optional features may not work due to warnings above.")
            self.generate_fixes()
            return 0
        else:
            print("\n❌ Configuration has errors that must be fixed.")
            self.generate_fixes()
            return 1


def main() -> int:
    """Main entry point."""
    validator = ConfigValidator()
    return validator.run()


if __name__ == "__main__":
    sys.exit(main())
