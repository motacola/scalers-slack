#!/usr/bin/env python3
"""
Security Scanning Script
Runs comprehensive security checks on the codebase.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class SecurityScanner:
    """Run security scans on the codebase."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.errors = 0
        self.warnings = 0

    def print_section(self, title: str) -> None:
        """Print a section header."""
        print(f"\n{'=' * 60}")
        print(f"🔒 {title}")
        print("=" * 60)

    def run_command(self, cmd: list[str], description: str, required: bool = True) -> bool:
        """Run a security command and report results."""
        print(f"\n▶ {description}...")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                print(f"✅ {description} - PASSED")
                if result.stdout.strip():
                    print(result.stdout)
                return True
            else:
                if required:
                    self.errors += 1
                    print(f"❌ {description} - FAILED")
                else:
                    self.warnings += 1
                    print(f"⚠️  {description} - WARNINGS")

                if result.stdout.strip():
                    print(result.stdout)
                if result.stderr.strip():
                    print(result.stderr)
                return False

        except FileNotFoundError:
            if required:
                self.errors += 1
                print(f"❌ {description} - Tool not installed")
            else:
                self.warnings += 1
                print(f"⚠️  {description} - Tool not installed (optional)")
            print(f"   Install with: pip install {cmd[0]}")
            return False
        except subprocess.TimeoutExpired:
            self.errors += 1
            print(f"❌ {description} - Timeout")
            return False
        except Exception as e:
            self.errors += 1
            print(f"❌ {description} - Error: {e}")
            return False

    def scan_code_security(self) -> bool:
        """Run bandit security scan on source code."""
        self.print_section("Code Security Scan (Bandit)")

        return self.run_command(
            ["bandit", "-r", "src/", "-c", ".bandit", "-f", "screen"],
            "Scanning source code for security issues",
            required=True,
        )

    def check_dependencies(self) -> bool:
        """Check for vulnerable dependencies."""
        self.print_section("Dependency Vulnerability Check")

        # Try pip-audit first (more comprehensive)
        pip_audit_ok = self.run_command(
            ["pip-audit", "--desc", "--skip-editable"],
            "Checking dependencies with pip-audit",
            required=False,
        )

        # Also try safety as a backup
        safety_ok = self.run_command(
            ["safety", "check", "--json"],
            "Checking dependencies with safety",
            required=False,
        )

        return pip_audit_ok or safety_ok

    def check_secrets(self) -> bool:
        """Check for accidentally committed secrets."""
        self.print_section("Secret Detection")

        # Check for common secret patterns
        patterns = [
            (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
            (r"sk-[a-zA-Z0-9]{32,}", "API Key (sk- prefix)"),
            (r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}", "Slack Bot Token"),
            (r"ghp_[a-zA-Z0-9]{36,}", "GitHub Personal Access Token"),
            (r"sk-ant-[a-zA-Z0-9\-]{95,}", "Anthropic API Key"),
        ]

        found_secrets = []

        try:

            for pattern, name in patterns:
                # Search in Python files (excluding .env and tests)
                cmd = ["grep", "-r", "-E", pattern, "src/", "scripts/"]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 and result.stdout.strip():
                    found_secrets.append((name, result.stdout))

            if found_secrets:
                self.errors += 1
                print("❌ Found potential secrets in code:")
                for name, matches in found_secrets:
                    print(f"\n  {name}:")
                    print(f"  {matches}")
                return False
            else:
                print("✅ No hardcoded secrets detected")
                return True

        except Exception as e:
            self.warnings += 1
            print(f"⚠️  Secret detection failed: {e}")
            return False

    def check_permissions(self) -> bool:
        """Check file permissions for sensitive files."""
        self.print_section("File Permissions Check")

        sensitive_files = [".env", "config/config.json", "config/browser_storage_state.json"]

        issues = []
        for file_path in sensitive_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                # Check if file is world-readable
                import stat

                file_stat = full_path.stat()
                mode = file_stat.st_mode

                if mode & stat.S_IROTH or mode & stat.S_IWOTH:
                    issues.append(f"{file_path} is world-readable/writable (permissions: {oct(mode)[-3:]})")

        if issues:
            self.warnings += 1
            print("⚠️  Permission issues found:")
            for issue in issues:
                print(f"  - {issue}")
            print("\n  Fix with: chmod 600 <file>")
            return False
        else:
            print("✅ Sensitive file permissions are secure")
            return True

    def check_env_file(self) -> bool:
        """Check .env file is properly gitignored."""
        self.print_section("Environment File Security")

        env_file = self.project_root / ".env"
        gitignore = self.project_root / ".gitignore"

        issues = []

        # Check if .env exists and is in .gitignore
        if env_file.exists():
            if not gitignore.exists():
                issues.append(".gitignore file is missing")
            else:
                with open(gitignore) as f:
                    gitignore_content = f.read()
                    if ".env" not in gitignore_content:
                        issues.append(".env is not in .gitignore")

        # Check if .env is tracked by git
        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", ".env"],
                cwd=self.project_root,
                capture_output=True,
            )
            if result.returncode == 0:
                issues.append(".env file is tracked by git (should be ignored)")
        except Exception:
            pass  # Git not available or other error

        if issues:
            self.errors += 1
            print("❌ Environment file security issues:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ Environment file is properly secured")
            return True

    def run_all_scans(self) -> int:
        """Run all security scans and return exit code."""
        print("🔒 Scalers Slack Security Scanner")
        print("=" * 60)

        # Run all scans
        results = {
            "Code Security": self.scan_code_security(),
            "Dependency Vulnerabilities": self.check_dependencies(),
            "Secret Detection": self.check_secrets(),
            "File Permissions": self.check_permissions(),
            "Environment Security": self.check_env_file(),
        }

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Security Scan Summary")
        print("=" * 60)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        print(f"\nChecks passed: {passed}/{total}")

        if self.errors > 0:
            print(f"❌ {self.errors} critical issue(s) found")
        if self.warnings > 0:
            print(f"⚠️  {self.warnings} warning(s) found")

        if self.errors == 0 and self.warnings == 0:
            print("\n✅ All security checks passed!")
            return 0
        elif self.errors == 0:
            print("\n⚠️  No critical issues, but some warnings were found")
            return 0
        else:
            print("\n❌ Critical security issues found. Please fix them before deployment.")
            return 1


def main() -> int:
    """Main entry point."""
    scanner = SecurityScanner()
    return scanner.run_all_scans()


if __name__ == "__main__":
    sys.exit(main())
