from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, TypedDict, cast

logger = logging.getLogger(__name__)

class BrowserError(Exception):
    """Base class for browser automation errors."""
    pass

class SessionExpiredError(BrowserError):
    """Raised when a browser session has expired and needs refresh."""
    pass

class LoadBalancer:
    """Manages load balancing for distributed environments."""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.workers: list[str] = []
        self.active_workers = 0

    def add_worker(self, worker_id: str):
        """Add a worker to the load balancer."""
        if worker_id not in self.workers:
            self.workers.append(worker_id)

    def remove_worker(self, worker_id: str):
        """Remove a worker from the load balancer."""
        if worker_id in self.workers:
            self.workers.remove(worker_id)

    def get_available_worker(self) -> str | None:
        """Get an available worker for processing."""
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
        """Get the number of available workers."""
        return len(self.workers)

    def get_active_worker_count(self) -> int:
        """Get the number of active workers."""
        return self.active_workers


class ScalabilityManager:
    """Manages optimizations for handling larger datasets and higher traffic."""

    def __init__(self, max_concurrent_sessions: int = 5, batch_size: int = 100):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.batch_size = batch_size
        self.active_sessions = 0

    def acquire_session(self) -> bool:
        """Acquire a session slot for concurrent operations."""
        if self.active_sessions < self.max_concurrent_sessions:
            self.active_sessions += 1
            return True
        return False

    def release_session(self):
        """Release a session slot after operation completion."""
        if self.active_sessions > 0:
            self.active_sessions -= 1

    def get_batch_size(self) -> int:
        """Get the recommended batch size for operations."""
        return self.batch_size

    def optimize_batch_size(self, data_size: int) -> int:
        """Optimize the batch size based on the dataset size."""
        if data_size > 1000:
            self.batch_size = 200
        elif data_size > 500:
            self.batch_size = 150
        else:
            self.batch_size = 100
        return self.batch_size


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
        self.start_time = 0.0

    def start_monitoring(self):
        """Start monitoring a sync operation."""
        self.start_time = time.time()

    def stop_monitoring(self, success: bool, operation_name: str | None = None):
        """Stop monitoring a sync operation and record metrics."""
        if self.start_time == 0.0:
            logger.warning("Stop monitoring called before start monitoring.")
            return

        duration_ms = (time.time() - self.start_time) * 1000
        self.metrics["sync_operations"] += 1
        self.metrics["total_time_ms"] += duration_ms

        if success:
            self.metrics["successful_operations"] += 1
        else:
            self.metrics["failed_operations"] += 1
            if operation_name:
                self.metrics["bottlenecks"].append(
                    {"operation": operation_name, "duration_ms": duration_ms, "timestamp": time.time()}
                )

        self.metrics["average_time_ms"] = self.metrics["total_time_ms"] / self.metrics["sync_operations"]

    def get_metrics(self) -> dict[str, Any]:
        """Get the current performance metrics."""
        return cast(dict[str, Any], self.metrics)

    def get_bottlenecks(self) -> list[dict[str, Any]]:
        """Get a list of identified bottlenecks."""
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


class RecoveryManager:
    """Manages automatic recovery mechanisms for common failure scenarios."""

    def __init__(self, max_retries: int = 3, retry_delay_ms: int = 1000):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.recovery_attempts = 0

    def handle_failure(self, error: Exception, recovery_action: Callable[[], None]) -> bool:
        """Attempt to recover from a failure by executing a recovery action."""
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
    proxy_server: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

_sync_playwright: Any = None
try:
    from playwright.sync_api import sync_playwright as _sync_playwright
except ImportError:
    pass

sync_playwright: Any = _sync_playwright


class BrowserSession:
    def __init__(self, config: BrowserAutomationConfig):
        self.config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self.recovery_manager = RecoveryManager(max_retries=config.max_retries, retry_delay_ms=config.retry_delay_ms)
        self.performance_monitor = PerformanceMonitor()
        self.scalability_manager = ScalabilityManager(max_concurrent_sessions=5, batch_size=100)
        self.load_balancer = LoadBalancer(max_workers=5)
        self._step_counter = 0
        self._action_start_time: float = 0.0
        self.last_refresh_time: float = time.time()

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
                "Browser storage state not found. Create it with scripts/create_storage_state.py to avoid re-login."
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
            
            if self.config.proxy_server:
                proxy_args: dict[str, str] = {"server": self.config.proxy_server}
                if self.config.proxy_username:
                    proxy_args["username"] = self.config.proxy_username
                if self.config.proxy_password:
                    proxy_args["password"] = self.config.proxy_password
                launch_args["proxy"] = proxy_args

            if self.config.user_data_dir:
                # Ensure user_data_dir is absolute to avoid relative path confusion
                data_dir = os.path.abspath(self.config.user_data_dir)
                os.makedirs(data_dir, exist_ok=True)
                
                try:
                    self._context = self._playwright.chromium.launch_persistent_context(
                        data_dir,
                        **launch_args,
                    )
                except Exception as e:
                    if "profile is in use" in str(e).lower() or "locked" in str(e).lower():
                        logger.warning("Browser profile is locked. Attempting to kill hanging processes...")
                        # Optional: Add logic to find and kill hanging playwright/chrome processes
                        # For now, let's try to wait briefly
                        time.sleep(2)
                        self._context = self._playwright.chromium.launch_persistent_context(
                            data_dir,
                            **launch_args,
                        )
                    else:
                        raise

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

    def close(self) -> None:
        """Close the browser session."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser session: {e}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
 
    def refresh_session(self) -> None:
        """Force a browser session refresh by restarting it."""
        logger.info("Refreshing browser session...")
        self.close()
        # If using persistent context, maybe delete the session lock file if it exists
        if self.config.user_data_dir:
            lock_file = os.path.join(self.config.user_data_dir, "SingletonLock")
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except Exception:
                    pass
        self.start()
        self.last_refresh_time = time.time()

    def request(self) -> Any:
        """Get the APIRequestContext for the current session."""
        if not self._context:
            self.start()
        return self._context.request

    def new_page(self, url: str | None = None) -> Any:
        """Create a new page in the current session."""
        if not self._context:
            self.start()
        page = self._context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
            self._smart_wait(page)
        return page

    def save_storage_state(self, path: str | None = None) -> None:
        """Save the current storage state to a file."""
        if not self._context:
            return
        path = path or self.config.storage_state_path
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._context.storage_state(path=path)
            if self.config.verbose_logging:
                logger.info("Saved browser storage state to %s", path)
        except Exception as exc:
            logger.warning("Failed to save browser storage state: %s", exc)

    @property
    def context(self) -> Any:
        """Get the current browser context."""
        if not self._context:
            self.start()
        return self._context

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
        
        duration = 0.0
        if self._action_start_time > 0:
            duration = time.time() - self._action_start_time
            
        status_text = f"🚀 {text}"
        if duration > 0.1:
            status_text += f" ({duration:.1f}s)"
            
        proxy_info = ""
        if self.config.proxy_server:
            proxy_info = f" | 🌐 {self.config.proxy_server}"
            
        refresh_info = ""
        refresh_age = time.time() - self.last_refresh_time
        if refresh_age > 60:
            refresh_info = f" | 🕒 Refresh: {int(refresh_age/60)}m ago"
        else:
            refresh_info = f" | 🕒 Refresh: {int(refresh_age)}s ago"

        try:
            page.evaluate(
                """
                (data) => {
                    const id = '__scalers_overlay__';
                    let el = document.getElementById(id);
                    if (!el) {
                        el = document.createElement('div');
                        el.id = id;
                        el.style.position = 'fixed';
                        el.style.top = '12px';
                        el.style.right = '12px';
                        el.style.zIndex = '9999999';
                        el.style.padding = '8px 14px';
                        el.style.background = 'rgba(15, 15, 15, 0.75)';
                        el.style.backdropFilter = 'blur(12px) saturate(180%)';
                        el.style.webkitBackdropFilter = 'blur(12px) saturate(180%)';
                        el.style.border = '1px solid rgba(255, 255, 255, 0.125)';
                        el.style.color = '#fff';
                        el.style.fontSize = '13px';
                        el.style.fontWeight = '500';
                        el.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
                        el.style.borderRadius = '10px';
                        el.style.boxShadow = '0 8px 32px 0 rgba(0, 0, 0, 0.37)';
                        el.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
                        el.style.pointerEvents = 'none';
                        el.style.display = 'flex';
                        el.style.flexDirection = 'column';
                        el.style.alignItems = 'flex-end';
                        el.style.gap = '4px';
                        document.body.appendChild(el);
                    }
                    el.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span>${data.text}</span>
                        </div>
                        <div style="font-size: 10px; opacity: 0.7; font-weight: 400;">
                            ${data.extra}
                        </div>
                    `;
                    el.style.opacity = '1';
                }
                """,
                {"text": status_text, "extra": f"{proxy_info}{refresh_info}".strip(" | ")},
            )
        except Exception:
            pass

    def _smart_wait(self, page) -> None:
        if not self.config.smart_wait:
            return
        try:
            if self.config.smart_wait_network_idle:
                try:
                    page.wait_for_load_state("networkidle", timeout=self.config.smart_wait_timeout_ms)
                except Exception:
                    pass
            page.wait_for_timeout(self.config.smart_wait_stability_ms)
        except Exception as exc:
            logger.warning("Smart wait error: %s", exc)


class BaseBrowserClient:
    """Base class for browser-based clients to consolidate common logic."""

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config
        self.stats: dict[str, Any] = {}
        self.reset_stats()

    def _with_page(self, url: str, func, retry_on_failure: bool = True):
        """Execute a function with a new page, handling retries and cleanup."""
        page = None
        last_error = None
        try:
            page = self.session.new_page(url)
            max_attempts = self.config.max_retries if retry_on_failure else 1
            for attempt in range(max_attempts):
                try:
                    self._wait_until_ready(page)
                    if self.config.verbose_logging:
                        logger.info("Running page action for %s (attempt %s)", url, attempt + 1)
                    self.session._action_start_time = time.time()
                    self.session._apply_overlay(page, f"Working on {url} ({attempt + 1})")
                    
                    result = func(page)
                    
                    self.session._action_start_time = 0.0
                    logger.info(f"Page action completed successfully for URL: {url}")
                    if self.config.screenshot_on_step:
                        self.session._maybe_screenshot(page, "success")
                    self.session.log_event("page_action_success", {"url": url})
                    return result
                except SessionExpiredError:
                    logger.warning("Session expired for URL %s, attempting refresh...", url)
                    self.session.refresh_session()
                    if retry_on_failure and attempt < max_attempts - 1:
                        continue
                    else:
                        raise
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
                    
                    if retry_on_failure and attempt < max_attempts - 1:
                        time.sleep(self.config.retry_delay_ms / 1000)
                    else:
                        break
            if last_error:
                logger.error(f"Page action failed after {max_attempts} attempts for URL {url}")
                raise last_error
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def _wait_until_ready(self, page) -> None:
        """Override in subclasses to wait for specific app readiness."""
        pass

    def reset_stats(self) -> None:
        """Reset client statistics."""
        self.stats = {"errors": 0}

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        return dict(self.stats)
