# codeeditor/ai/session_logger.py
# JSON session logger — one file per application session.

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class SessionLogger:
    """Writes a single JSON log file for the current app session."""

    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)

        self._session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._file_path = log_dir / f"session-{self._session_id}.json"
        self._data: dict = {
            "session_id": self._session_id,
            "started": datetime.now().isoformat(),
            "ended": None,
            "messages": [],
        }
        self._flush()

    @property
    def session_id(self) -> str:
        return self._session_id

    def log_message(
        self,
        persona: str,
        role: str,
        content: str,
        attachments: list[str] | None = None,
    ) -> None:
        """Append a message and flush to disk immediately."""
        entry: dict = {
            "timestamp": datetime.now().isoformat(),
            "persona": persona,
            "role": role,
            "content": content,
        }
        if attachments:
            entry["attachments"] = attachments
        self._data["messages"].append(entry)
        self._flush()

    def close(self) -> None:
        """Finalize the session with an end timestamp."""
        self._data["ended"] = datetime.now().isoformat()
        self._flush()

    def _flush(self) -> None:
        """Write the full session dict to disk."""
        self._file_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
