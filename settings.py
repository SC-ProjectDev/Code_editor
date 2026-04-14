# codeeditor/settings.py
# Persistent application settings backed by ~/.codeeditor/config.json.

from __future__ import annotations

import json
from pathlib import Path

from codeeditor.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_FONT_SIZE,
    DEFAULT_TAB_WIDTH,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    MAX_RECENT_FILES,
)


class Settings:
    """Singleton settings manager that persists to config.json."""

    _instance: Settings | None = None

    @classmethod
    def instance(cls) -> Settings:
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    def __init__(self):
        self._data: dict = {}
        self._load()

    # ── Theme ─────────────────────────────────────────────

    def theme(self) -> str:
        return self._get("theme", "dark")

    def set_theme(self, theme: str) -> None:
        self._set("theme", theme)

    # ── Window Geometry ───────────────────────────────────

    def window_geometry(self) -> dict:
        return self._get("window_geometry", {
            "x": 100, "y": 100,
            "width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT,
        })

    def set_window_geometry(self, x: int, y: int, w: int, h: int) -> None:
        self._set("window_geometry", {"x": x, "y": y, "width": w, "height": h})

    # ── Splitter Sizes ────────────────────────────────────

    def splitter_sizes(self) -> dict[str, list[int]]:
        return self._get("splitter_sizes", {})

    def set_splitter_sizes(self, name: str, sizes: list[int]) -> None:
        current = self.splitter_sizes()
        current[name] = sizes
        self._set("splitter_sizes", current)

    # ── Last Opened Folder ────────────────────────────────

    def last_opened_folder(self) -> str | None:
        return self._get("last_opened_folder", None)

    def set_last_opened_folder(self, path: str) -> None:
        self._set("last_opened_folder", path)

    # ── Editor Settings ───────────────────────────────────

    def font_size(self) -> int:
        return self._get("font_size", DEFAULT_FONT_SIZE)

    def set_font_size(self, size: int) -> None:
        self._set("font_size", size)

    def tab_width(self) -> int:
        return self._get("tab_width", DEFAULT_TAB_WIDTH)

    def set_tab_width(self, width: int) -> None:
        self._set("tab_width", width)

    def wrap_mode(self) -> bool:
        return self._get("wrap_mode", False)

    def set_wrap_mode(self, enabled: bool) -> None:
        self._set("wrap_mode", enabled)

    # ── Recent Files ──────────────────────────────────────

    def recent_files(self) -> list[str]:
        return self._get("recent_files", [])

    def add_recent_file(self, path: str) -> None:
        recent = self.recent_files()
        # Deduplicate — move to front if already present
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        # Limit
        self._set("recent_files", recent[:MAX_RECENT_FILES])

    # ── Internal I/O ──────────────────────────────────────

    def _get(self, key: str, default):
        return self._data.get("settings", {}).get(key, default)

    def _set(self, key: str, value) -> None:
        if "settings" not in self._data:
            self._data["settings"] = {}
        self._data["settings"][key] = value
        self._save()

    def _load(self) -> None:
        try:
            self._data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
