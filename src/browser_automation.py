from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, TypedDict, cast
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Manages load balancing for distributed environments."""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.workers: list[str] = []
        self.active_workers = 0
    
    def add_worker(self, worker_id: str):
        """Add a worker to the load balancer.
        
        Args:
            worker_id: The ID of the worker to add.
        """
        if worker_id not in self.workers:
            self.workers.append(worker_id)
    
    def remove_worker(self, worker_id: str):
        """Remove a worker from the load balancer.
        
        Args:
            worker_id: The ID of the worker to remove.
        """
        if worker_id in self.workers:
            self.workers.remove(worker_id)
    
    def get_available_worker(self) -> str | None:
        """Get an available worker for processing.
        
        Returns:
            str | None: The ID of an available worker, or None if no workers are available.
        """
        if self.active_workers < self.max_workers and self.workers:
            worker = self.workers[self.active_workers % len(self.workers)]
            self.active_workers += 1
            return worker
        return None
    
    def release_worker(self):
        """Release a worker after processing."""
        if self.active_workers > 0:
            self.active_workers -= 1
    
    def get_worker_count(self) -> int:
        """Get the number of available workers.
        
        Returns:
            int: The number of available workers.
        """
        return len(self.workers)
    
    def get_active_worker_count(self) -> int:
        """Get the number of active workers.
        
        Returns:
            int: The number of active workers.
        """
        return self.active_workers


class ScalabilityManager:
    """Manages optimizations for handling larger datasets and higher traffic."""
    
    def __init__(self, max_concurrent_sessions: int = 5, batch_size: int = 100):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.batch_size = batch_size
        self.active_sessions = 0
    
    def acquire_session(self) -> bool:
        """Acquire a session slot for concurrent operations.
        
        Returns:
            bool: True if a session slot is available, False otherwise.
        """
        if self.active_sessions < self.max_concurrent_sessions:
            self.active_sessions += 1
            return True
        return False
    
    def release_session(self):
        """Release a session slot after operation completion."""
        if self.active_sessions > 0:
            self.active_sessions -= 1
    
    def get_batch_size(self) -> int:
        """Get the recommended batch size for operations.
        
        Returns:
            int: The recommended batch size.
        """
        return self.batch_size
    
    def optimize_batch_size(self, data_size: int) -> int:
        """Optimize the batch size based on the dataset size.
        
        Args:
            data_size: The size of the dataset.
            
        Returns:
            int: The optimized batch size.
        """
        if data_size < 1000:
            return min(self.batch_size, data_size)
        elif data_size < 10000:
            return min(self.batch_size * 2, data_size)
        else:
            return min(self.batch_size * 5, data_size)


class PerformanceMetrics(TypedDict):
    sync_operations: int
    successful_operations: int
    failed_operations: int
    total_time_ms: float
    average_time_ms: float
    bottlenecks: list[dict[str, Any]]


class PerformanceMonitor:
    """Monitors and tracks the performance of sync operations."""
    
    def __init__(self):
        self.metrics: PerformanceMetrics = {
            "sync_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_time_ms": 0.0,
            "average_time_ms": 0.0,
            "bottlenecks": [],
        }
        self.start_time: float = 0.0
    
    def start_monitoring(self):
        """Start monitoring a sync operation."""
        self.start_time = time.time()
    
    def stop_monitoring(self, success: bool, operation_name: str | None = None):
        """Stop monitoring a sync operation and record metrics.
        
        Args:
            success: Whether the operation was successful.
            operation_name: The name of the operation being monitored.
        """
        if not self.start_time:
            logger.warning("PerformanceMonitor.stop_monitoring called before start_monitoring.")
            return
        elapsed_time = time.time() - self.start_time
        self.metrics["total_time_ms"] += elapsed_time * 1000
        self.metrics["sync_operations"] += 1
        
        if success:
            self.metrics["successful_operations"] += 1
        else:
            self.metrics["failed_operations"] += 1
        
        if self.metrics["sync_operations"] > 0:
            self.metrics["average_time_ms"] = self.metrics["total_time_ms"] / self.metrics["sync_operations"]
        
        # Identify bottlenecks
        if operation_name and elapsed_time > 5:  # Threshold for identifying bottlenecks
            self.metrics["bottlenecks"].append({
                "operation": operation_name,
                "time_ms": elapsed_time * 1000,
                "timestamp": time.time(),
            })
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get the current performance metrics.
        
        Returns:
            dict: A dictionary containing the performance metrics.
        """
        return self.metrics.copy()
    
    def get_bottlenecks(self) -> list[dict[str, Any]]:
        """Get a list of identified bottlenecks.
        
        Returns:
            list: A list of dictionaries containing bottleneck information.
        """
        return self.metrics["bottlenecks"]
    
    def reset(self):
        """Reset all performance metrics."""
        self.metrics = {
            "sync_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_time_ms": 0.0,
            "average_time_ms": 0.0,
            "bottlenecks": [],
        }
        self.start_time = 0.0


class RecoveryManager:
    """Manages automatic recovery mechanisms for common failure scenarios."""
    
    def __init__(self, max_retries: int = 3, retry_delay_ms: int = 1000):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.recovery_attempts = 0
    
    def handle_failure(self, error: Exception, recovery_action: Callable[[], None]) -> bool:
        """Attempt to recover from a failure by executing a recovery action.
        
        Args:
            error: The exception that caused the failure.
            recovery_action: A callable that attempts to recover from the failure.
            
        Returns:
            bool: True if recovery was successful, False otherwise.
        """
        self.recovery_attempts += 1
        logger.warning(f"Attempting recovery from failure (attempt {self.recovery_attempts}): {error}")
        
        if self.recovery_attempts > self.max_retries:
            logger.error(f"Max recovery attempts ({self.max_retries}) exceeded for error: {error}")
            return False
        
        try:
            time.sleep(self.retry_delay_ms / 1000)
            recovery_action()
            logger.info(f"Recovery successful after {self.recovery_attempts} attempt(s)")
            self.recovery_attempts = 0
            return True
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return False
    
    def reset(self):
        """Reset the recovery attempts counter."""
        self.recovery_attempts = 0

_sync_playwright: Any = None
try:
    from playwright.sync_api import sync_playwright as _sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    pass

sync_playwright: Any = _sync_playwright


@dataclass
class BrowserAutomationConfig:
    enabled: bool = False
    storage_state_path: str = ""
    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 30000
    browser_channel: str | None = None
    user_data_dir: str | None = None
    slack_workspace_id: str = ""
    slack_client_url: str = "https://app.slack.com/client"
    slack_api_base_url: str = "https://slack.com/api"
    notion_base_url: str = "https://www.notion.so"
    max_retries: int = 3
    retry_delay_ms: int = 1000
    verbose_logging: bool = False
    keep_open: bool = False
    interactive_login: bool = True
    interactive_login_timeout_ms: int = 120000
    auto_save_storage_state: bool = True
    auto_recover: bool = True
    auto_recover_refresh: bool = True
    smart_wait: bool = True
    smart_wait_network_idle: bool = True
    smart_wait_timeout_ms: int = 15000
    smart_wait_stability_ms: int = 600
    overlay_enabled: bool = False
    recordings_dir: str = "output/browser_recordings"
    html_snapshot_on_error: bool = True
    event_log_path: str = "output/browser_events.jsonl"
    screenshot_on_step: bool = False
    screenshot_on_error: bool = True


class BrowserSession:
    def __init__(self, config: BrowserAutomationConfig):
        self.config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self.recovery_manager = RecoveryManager(
            max_retries=config.max_retries,
            retry_delay_ms=config.retry_delay_ms
        )
        self.performance_monitor = PerformanceMonitor()
        self.scalability_manager = ScalabilityManager(
            max_concurrent_sessions=5,
            batch_size=100
        )
        self.load_balancer = LoadBalancer(max_workers=5)
        self._step_counter = 0

    def start(self) -> None:
        if self._context:
            return
        if sync_playwright is None:
            logger.error("Playwright is not installed. Install it to use browser automation fallback.")
            raise RuntimeError("Playwright is not installed. Install it to use browser automation fallback.")
        if (
            not self.config.user_data_dir
            and self.config.storage_state_path
            and not os.path.exists(self.config.storage_state_path)
            and (self.config.headless or not self.config.interactive_login)
        ):
            raise RuntimeError(
                "Browser storage state not found. "
                "Create it with scripts/create_storage_state.py to avoid re-login."
            )

        def recovery_action():
            """Recovery action to restart the browser session."""
            self.close()
            self._playwright = sync_playwright().start()
            launch_args: dict[str, Any] = {
                "headless": self.config.headless,
                "slow_mo": self.config.slow_mo_ms,
            }
            if self.config.browser_channel:
                launch_args["channel"] = self.config.browser_channel

            if self.config.user_data_dir:
                context_args: dict[str, Any] = {}
                if self.config.storage_state_path and self.config.verbose_logging:
                    logger.info(
                        "Ignoring storage_state_path because user_data_dir is set (%s).",
                        self.config.user_data_dir,
                    )
                self._context = self._playwright.chromium.launch_persistent_context(
                    self.config.user_data_dir,
                    **launch_args,
                    **context_args,
                )
                browser_attr = getattr(self._context, "browser", None)
                self._browser = browser_attr() if callable(browser_attr) else browser_attr
            else:
                self._browser = self._playwright.chromium.launch(**launch_args)
                context_args = {}
                if self.config.storage_state_path:
                    context_args["storage_state"] = self.config.storage_state_path
                self._context = self._browser.new_context(**context_args)
            self._context.set_default_timeout(self.config.timeout_ms)

        try:
            recovery_action()
            if self.config.verbose_logging:
                logger.info("Browser session started with storage_state=%s", self.config.storage_state_path)
            logger.info("Browser session started successfully.")
        except Exception as e:
            if self.recovery_manager.handle_failure(e, recovery_action):
                logger.info("Browser session recovered successfully.")
            else:
                logger.error(f"Failed to start browser session after recovery attempts: {e}")
                raise

    def log_event(self, event: str, detail: dict[str, Any] | None = None) -> None:
        detail = detail or {}
        payload = {
            "ts": time.time(),
            "event": event,
            "detail": detail,
        }
        try:
            log_dir = os.path.dirname(self.config.event_log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(self.config.event_log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except Exception as exc:
            logger.warning("Failed to write browser event log: %s", exc)

    def _next_step_id(self) -> str:
        self._step_counter += 1
        return f"step_{self._step_counter:04d}"

    def _maybe_screenshot(self, page, label: str) -> None:
        if not self.config.recordings_dir:
            return
        try:
            os.makedirs(self.config.recordings_dir, exist_ok=True)
            filename = f"{self._next_step_id()}_{label}.png"
            path = os.path.join(self.config.recordings_dir, filename)
            page.screenshot(path=path, full_page=True)
            if self.config.verbose_logging:
                logger.info("Saved screenshot %s", path)
        except Exception as exc:
            logger.warning("Failed to capture screenshot: %s", exc)

    def _maybe_dom_snapshot(self, page, label: str) -> None:
        if not self.config.recordings_dir or not self.config.html_snapshot_on_error:
            return
        try:
            os.makedirs(self.config.recordings_dir, exist_ok=True)
            filename = f"{self._next_step_id()}_{label}.html"
            path = os.path.join(self.config.recordings_dir, filename)
            content = page.content()
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            if self.config.verbose_logging:
                logger.info("Saved DOM snapshot %s", path)
        except Exception as exc:
            logger.warning("Failed to capture DOM snapshot: %s", exc)

    def _apply_overlay(self, page, text: str) -> None:
        if not self.config.overlay_enabled:
            return
        try:
            page.evaluate(
                """
                (overlayText) => {
                    const id = '__scalers_overlay__';
                    let el = document.getElementById(id);
                    if (!el) {
                        el = document.createElement('div');
                        el.id = id;
                        el.style.position = 'fixed';
                        el.style.top = '8px';
                        el.style.right = '8px';
                        el.style.zIndex = '99999';
                        el.style.padding = '6px 10px';
                        el.style.background = 'rgba(20,20,20,0.8)';
                        el.style.color = '#fff';
                        el.style.fontSize = '12px';
                        el.style.fontFamily = 'monospace';
                        el.style.borderRadius = '6px';
                        el.style.pointerEvents = 'none';
                        document.body.appendChild(el);
                    }
                    el.textContent = overlayText;
                }
                """,
                text,
            )
        except Exception:
            pass

    def _smart_wait(self, page) -> None:
        if not self.config.smart_wait:
            return
        try:
            page.wait_for_load_state("domcontentloaded", timeout=self.config.smart_wait_timeout_ms)
        except Exception:
            return
        if self.config.smart_wait_network_idle:
            try:
                page.wait_for_load_state("networkidle", timeout=self.config.smart_wait_timeout_ms)
            except Exception:
                pass
        stability_ms = max(0, self.config.smart_wait_stability_ms)
        if stability_ms <= 0:
            return
        checks = max(1, int(stability_ms / 200))
        last_len = None
        stable = 0
        for _ in range(checks):
            try:
                length = page.evaluate(
                    "() => document.body && document.body.innerText ? document.body.innerText.length : 0"
                )
            except Exception:
                break
            if length == last_len:
                stable += 1
            else:
                stable = 0
            last_len = length
            time.sleep(0.2)
        if self.config.verbose_logging:
            logger.info("Smart wait stability checks=%s stable=%s", checks, stable)

    def save_storage_state(self) -> None:
        if not self._context or not self.config.storage_state_path:
            return
        try:
            self._context.storage_state(path=self.config.storage_state_path)
            if self.config.verbose_logging:
                logger.info("Saved browser storage state to %s", self.config.storage_state_path)
        except Exception as exc:
            logger.warning("Failed to save browser storage state: %s", exc)

    def new_page(self, url: str):
        self.start()
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            page = self._context.new_page()
            try:
                self._apply_overlay(page, "Starting navigation...")
                if self.config.verbose_logging:
                    logger.info("Navigating to %s (attempt %s)", url, attempt + 1)
                page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
                self._smart_wait(page)
                if self.config.overlay_enabled:
                    self._apply_overlay(page, f"Loaded {url}")
                return page
            except Exception as exc:
                last_error = exc
                try:
                    page.close()
                except Exception:
                    pass
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_ms / 1000)
        raise last_error or RuntimeError(f"Failed to navigate to {url}")

    def navigate(self, url: str):
        """Alias for new_page to maintain compatibility."""
        return self.new_page(url)

    def request(self):
        self.start()
        return self._context.request

    def close(self) -> None:
        if self.config.auto_save_storage_state:
            self.save_storage_state()
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None


class SlackBrowserClient:
    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config
        self.stats: dict[str, Any] = {}
        self.pagination_stats: dict[str, Any] = {}
        self._web_token: str | None = None
        self.reset_stats()

    def _slack_client_home(self) -> str:
        if self.config.slack_workspace_id:
            return f"{self.config.slack_client_url}/{self.config.slack_workspace_id}"
        return self.config.slack_client_url

    def _with_page(self, url: str, func, retry_on_failure: bool = True):
        page = None
        last_error = None
        try:
            page = self.session.new_page(url)
            for attempt in range(self.config.max_retries if retry_on_failure else 1):
                try:
                    if self.config.verbose_logging:
                        logger.info("Running page action for %s (attempt %s)", url, attempt + 1)
                    self.session._apply_overlay(page, f"Working on {url} ({attempt + 1})")
                    result = func(page)
                    logger.info(f"Page action completed successfully for URL: {url}")
                    if self.config.screenshot_on_step:
                        self.session._maybe_screenshot(page, "success")
                    self.session.log_event("page_action_success", {"url": url})
                    return result
                except Exception as e:
                    last_error = e
                    logger.error(f"Page action failed for URL {url} (attempt {attempt + 1}): {e}")
                    self.session.log_event(
                        "page_action_error",
                        {"url": url, "attempt": attempt + 1, "error": str(e)},
                    )
                    if self.config.screenshot_on_error:
                        self.session._maybe_screenshot(page, "error")
                    self.session._maybe_dom_snapshot(page, "error")
                    if self.config.auto_recover and self.config.auto_recover_refresh:
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=self.config.timeout_ms)
                            self.session._smart_wait(page)
                        except Exception:
                            pass
                    if retry_on_failure and attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_ms / 1000)
                    else:
                        break
            if last_error:
                logger.error(f"Page action failed after {self.config.max_retries} attempts for URL {url}")
                raise last_error
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def _slack_api_call(
        self,
        endpoint: str,
        params: dict | None = None,
        method: str = "GET",
        body: dict | None = None,
    ) -> dict[str, Any]:
        base_url = f"{self.config.slack_api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        url = f"{base_url}?{urlencode(params or {})}" if params else base_url
        request = self.session.request()
        last_error: Exception | None = None

        for attempt in range(2):
            token = self._get_web_token()
            if not token:
                raise RuntimeError(
                    "Slack web token not found. Recreate browser storage state "
                    "with scripts/create_storage_state.py to avoid re-login."
                )
            headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {token}"}
            try:
                if method.upper() == "GET":
                    response = request.get(url, headers=headers)
                else:
                    payload = json.dumps(body or {})
                    response = request.fetch(url, method=method, headers=headers, data=payload)

                status = response.status
                try:
                    data: Any = response.json()
                except Exception:
                    data = {}

                self.stats["api_calls"] += 1
                if status == 429:
                    self.stats["rate_limit_hits"] += 1
                    logger.warning(f"Rate limit hit for Slack API endpoint: {endpoint}")

                if self._is_auth_error(status, data) and attempt == 0:
                    logger.warning("Slack auth failed; refreshing web token and retrying.")
                    self._refresh_web_token()
                    continue

                if status and status >= 400:
                    error = data.get("error") if isinstance(data, dict) else "unknown_error"
                    logger.error(f"Slack API error (browser): {status} {error}")
                    raise RuntimeError(f"Slack API error (browser): {status} {error}")

                if isinstance(data, dict) and not data.get("ok", True):
                    error_msg = data.get("error", "unknown_error")
                    logger.error(f"Slack API error (browser): {error_msg}")
                    raise RuntimeError(f"Slack API error (browser): {error_msg}")

                if not isinstance(data, dict):
                    logger.error("Slack API error (browser): invalid response")
                    raise RuntimeError("Slack API error (browser): invalid response")

                logger.info(f"Slack API call successful: {endpoint}")
                return cast(dict[str, Any], data)
            except Exception as e:
                last_error = e
                logger.error(f"Failed to execute Slack API call: {e}")
                if attempt >= 1:
                    raise
        if last_error:
            raise last_error
        raise RuntimeError("Slack API call failed")

    def _get_web_token(self) -> str | None:
        if self._web_token:
            return self._web_token

        workspace_id = self.config.slack_workspace_id

        def _extract_token_from_storage_state() -> str | None:
            try:
                state = self.session._context.storage_state()
            except Exception:
                return None
            for origin in state.get("origins", []):
                if "slack.com" not in origin.get("origin", ""):
                    continue
                for entry in origin.get("localStorage", []):
                    if entry.get("name") not in {"localConfig_v2", "localConfig"}:
                        continue
                    raw = entry.get("value")
                    if not isinstance(raw, str):
                        continue
                    try:
                        parsed = json.loads(raw)
                    except Exception:
                        continue
                    teams = parsed.get("teams") if isinstance(parsed, dict) else None
                    if not isinstance(teams, dict):
                        continue
                    if workspace_id and workspace_id in teams and isinstance(teams[workspace_id], dict):
                        token = teams[workspace_id].get("token")
                        if isinstance(token, str):
                            return token
                    for team in teams.values():
                        if isinstance(team, dict):
                            token = team.get("token")
                            if isinstance(token, str):
                                return token
            return None

        def action(page):
            return _extract_token_from_storage_state()

        token = self._with_page(self._slack_client_home(), action)
        if isinstance(token, str) and token:
            self._web_token = token
            return self._web_token

        if self.config.interactive_login and not self.config.headless:
            token = self._interactive_login_slack()
            if isinstance(token, str) and token:
                self._web_token = token
        return self._web_token

    def _is_auth_error(self, status: int | None, data: Any) -> bool:
        auth_errors = {"not_authed", "invalid_auth", "token_revoked", "account_inactive", "token_expired"}
        if status in {401, 403}:
            return True
        if isinstance(data, dict):
            return data.get("error") in auth_errors
        return False

    def _refresh_web_token(self) -> str | None:
        previous = self._web_token
        self._web_token = None
        token = self._get_web_token()
        if token and token != previous:
            logger.info("Slack web token refreshed.")
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
        return token

    def _interactive_login_slack(self) -> str | None:
        page = self.session.new_page(self._slack_client_home())
        try:
            logger.warning(
                "Slack login required. Complete login in the opened browser window "
                "(waiting up to %s seconds).",
                int(self.config.interactive_login_timeout_ms / 1000),
            )
            page.wait_for_selector(
                "div[role='application'], div[data-qa='client_container']",
                timeout=self.config.interactive_login_timeout_ms,
            )
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
            token = self._get_web_token()
            if isinstance(token, str) and token:
                return token
        except Exception as exc:
            logger.error("Slack interactive login failed: %s", exc)
        finally:
            try:
                page.close()
            except Exception:
                pass
        return None

    def fetch_channel_history_paginated(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        messages: list[dict] = []
        cursor: str | None = None
        page = 0

        while True:
            params = {"channel": channel_id, "limit": limit}
            if latest:
                params["latest"] = latest
            if oldest:
                params["oldest"] = oldest
            if cursor:
                params["cursor"] = cursor
            data = self._slack_api_call("conversations.history", params=params)
            messages.extend(data.get("messages", []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break
        self._set_pagination_stats("history", page, len(messages))
        return messages

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict]:
        matches: list[dict] = []
        page = 1
        while True:
            params = {"query": query, "count": count, "page": page}
            data = self._slack_api_call("search.messages", params=params)
            message_block = data.get("messages", {}) if isinstance(data, dict) else {}
            matches.extend(message_block.get("matches", []))
            paging = message_block.get("paging", {}) if isinstance(message_block, dict) else {}
            total_pages = paging.get("pages")
            if not total_pages or page >= total_pages or page >= max_pages:
                break
            page += 1
        self._set_pagination_stats("search", page, len(matches))
        return matches

    def list_conversations_paginated(
        self,
        types: str = "im,mpim",
        limit: int = 200,
        max_pages: int = 10,
        exclude_archived: bool = True,
    ) -> list[dict[str, Any]]:
        """List conversations (supports DMs via types=im,mpim)."""
        conversations: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0
        while True:
            params: dict[str, Any] = {
                "types": types,
                "limit": limit,
                "exclude_archived": 1 if exclude_archived else 0,
            }
            if cursor:
                params["cursor"] = cursor
            data = self._slack_api_call("conversations.list", params=params)
            conversations.extend(cast(list[dict[str, Any]], data.get("channels", [])))
            cursor = cast(dict, data.get("response_metadata", {}) or {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break
        self._set_pagination_stats("conversations.list", page, len(conversations))
        return conversations

    def fetch_thread_replies_paginated(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0
        while True:
            params: dict[str, Any] = {"channel": channel_id, "ts": thread_ts, "limit": limit}
            if cursor:
                params["cursor"] = cursor
            data = self._slack_api_call("conversations.replies", params=params)
            messages.extend(cast(list[dict[str, Any]], data.get("messages", [])))
            cursor = cast(dict, data.get("response_metadata", {}) or {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break
        return messages

    def get_message_permalink(self, channel_id: str, message_ts: str) -> str | None:
        try:
            data = self._slack_api_call("chat.getPermalink", params={"channel": channel_id, "message_ts": message_ts})
            return cast(str | None, data.get("permalink"))
        except Exception:
            return None

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self._slack_api_call("conversations.setTopic", method="POST", body={"channel": channel_id, "topic": topic})

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        data = self._slack_api_call("conversations.info", params={"channel": channel_id})
        return cast(dict[str, Any], data.get("channel", {}))

    def get_user_info(self, user_id: str) -> dict[str, Any]:
        data = self._slack_api_call("users.info", params={"user": user_id})
        return cast(dict[str, Any], data.get("user", {}))

    def auth_test(self) -> dict[str, Any]:
        return self._slack_api_call("auth.test")

    def reset_stats(self) -> None:
        self.stats = {
            "api_calls": 0,
            "retries": 0,
            "rate_limit_hits": 0,
            "rate_limit_sleep_s": 0.0,
            "retry_sleep_s": 0.0,
        }
        self.pagination_stats = {}

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def get_pagination_stats(self) -> dict[str, Any]:
        return dict(self.pagination_stats)

    def _set_pagination_stats(self, method: str, pages: int, messages: int) -> None:
        self.pagination_stats = {
            "method": method,
            "pages": pages,
            "messages": messages,
        }


class NotionBrowserClient:
    supports_verification = False
    supports_last_synced_update = True
    MAIN_SELECTOR = "div[role='main']"
    PAGE_CANVAS_SELECTOR = "div[data-qa='page-canvas']"
    READY_SELECTORS = "div[role='main'], div[data-qa='page-canvas']"
    CONTENT_EDITABLE_SELECTOR = "div[contenteditable='true']"

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config
        self.stats: dict[str, Any] = {}
        self.reset_stats()

    def _with_page(self, url: str, func, retry_on_failure: bool = True):
        page = None
        last_error = None
        try:
            page = self.session.new_page(url)
            for attempt in range(self.config.max_retries if retry_on_failure else 1):
                try:
                    self._wait_for_notion_ready(page)
                    if self.config.verbose_logging:
                        logger.info("Running page action for %s (attempt %s)", url, attempt + 1)
                    self.session._apply_overlay(page, f"Working on {url} ({attempt + 1})")
                    result = func(page)
                    logger.info(f"Page action completed successfully for URL: {url}")
                    if self.config.screenshot_on_step:
                        self.session._maybe_screenshot(page, "success")
                    self.session.log_event("page_action_success", {"url": url})
                    return result
                except Exception as e:
                    last_error = e
                    logger.error(f"Page action failed for URL {url} (attempt {attempt + 1}): {e}")
                    self.session.log_event(
                        "page_action_error",
                        {"url": url, "attempt": attempt + 1, "error": str(e)},
                    )
                    if self.config.screenshot_on_error:
                        self.session._maybe_screenshot(page, "error")
                    self.session._maybe_dom_snapshot(page, "error")
                    if self.config.auto_recover and self.config.auto_recover_refresh:
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=self.config.timeout_ms)
                            self.session._smart_wait(page)
                        except Exception:
                            pass
                    if retry_on_failure and attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_ms / 1000)
                    else:
                        break
            if last_error:
                logger.error(f"Page action failed after {self.config.max_retries} attempts for URL {url}")
                raise last_error
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def _wait_for_notion_ready(self, page) -> None:
        timeout_s = max(1, int(self.config.interactive_login_timeout_ms / 1000))
        start = time.time()
        while time.time() - start < timeout_s:
            current_url = page.url or ""
            if "login" in current_url or "signup" in current_url:
                if not self.config.interactive_login or self.config.headless:
                    raise RuntimeError(
                        "Notion login required. Recreate browser storage state "
                        "with scripts/create_storage_state.py to avoid re-login."
                    )
                logger.warning(
                    "Notion login required. Complete login in the opened browser window "
                    "(waiting up to %s seconds).",
                    int(self.config.interactive_login_timeout_ms / 1000),
                )
            try:
                if page.query_selector(self.READY_SELECTORS):
                    if self.config.auto_save_storage_state:
                        self.session.save_storage_state()
                    return
            except Exception:
                pass
            page.wait_for_timeout(1000)
        raise RuntimeError("Timed out waiting for Notion to load.")

    def _page_url(self, page_id_or_url: str) -> str:
        if page_id_or_url.startswith("http"):
            return page_id_or_url
        return f"{self.config.notion_base_url.rstrip('/')}/{page_id_or_url}"

    def append_audit_note(self, page_id: str, text: str) -> str:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1500)
            page.wait_for_selector(self.MAIN_SELECTOR, timeout=15000)
            editor = page.locator(f"{self.MAIN_SELECTOR} {self.CONTENT_EDITABLE_SELECTOR}").last
            if editor.count() == 0:
                editor = page.locator(self.CONTENT_EDITABLE_SELECTOR).last
            editor.click(timeout=15000)
            page.keyboard.type(text)
            page.keyboard.press("Enter")

        self._with_page(url, action)
        self.stats["ui_actions"] += 1
        return "browser-note"

    def get_block(self, block_id: str) -> dict:
        return {}

    def update_page_property(self, page_id: str, property_name: str, date_iso: str) -> None:
        url = self._page_url(page_id)
        date_value = date_iso.split("T")[0] if date_iso else ""

        def action(page):
            page.wait_for_timeout(1500)
            label = page.get_by_text(property_name, exact=True)
            label.wait_for(timeout=10000)

            row = label.locator(
                "xpath=ancestor::div[@role='row' or @role='listitem' or @data-property-id][1]"
            )
            if row.count() == 0:
                row = label.locator("xpath=..")

            value_cell = row.locator(
                "css=div[contenteditable='true'], css=div[role='button'], css=div[role='textbox']"
            ).first
            value_cell.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Meta+A")
            if date_value:
                page.keyboard.type(date_value)
            page.keyboard.press("Enter")

        self._with_page(url, action)
        self.stats["ui_actions"] += 1

    def get_page(self, page_id: str) -> dict:
        return {}

    def query_database(self, database_id: str, filter: dict | None = None) -> list[dict]:
        logger.warning("query_database not implemented in NotionBrowserClient fallback.")
        return []

    def search_pages(self, query: str) -> list[dict]:
        logger.warning("search_pages not implemented in NotionBrowserClient fallback.")
        return []

    def reset_stats(self) -> None:
        self.stats = {
            "ui_actions": 0,
            "errors": 0,
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def check_page_access(self, page_id: str) -> bool:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1500)
            current_url = page.url or ""
            if "login" in current_url or "signup" in current_url:
                return False
            try:
                page.wait_for_selector(self.MAIN_SELECTOR, timeout=10000)
            except Exception:
                return False
            return True

        return bool(self._with_page(url, action))
