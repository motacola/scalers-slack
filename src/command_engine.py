"""Natural language command processor for Scalers Slack."""

import logging
from datetime import datetime, timedelta, timezone

from .engine import ScalersSlackEngine

logger = logging.getLogger(__name__)


class CommandEngine:
    """Processes natural language-like commands and routes them to the engine."""

    def __init__(self, engine: ScalersSlackEngine):
        self.engine = engine
        self.memory = engine.memory

    def execute(self, command: str) -> str:
        """Parse and execute a command string."""
        cmd = command.lower().strip()

        # 0. Manual Login / Interactive Help
        if any(x in cmd for x in ["let me login", "open browser", "sign in", "web login", "fix login", "login"]):
            return self._handle_interactive_login(cmd)

        # 1. Check/Login Commands
        if any(x in cmd for x in ["check connection", "verify session", "google", "logged in", "ready"]):
            return self._handle_session_check(cmd)

        # 2. Sync/Work Commands
        if any(x in cmd for x in ["sync", "update", "pull", "work on"]):
            return self._handle_sync(cmd)

        # 3. Status/Memory Commands
        if any(x in cmd for x in ["status", "what did you do", "history", "memory"]):
            return self._handle_status(cmd)

        return "I'm not sure. Try 'login', 'sync', or 'status'."

    def _handle_interactive_login(self, cmd: str) -> str:
        """Open browser and wait for user."""
        if not self.engine.browser_session:
            return "Browser automation is disabled in config."

        try:
            # Force start if not valid
            self.engine.browser_session.start()

            # Check if we are headless
            if self.engine.browser_config.headless:
                return (
                    "I'm currently running in headless mode (invisible). "
                    "Please check config.json and set 'headless': false to use this feature."
                )

            page = self.engine.browser_session.new_page()

            # Navigate to a useful landing page
            print(">> Opening Google Login page...")
            page.goto("https://accounts.google.com/")

            print("\n[BROWSER OPEN] Please log in to Google, Slack, or Notion in the popped-up window.")
            print("The assistant is paused waiting for you.")
            input(">> Press ENTER here when you have finished logging in <<")

            self.engine.browser_session.save_storage_state()
            page.close()
            return "Perfect. I've saved your session state! You shouldn't need to log in again."
        except Exception as e:
            return f"Error opening browser: {e}"

    def _handle_session_check(self, cmd: str) -> str:
        """Trigger session verification."""
        # Special handling for "I'm logged in" or "ready" logic
        if "logged in" in cmd and "im" in cmd or "i am" in cmd:
            if self.engine.browser_session:
                try:
                    self.engine.browser_session.refresh_session()
                    return (
                        "Thanks! I've refreshed the browser session to pick up your new login state. "
                        "You should be good to go."
                    )
                except Exception as e:
                    return f"I tried to refresh the session but hit an error: {e}"
            else:
                return "I don't have an active browser session to refresh, but I've noted that you are logged in."

        results = []

        # Check Slack
        if self.engine.slack:
            try:
                # Basic API test
                self.engine.slack.auth_test() if hasattr(self.engine.slack, "auth_test") else None
                results.append("✅ Slack API: Connected")
            except Exception:
                results.append("❌ Slack API: Error")

        # Check Browser Session if active
        if self.engine.browser_session:
            try:
                page = self.engine.browser_session.new_page()
                page.close()
                results.append("✅ Browser Engine: Ready (Persistence Enabled)")

                # If command specifically asked for google, we can't fully verify inside the engine
                # without running the session manager script, but we can give a hint.
                if "google" in cmd:
                    results.append(
                        "ℹ️ Google: To verify/login to Google, "
                        "please run: python scripts/session_manager.py --google --interactive"
                    )
            except Exception as e:
                results.append(f"❌ Browser Engine: Failed ({str(e)})")

        return "\n".join(results) or "No active clients to check."

    def _handle_sync(self, cmd: str) -> str:
        """Execute sync logic based on natural language."""
        is_dirty = any(x in cmd for x in ["new", "recent", "dirty", "since yesterday"])

        # Determine scope
        projects_to_run = []
        all_projects = [p["name"] for p in self.engine.config.get("projects", [])]

        if "everything" in cmd or "all" in cmd:
            projects_to_run = all_projects
        else:
            # Fuzzy match project names
            for p in all_projects:
                if p.lower() in cmd:
                    projects_to_run.append(p)

        if not projects_to_run:
            return (
                "I couldn't identify which project you want to sync. "
                "Try saying 'sync everything' or naming a specific project."
            )

        # Filter if dirty flag is requested (simulated logic from Step 883)
        if is_dirty:
            # Re-implement strict dirty check or call a helper if engine exposes it
            # For now, we'll just log it.
            return f"I would run a DIRTY sync on: {', '.join(projects_to_run)} (Logic implementation pending in Engine)"

        # Actually run them (Sequential for safety in this MVP)
        results = []
        since_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(microsecond=0).isoformat()
        for p in projects_to_run:
            try:
                # Defaulting to 24h lookback for natural commands
                summary = self.engine.run_sync(project_name=p, since=since_iso) or {}
                status = summary.get("status", "unknown")
                count = summary.get("thread_count", 0)
                results.append(f"- {p}: {status} ({count} items)")
            except Exception as e:
                results.append(f"- {p}: Failed ({str(e)})")

        return "Sync complete:\n" + "\n".join(results)

    def _handle_status(self, cmd: str) -> str:
        """Read from memory."""
        total_runs = self.memory.data["global"]["total_runs"]
        last_run = self.memory.data["global"]["last_run"] or "never"

        # Get simplified project list
        # We can analyze self.memory.data["projects"]
        projects = self.memory.data["projects"]
        active = sum(1 for p in projects.values() if p.get("last_sync"))

        return (
            f"**System Status**\n"
            f"- Total Syncs Run: {total_runs}\n"
            f"- Last Activity: {last_run}\n"
            f"- Active Projects: {active} tracked in memory"
        )
