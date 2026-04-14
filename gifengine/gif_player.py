# codeeditor/gifengine/gif_player.py
# Dual-mode media widget: plays animated GIFs (QMovie) and MP4 clips (QMediaPlayer).
# Supports one-shot mode for reaction clips (play once, don't loop).

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QMovie
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QWidget,
)


class GifPlayer(QWidget):
    """Plays animated GIFs or short MP4 clips inside a resizable widget."""

    # Emitted when a non-looping GIF ends or an MP4 completes one loop
    gif_finished = Signal()

    MIN_HEIGHT = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gif_player")
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Stacked layout: index 0 = GIF label, index 1 = video widget ──
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        # GIF layer
        self._gif_label = QLabel()
        self._gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gif_label.setScaledContents(False)
        self._stack.addWidget(self._gif_label)  # index 0

        # Video layer
        self._video_widget = QVideoWidget()
        self._stack.addWidget(self._video_widget)  # index 1

        # Media player for MP4s
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.5)  # default 50% volume
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setVideoOutput(self._video_widget)
        self._media_player.mediaStatusChanged.connect(self._on_media_status)

        self._movie: QMovie | None = None
        self._mode: str = "gif"  # "gif" or "video"

        # One-shot mode: play clip once, don't loop
        self._one_shot: bool = False
        self._one_shot_seen_frame: int = -1

    # ── Public API ────────────────────────────────────────

    def play_gif(self, path: Path, one_shot: bool = False) -> None:
        """Load and start playing a GIF or MP4 from *path*.

        If *one_shot* is True, the clip plays once and emits gif_finished
        without looping (for reaction clips).
        """
        self.stop()
        self._one_shot = one_shot

        if not path.is_file():
            return

        if path.suffix.lower() == ".mp4":
            self._play_video(path)
        else:
            self._play_gif(path)

    def stop(self) -> None:
        """Stop current playback and clear the display."""
        if self._movie is not None:
            try:
                self._movie.frameChanged.disconnect(self._on_gif_frame_changed)
            except RuntimeError:
                pass
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None
            self._gif_label.clear()

        if self._media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._media_player.stop()

        self._mode = "gif"
        self._one_shot = False
        self._one_shot_seen_frame = -1

    def is_playing(self) -> bool:
        if self._mode == "video":
            return self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return self._movie is not None and self._movie.state() == QMovie.MovieState.Running

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute MP4 audio."""
        self._audio_output.setMuted(muted)

    def is_muted(self) -> bool:
        return self._audio_output.isMuted()

    def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)."""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._mode == "gif":
            self._scale_movie()

    # ── GIF internals ─────────────────────────────────────

    def _play_gif(self, path: Path) -> None:
        self._mode = "gif"
        self._stack.setCurrentIndex(0)

        self._movie = QMovie(str(path))
        if not self._movie.isValid():
            self._movie = None
            return

        self._movie.jumpToFrame(0)
        self._scale_movie()
        self._movie.finished.connect(self.gif_finished.emit)
        self._gif_label.setMovie(self._movie)

        # For one-shot mode on looping GIFs, track frames to detect
        # when the first cycle completes (frame wraps back to 0)
        if self._one_shot:
            self._one_shot_seen_frame = -1
            self._movie.frameChanged.connect(self._on_gif_frame_changed)

        self._movie.start()

    def _on_gif_frame_changed(self, frame_number: int) -> None:
        """Detect when a looping GIF completes its first cycle in one-shot mode."""
        if not self._one_shot or self._movie is None:
            return
        # If we've seen frames > 0 and now we're back at 0, first loop is done
        if frame_number == 0 and self._one_shot_seen_frame > 0:
            self._movie.stop()
            self.gif_finished.emit()
            return
        self._one_shot_seen_frame = frame_number

    def _scale_movie(self) -> None:
        if self._movie is None:
            return
        natural = self._movie.currentImage().size()
        if natural.isEmpty():
            return
        self._movie.setScaledSize(
            natural.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio)
        )

    # ── Video internals ───────────────────────────────────

    def _play_video(self, path: Path) -> None:
        self._mode = "video"
        self._stack.setCurrentIndex(1)
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.gif_finished.emit()
            if not self._one_shot:
                # Normal mode: loop the clip
                self._media_player.setPosition(0)
                self._media_player.play()
            # One-shot mode: clip ends here, gif_finished already emitted
