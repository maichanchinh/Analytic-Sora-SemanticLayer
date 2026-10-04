"""Read-only loader for checked-in dashboard JSON configurations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_DASHBOARD_ID = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class DashboardConfigError(RuntimeError):
    """A dashboard config file is unreadable or violates its basic shape."""


class DashboardNotFoundError(LookupError):
    """No dashboard config exists for the requested identifier."""


def default_dashboard_config_dir() -> Path:
    """Resolve configs from the repository during development or packaged data."""
    repository_dir = Path(__file__).resolve().parents[2] / "dashboard" / "config"
    if repository_dir.is_dir():
        return repository_dir
    return Path(__file__).resolve().parent / "dashboard" / "config"


class DashboardConfigStore:
    """Expose dashboard configs from a fixed, read-only directory."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = (directory or default_dashboard_config_dir()).resolve()

    def list(self) -> list[dict[str, str]]:
        if not self._directory.exists():
            return []
        try:
            paths = sorted(self._directory.glob("*.json"), key=lambda path: path.stem)
        except OSError:
            raise DashboardConfigError("Could not list dashboard configs.") from None

        summaries = []
        for path in paths:
            try:
                payload = self._read(path.stem)
            except DashboardNotFoundError:
                raise DashboardConfigError("Dashboard config has an invalid filename.") from None
            summaries.append({"id": payload["id"], "title": payload["title"]})
        return summaries

    def get(self, dashboard_id: str) -> dict[str, Any]:
        if _DASHBOARD_ID.fullmatch(dashboard_id) is None:
            raise DashboardNotFoundError(dashboard_id)
        return self._read(dashboard_id)

    def _read(self, dashboard_id: str) -> dict[str, Any]:
        if _DASHBOARD_ID.fullmatch(dashboard_id) is None:
            raise DashboardNotFoundError(dashboard_id)

        path = self._directory / f"{dashboard_id}.json"
        try:
            if path.is_symlink() or not path.is_file():
                raise DashboardNotFoundError(dashboard_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except DashboardNotFoundError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise DashboardConfigError("Could not read dashboard config.") from None

        if (
            not isinstance(payload, dict)
            or payload.get("id") != dashboard_id
            or not isinstance(payload.get("title"), str)
            or not payload["title"].strip()
            or not isinstance(payload.get("filters"), list)
            or not all(isinstance(item, str) for item in payload["filters"])
            or not isinstance(payload.get("widgets"), list)
            or not all(isinstance(item, dict) for item in payload["widgets"])
        ):
            raise DashboardConfigError("Dashboard config has an invalid shape.")
        return payload
