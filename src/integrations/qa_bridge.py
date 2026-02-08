"""
QA Bridge - Interface to connect Scalers Slack with BugHerd QA Engine.

This bridge allows the Scalers Slack engine to:
1. Trigger QA checks on project websites
2. Compare Google Doc content with live sites
3. Check SEO metadata
4. Verify metrics and copy

The actual QA engine lives in the parent directory's project.
This bridge imports and wraps it for use in the Scalers Slack context.
"""

import logging
import os
import sys
from typing import Any, cast

logger = logging.getLogger(__name__)

# Add parent directory to path to import QA engine
# Structure: auto-bugherd/Scalers slack/src/integrations/qa_bridge.py
# Parent src: auto-bugherd/src/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCALERS_SLACK_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))  # Scalers slack/
_AUTO_BUGHERD_ROOT = os.path.dirname(_SCALERS_SLACK_ROOT)  # auto-bugherd/
_PARENT_SRC = os.path.join(_AUTO_BUGHERD_ROOT, "src")

if os.path.isdir(_PARENT_SRC) and _PARENT_SRC not in sys.path:
    sys.path.insert(0, _PARENT_SRC)


class QABridge:
    """
    Bridge to connect Scalers Slack engine with BugHerd QA Engine.

    Provides a clean interface for:
    - Running QA checks on websites
    - Comparing Google Docs with live content
    - SEO metadata verification
    - Copy/metrics verification
    """

    def __init__(
        self,
        config_path: str | None = None,
        bugherd_api_key: str | None = None,
    ):
        """
        Initialize the QA bridge.

        Args:
            config_path: Path to config.json (defaults to parent project's config)
            bugherd_api_key: BugHerd API key for auto-ticketing
        """
        self._engine = None
        self._config_path = config_path
        self._bugherd_api_key = bugherd_api_key or os.getenv("BUGHERD_API_KEY")
        self._stats = {
            "qa_runs": 0,
            "issues_found": 0,
            "tickets_created": 0,
            "pages_checked": 0,
        }

    @property
    def engine(self) -> Any:
        """Lazy-load the BugHerd QA engine from parent project."""
        if self._engine is None:
            # Use parent project's config if not specified
            if self._config_path is None:
                self._config_path = os.path.join(_AUTO_BUGHERD_ROOT, "config.json")

            try:
                # The parent engine uses relative imports, so we need to handle this
                # by temporarily making the parent src a proper package
                import importlib.util

                # First, load the dependencies that the engine needs
                deps = [
                    "bugherd_client",
                    "doc_parser",
                    "link_checker",
                    "report_generator",
                    "element_locator",
                    "state_manager",
                    "screenshotter",
                    "browser_inspector",
                ]
                loaded_modules = {}
                for dep in deps:
                    dep_path = os.path.join(_PARENT_SRC, f"{dep}.py")
                    if os.path.exists(dep_path):
                        spec = importlib.util.spec_from_file_location(dep, dep_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[dep] = module
                            try:
                                spec.loader.exec_module(module)
                                loaded_modules[dep] = module
                            except Exception as e:
                                logger.debug(f"Could not load {dep}: {e}")

                # Now try to load the engine
                engine_path = os.path.join(_PARENT_SRC, "engine.py")
                if os.path.exists(engine_path):
                    # Read and modify the engine source to use absolute imports
                    with open(engine_path, "r") as f:
                        source = f.read()

                    # Replace relative imports with absolute imports
                    modified_source = source.replace("from .", "from ")

                    # Compile and execute
                    code = compile(modified_source, engine_path, "exec")
                    engine_module = type(sys)("bugherd_engine")
                    engine_module.__file__ = engine_path
                    exec(code, engine_module.__dict__)

                    self._engine = engine_module.BugHerdEngine(
                        config_path=self._config_path,
                        bugherd_api_key=self._bugherd_api_key,
                    )
                    logger.info("QA Engine initialized successfully")
                else:
                    logger.warning("QA Engine file not found at %s", engine_path)

            except Exception as e:
                logger.warning(
                    "QA Engine not available: %s. Make sure the parent auto-bugherd project is accessible.",
                    e,
                )
                self._engine = None

        return self._engine

    @property
    def is_available(self) -> bool:
        """Check if QA integration is available."""
        return self.engine is not None

    def run_qa_check(
        self,
        url: str,
        google_doc_url: str | None = None,
        auto_ticket: bool = False,
        bugherd_project_id: str | None = None,
        check_links: bool = False,
        use_browser: bool = True,
    ) -> dict[str, Any]:
        """
        Run a QA check on a URL.

        Args:
            url: URL to check
            google_doc_url: Optional Google Doc URL for comparison
            auto_ticket: Whether to auto-create BugHerd tickets for issues
            bugherd_project_id: BugHerd project ID for ticket creation
            check_links: Whether to check for broken links
            use_browser: Whether to use browser rendering (Playwright)

        Returns:
            Dict with status, issues found, and any errors
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "QA Engine not available",
            }

        try:
            self._stats["qa_runs"] += 1
            self._stats["pages_checked"] += 1

            success = self.engine.run_qa_ad_hoc(
                url=url,
                doc_url=google_doc_url,
                auto_ticket=auto_ticket,
                project_id=bugherd_project_id,
                check_links=check_links,
                use_browser=use_browser,
            )

            return {
                "status": "success" if success else "issues_found",
                "url": url,
                "passed": success,
                "doc_url": google_doc_url,
            }

        except Exception as e:
            logger.error(f"Error running QA check: {e}")
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }

    def run_project_qa(
        self,
        project_id: str,
        auto_ticket: bool = False,
        check_links: bool = False,
        use_browser: bool = True,
    ) -> dict[str, Any]:
        """
        Run QA checks on all pages in a project.

        Args:
            project_id: Project ID from config.json
            auto_ticket: Whether to auto-create BugHerd tickets
            check_links: Whether to check for broken links
            use_browser: Whether to use browser rendering

        Returns:
            Dict with status, pages checked, and results
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "QA Engine not available",
            }

        try:
            self._stats["qa_runs"] += 1

            success = self.engine.run_qa_project(
                project_id=project_id,
                auto_ticket=auto_ticket,
                check_links=check_links,
                use_browser=use_browser,
            )

            return {
                "status": "success" if success else "issues_found",
                "project_id": project_id,
                "passed": success,
            }

        except Exception as e:
            logger.error(f"Error running project QA: {e}")
            return {
                "status": "error",
                "error": str(e),
                "project_id": project_id,
            }

    def check_seo_metadata(
        self,
        url: str,
        expected_title: str | None = None,
        expected_description: str | None = None,
        expected_h1: str | None = None,
    ) -> dict[str, Any]:
        """
        Check SEO metadata on a page.

        Args:
            url: URL to check
            expected_title: Expected page title
            expected_description: Expected meta description
            expected_h1: Expected H1 header

        Returns:
            Dict with SEO check results
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "QA Engine not available",
            }

        try:
            soup = self.engine.fetch_live_soup(url)
            if not soup:
                return {
                    "status": "error",
                    "error": f"Could not fetch {url}",
                }

            target_meta = {}
            if expected_title:
                target_meta["title"] = expected_title
            if expected_description:
                target_meta["description"] = expected_description
            if expected_h1:
                target_meta["h1"] = expected_h1

            issues = self.engine.check_seo_metadata(
                soup=soup,
                target_meta=target_meta,
                page_name=url,
                page_url=url,
                auto_ticket=False,
            )

            return {
                "status": "success",
                "url": url,
                "issues": issues,
                "passed": len(issues) == 0,
            }

        except Exception as e:
            logger.error(f"Error checking SEO metadata: {e}")
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }

    def compare_with_google_doc(
        self,
        url: str,
        google_doc_url: str,
    ) -> dict[str, Any]:
        """
        Compare live page content with a Google Doc.

        Args:
            url: URL of live page
            google_doc_url: Google Doc URL for comparison

        Returns:
            Dict with comparison results
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "QA Engine not available",
            }

        try:
            # Fetch Google Doc content
            doc_text = self.engine.doc_parser.fetch_text_public(google_doc_url)
            if not doc_text:
                return {
                    "status": "error",
                    "error": "Could not fetch Google Doc content",
                    "doc_url": google_doc_url,
                }

            # Fetch live page
            soup, content, _ = self.engine.fetch_live_data(url, use_browser=True)
            if not soup:
                return {
                    "status": "error",
                    "error": f"Could not fetch {url}",
                }

            # Extract expected SEO metadata from doc
            expected_seo = self.engine.doc_parser.extract_seo_metadata(doc_text)

            # Check SEO
            seo_issues = self.engine.check_seo_metadata(
                soup=soup,
                target_meta=expected_seo,
                page_name=url,
                page_url=url,
                auto_ticket=False,
            )

            # Check metrics
            metrics_results = self.engine.find_metrics_in_content(doc_text, content)
            missing_metrics = [m for m, found in metrics_results.items() if not found]

            return {
                "status": "success",
                "url": url,
                "doc_url": google_doc_url,
                "seo_issues": seo_issues,
                "missing_metrics": missing_metrics,
                "passed": len(seo_issues) == 0 and len(missing_metrics) == 0,
            }

        except Exception as e:
            logger.error(f"Error comparing with Google Doc: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def get_project_info(self, project_id: str) -> dict[str, Any] | None:
        """
        Get project information from the QA engine config.

        Args:
            project_id: Project ID to look up

        Returns:
            Project dict or None if not found
        """
        if not self.is_available:
            return None

        projects = self.engine.config.get("projects", [])
        for project in projects:
            if str(project.get("id")) == str(project_id):
                return cast(dict[str, Any], project)

        return None

    def list_projects(self) -> list[dict[str, Any]]:
        """
        List all configured projects.

        Returns:
            List of project dicts with id, name, and page count
        """
        if not self.is_available:
            return []

        projects = self.engine.config.get("projects", [])
        return [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "bugherd_project_id": p.get("bugherd_project_id"),
                "page_count": len(p.get("live_pages", {})),
                "has_google_doc": bool(p.get("google_doc_url")),
            }
            for p in projects
        ]

    def get_stats(self) -> dict[str, int]:
        """Get bridge usage statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._stats = {
            "qa_runs": 0,
            "issues_found": 0,
            "tickets_created": 0,
            "pages_checked": 0,
        }
