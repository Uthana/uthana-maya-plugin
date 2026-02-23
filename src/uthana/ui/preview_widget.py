"""Animated motion preview widget.

Downloads a preview.webm from the API, extracts frames with ffmpeg,
and cycles through them in a QLabel using a QTimer.
"""

import os
import platform
import shutil
import subprocess
import tempfile

from uthana.core import client
from uthana.core.logger import logger
from uthana.ui import QtCore, QtGui, QThread, QTimer, QtWidgets, Signal


class PreviewDownloadWorker(QThread):
    """Download preview.webm and extract frames in a background thread.

    The server may need time to render the preview after motion creation,
    so this worker retries the download several times with delays.
    """

    frames_ready = Signal(list)  # list of PNG file paths
    status_update = Signal(str)  # progress messages
    error = Signal(str)

    MAX_RETRIES = 15
    RETRY_DELAY_SECS = 2.0

    def __init__(self, domain, api_key, character_id, motion_id):
        super().__init__()
        self._domain = domain
        self._api_key = api_key
        self._character_id = character_id
        self._motion_id = motion_id

    def run(self):
        try:
            # Retry loop — the preview video may not be ready immediately
            last_error = ""
            for attempt in range(1, self.MAX_RETRIES + 1):
                logger.info(
                    "Preview download attempt %d/%d for motion %s",
                    attempt,
                    self.MAX_RETRIES,
                    self._motion_id,
                )
                self.status_update.emit(
                    f"Loading preview (attempt {attempt}/{self.MAX_RETRIES})..."
                )

                result = client.download_preview_video(
                    self._domain, self._character_id, self._motion_id, self._api_key
                )

                if result.success:
                    webm_path = result.data.get("file_path", "")
                    if webm_path and os.path.exists(webm_path):
                        break
                    last_error = "Preview file not found after download"
                    logger.warning("Attempt %d: %s", attempt, last_error)
                else:
                    last_error = result.message
                    logger.warning("Attempt %d: %s", attempt, last_error)

                if attempt < self.MAX_RETRIES:
                    import time

                    time.sleep(self.RETRY_DELAY_SECS)
            else:
                # All retries exhausted
                error_msg = f"Preview not available after {self.MAX_RETRIES} attempts: {last_error}"
                logger.error(error_msg)
                self.error.emit(error_msg)
                return

            # Extract frames with ffmpeg
            frame_paths = _extract_frames(webm_path)
            if not frame_paths:
                msg = (
                    "Could not extract preview frames. "
                    "Install ffmpeg to enable animated previews "
                    "(brew install ffmpeg)"
                )
                logger.error(msg)
                self.error.emit(msg)
                return

            self.frames_ready.emit(frame_paths)

        except Exception as e:
            logger.error("Preview download failed: %s", e, exc_info=True)
            self.error.emit(str(e))


def _find_ffmpeg():
    """Find the ffmpeg executable."""
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd

    system = platform.system()
    fallback_paths = []
    if system == "Darwin":
        fallback_paths = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ]
    elif system == "Windows":
        fallback_paths = [
            os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe"),
            os.path.expandvars(r"%LocalAppData%\ffmpeg\bin\ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
    else:
        fallback_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/snap/bin/ffmpeg",
        ]

    for path in fallback_paths:
        try:
            result = subprocess.run([path, "-version"], capture_output=True, timeout=2)
            if result.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue

    return None


def _extract_frames(webm_path):
    """Extract frames from a WebM file using ffmpeg.

    Returns:
        list of PNG file paths (in a temp directory), or empty list on failure.
    """
    ffmpeg_cmd = _find_ffmpeg()
    if not ffmpeg_cmd:
        logger.warning("ffmpeg not found - animated preview unavailable")
        return []

    temp_dir = tempfile.mkdtemp(prefix="uthana_preview_")
    output_pattern = os.path.join(temp_dir, "frame_%04d.png")

    try:
        cmd = [
            ffmpeg_cmd,
            "-i",
            webm_path,
            "-vf",
            "scale=384:-2:flags=lanczos",
            "-vsync",
            "0",
            output_pattern,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error("ffmpeg failed: %s", result.stderr.decode())
            shutil.rmtree(temp_dir, ignore_errors=True)
            return []

        frame_files = sorted(f for f in os.listdir(temp_dir) if f.startswith("frame_"))
        logger.info("Extracted %d preview frames", len(frame_files))
        return [os.path.join(temp_dir, f) for f in frame_files]

    except Exception as e:
        logger.error("Frame extraction failed: %s", e)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return []


class PreviewWidget(QtWidgets.QWidget):
    """Animated preview player: cycles through extracted PNG frames."""

    # Emitted when the preview fails to load, so parent widgets can display it
    preview_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Frame display
        self._frame_label = QtWidgets.QLabel()
        self._frame_label.setAlignment(QtCore.Qt.AlignCenter)
        self._frame_label.setMinimumHeight(200)
        self._frame_label.setStyleSheet("background-color: #222;")
        layout.addWidget(self._frame_label)

        # Status
        self._status_label = QtWidgets.QLabel("")
        self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._status_label)

        # Timer for animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        # State
        self._pixmaps = []
        self._current_frame = 0
        self._frame_paths = []
        self._temp_dir = None
        self._worker = None

    def load_preview(self, domain, api_key, character_id, motion_id):
        """Start downloading and extracting preview frames."""
        self.stop()
        self._clear_frames()

        self._status_label.setText("Loading preview...")
        self._frame_label.setText("")

        self._worker = PreviewDownloadWorker(domain, api_key, character_id, motion_id)
        self._worker.frames_ready.connect(self._on_frames_ready)
        self._worker.status_update.connect(self._on_status_update)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_frames_ready(self, frame_paths):
        if not frame_paths:
            self._status_label.setText("No frames extracted")
            return

        self._frame_paths = frame_paths
        # Remember temp dir for cleanup (parent of first frame)
        self._temp_dir = os.path.dirname(frame_paths[0])

        # Load all frames as QPixmaps
        for path in frame_paths:
            pm = QtGui.QPixmap(path)
            if not pm.isNull():
                self._pixmaps.append(pm)

        if not self._pixmaps:
            self._status_label.setText("Failed to load frames")
            self._status_label.setStyleSheet("color: #ff6666; font-size: 11px;")
            return

        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._status_label.setText(f"{len(self._pixmaps)} frames")
        self._current_frame = 0
        self._show_frame(0)

        # Start playback at ~10 FPS (matching Blender's default)
        self._timer.start(100)

    def _on_status_update(self, msg):
        self._status_label.setText(msg)

    def _on_error(self, msg):
        logger.error("Motion preview failed: %s", msg)
        self._status_label.setText(msg)
        self._status_label.setStyleSheet("color: #ff6666; font-size: 11px;")
        self.preview_error.emit(msg)

    def _advance_frame(self):
        if not self._pixmaps:
            return
        self._current_frame = (self._current_frame + 1) % len(self._pixmaps)
        self._show_frame(self._current_frame)

    def _show_frame(self, idx):
        if 0 <= idx < len(self._pixmaps):
            pm = self._pixmaps[idx]
            # Scale to fit the label while keeping aspect ratio
            scaled = pm.scaled(
                self._frame_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self._frame_label.setPixmap(scaled)

    def stop(self):
        """Stop playback."""
        self._timer.stop()

    def _clear_frames(self):
        """Clear all loaded frames and clean up temp files."""
        self._timer.stop()
        self._pixmaps.clear()
        self._frame_paths.clear()
        self._current_frame = 0
        self._frame_label.clear()
        self._status_label.setText("")

        if self._temp_dir and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def clear(self):
        """Public method to reset the preview."""
        self._clear_frames()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if self._pixmaps:
            self._timer.start(100)
        super().showEvent(event)
