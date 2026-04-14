# codeeditor/ai/worker.py
# Shared QThread worker for non-blocking API calls.

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class AIWorker(QThread):
    """Runs a callable in a background thread and emits the result."""

    finished = Signal(str)  # response text on success
    errored = Signal(str)   # error message on failure

    def __init__(self, task_fn: Callable[[], str], parent=None):
        super().__init__(parent)
        self._task_fn = task_fn

    def run(self) -> None:
        try:
            result = self._task_fn()
            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))
