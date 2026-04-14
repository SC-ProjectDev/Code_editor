# codeeditor/gifengine/gif_state_manager.py
# Maps application states to GIF folders and drives the GifPlayer.
# Supports both persistent looping states and one-shot reaction clips.

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Dict, List, Set

from PySide6.QtCore import QObject, QTimer

from codeeditor.config import (
    GIF_BASE_DIR,
    GIF_CATEGORIES,
    GIF_PRIORITY,
    GIF_REACTION_CATEGORIES,
    GIF_ROTATION_INTERVAL_MS,
    IDLE_TIMEOUT_MS,
    MEDIA_EXTENSIONS,
    REACTION_SAFETY_TIMEOUT_MS,
    RETURNED_THRESHOLD_S,
    EASTER_EGG_MIN_INTERVAL_MS,
    EASTER_EGG_MAX_INTERVAL_MS,
)
from codeeditor.gifengine.gif_player import GifPlayer


class GifStateManager(QObject):
    """Priority-based state machine that picks GIFs from categorised folders.

    Also supports one-shot **reactions** — short clips that interrupt the
    current state, play once, and automatically revert.
    """

    def __init__(self, player: GifPlayer, parent=None):
        super().__init__(parent)
        self._player = player

        # Registry: state_name -> (folder_path, priority)
        self._registry: Dict[str, tuple[Path, int]] = {}

        # Currently active states (can overlap — highest priority wins)
        self._active_states: Set[str] = set()

        # Pre-register the built-in looping categories
        for cat in GIF_CATEGORIES:
            folder = GIF_BASE_DIR / cat
            priority = GIF_PRIORITY.get(cat, 0)
            self._registry[cat] = (folder, priority)

        # Pre-register one-shot reaction categories (priority is irrelevant)
        for cat in GIF_REACTION_CATEGORIES:
            folder = GIF_BASE_DIR / cat
            self._registry[cat] = (folder, 0)

        # Rotation timer — cycles to a new random GIF in the same folder
        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(GIF_ROTATION_INTERVAL_MS)
        self._rotation_timer.timeout.connect(self._rotate_gif)

        # Also rotate when a non-looping GIF finishes
        self._player.gif_finished.connect(self._rotate_gif)

        # Idle timer — transitions to "idle" after inactivity
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(IDLE_TIMEOUT_MS)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        # Track which folder we're currently playing from
        self._current_folder: Path | None = None

        # ── Reaction system ───────────────────────────────
        self._reacting: bool = False

        # Safety timer: force-revert if a reaction clip runs too long
        self._reaction_safety_timer = QTimer(self)
        self._reaction_safety_timer.setSingleShot(True)
        self._reaction_safety_timer.setInterval(REACTION_SAFETY_TIMEOUT_MS)
        self._reaction_safety_timer.timeout.connect(self._on_reaction_finished)

        # Per-state debounce timers for rapid-fire reactions
        self._reaction_debouncers: Dict[str, QTimer] = {}

        # "Returned after being away" detection
        self._last_activity_ts: float = time.monotonic()

        # Easter egg timer
        self._easter_egg_timer = QTimer(self)
        self._easter_egg_timer.setSingleShot(True)
        self._easter_egg_timer.timeout.connect(self._on_easter_egg_tick)
        self._schedule_next_easter_egg()

        # Start the idle countdown immediately
        self._idle_timer.start()

    # ── Public API — Looping states ───────────────────────

    def register_state(self, name: str, folder_path: Path, priority: int) -> None:
        """Add or update a state in the registry."""
        self._registry[name] = (folder_path, priority)

    def set_state(self, state_name: str) -> None:
        """Activate a state. If it's the highest priority, switch GIFs."""
        if state_name not in self._registry:
            return

        self._active_states.add(state_name)

        # Reset idle timer on any activity (except idle itself)
        if state_name != "idle":
            self._idle_timer.start()
            self.record_activity()

        # Error state always takes priority — force-finish any reaction
        if state_name == "error" and self._reacting:
            self._on_reaction_finished()

        self._resolve_and_play()

    def clear_state(self, state_name: str) -> None:
        """Deactivate a state and fall back to the next highest."""
        self._active_states.discard(state_name)
        self._resolve_and_play()

    # ── Public API — One-shot reactions ───────────────────

    def trigger_reaction(self, state_name: str) -> None:
        """Play a single random clip from *state_name*'s folder, then revert.

        The clip plays once (one-shot mode) and automatically returns to
        whatever looping state was active before.
        """
        if state_name not in self._registry:
            return

        # Don't interrupt error state
        if "error" in self._active_states:
            return

        folder = self._registry[state_name][0]
        clips = self._list_gifs(folder)
        if not clips:
            return  # no clips in folder — silently skip

        chosen = random.choice(clips)

        # If already reacting, clean up the previous reaction first
        if self._reacting:
            self._cleanup_reaction_signals()

        self._reacting = True

        # Pause the normal rotation
        self._rotation_timer.stop()

        # Rewire gif_finished: disconnect rotation, connect reaction handler
        try:
            self._player.gif_finished.disconnect(self._rotate_gif)
        except RuntimeError:
            pass
        self._player.gif_finished.connect(self._on_reaction_finished)

        # Play the clip in one-shot mode
        self._player.play_gif(chosen, one_shot=True)

        # Start safety timer
        self._reaction_safety_timer.start()

    def trigger_reaction_debounced(self, state_name: str, delay_ms: int) -> None:
        """Trigger a reaction with debouncing — rapid calls restart the timer."""
        if state_name in self._reaction_debouncers:
            timer = self._reaction_debouncers[state_name]
            timer.stop()
            timer.start(delay_ms)
        else:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.trigger_reaction(state_name))
            self._reaction_debouncers[state_name] = timer
            timer.start(delay_ms)

    def record_activity(self) -> None:
        """Track user activity and trigger 'returned' if they've been away."""
        now = time.monotonic()
        if now - self._last_activity_ts > RETURNED_THRESHOLD_S:
            # User has been away for 3+ minutes — welcome them back
            self.trigger_reaction("returned")
        self._last_activity_ts = now

    # ── Internals — State resolution ──────────────────────

    def _resolve_and_play(self) -> None:
        """Determine the highest-priority active state and play from its folder."""
        # Don't clobber an in-progress reaction
        if self._reacting:
            return

        if not self._active_states:
            # Nothing active — stop playback
            self._rotation_timer.stop()
            self._player.stop()
            self._current_folder = None
            return

        # Find highest-priority active state
        best_state = max(
            self._active_states,
            key=lambda s: self._registry[s][1],
        )
        folder = self._registry[best_state][0]

        if folder == self._current_folder:
            return  # already playing from this folder

        self._current_folder = folder
        self._play_random_from_folder(folder)

    def _play_random_from_folder(self, folder: Path) -> None:
        """Pick a random GIF from *folder* and play it."""
        gifs = self._list_gifs(folder)
        if not gifs:
            self._player.stop()
            self._rotation_timer.stop()
            return

        chosen = random.choice(gifs)
        self._player.play_gif(chosen)
        self._rotation_timer.start()

    def _rotate_gif(self) -> None:
        """Switch to another random GIF in the current folder."""
        if self._current_folder is None:
            return
        self._play_random_from_folder(self._current_folder)

    # ── Internals — Reaction cleanup ──────────────────────

    def _on_reaction_finished(self) -> None:
        """Called when a one-shot reaction clip ends (or safety timer fires)."""
        if not self._reacting:
            return  # idempotent guard

        self._reacting = False
        self._reaction_safety_timer.stop()

        self._cleanup_reaction_signals()

        # Force re-evaluation of the looping state
        self._current_folder = None
        self._resolve_and_play()

    def _cleanup_reaction_signals(self) -> None:
        """Rewire gif_finished back to normal rotation."""
        try:
            self._player.gif_finished.disconnect(self._on_reaction_finished)
        except RuntimeError:
            pass
        self._player.gif_finished.connect(self._rotate_gif)

    # ── Internals — Idle & Easter eggs ────────────────────

    def _on_idle_timeout(self) -> None:
        """Called when the inactivity timer fires."""
        self.set_state("idle")

    def _schedule_next_easter_egg(self) -> None:
        """Schedule the next easter egg at a random interval."""
        interval = random.randint(
            EASTER_EGG_MIN_INTERVAL_MS, EASTER_EGG_MAX_INTERVAL_MS
        )
        self._easter_egg_timer.setInterval(interval)
        self._easter_egg_timer.start()

    def _on_easter_egg_tick(self) -> None:
        """Fire an easter egg if conditions are right, then reschedule."""
        if "idle" in self._active_states and not self._reacting:
            self.trigger_reaction("easter_eggs")
        self._schedule_next_easter_egg()

    # ── Utilities ─────────────────────────────────────────

    @staticmethod
    def _list_gifs(folder: Path) -> List[Path]:
        """Return all supported media files (.gif, .mp4) in *folder*."""
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.iterdir() if p.suffix.lower() in MEDIA_EXTENSIONS)
