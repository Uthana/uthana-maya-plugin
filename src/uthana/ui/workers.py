"""QThread-based workers for async API operations.

These workers run API calls in background threads to avoid blocking
Maya's UI. Results are delivered via Qt signals.
"""

import time

from uthana.core import client
from uthana.core.logger import logger
from uthana.ui import QThread, Signal


class ApiWorker(QThread):
    """Generic worker for single API calls that should not block the UI."""

    finished = Signal(object)  # Emits OperationResult
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DownloadAndImportWorker(QThread):
    """Worker to download a motion file (the actual import must happen on the main thread)."""

    download_finished = Signal(object)  # OperationResult with file_path
    error = Signal(str)

    def __init__(self, domain, api_key, character_id, motion_id):
        super().__init__()
        self._domain = domain
        self._api_key = api_key
        self._character_id = character_id
        self._motion_id = motion_id

    def run(self):
        try:
            from uthana.core.types import DownloadRequest

            request = DownloadRequest(
                domain=self._domain,
                api_key=self._api_key,
                character_id=self._character_id,
                motion_id=self._motion_id,
            )
            result = client.download_motion_file(request)
            self.download_finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class VideoToMotionWorker(QThread):
    """Worker for video-to-motion: upload + poll for completion."""

    upload_complete = Signal(object)  # OperationResult
    job_status_updated = Signal(str, float)  # (status, progress_pct)
    motion_ready = Signal(str, str)  # (motion_id, motion_name)
    error = Signal(str)

    def __init__(self, api_key, domain, video_path, motion_name):
        super().__init__()
        self._api_key = api_key
        self._domain = domain
        self._video_path = video_path
        self._motion_name = motion_name
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Phase 1: Upload
        result = client.create_video_to_motion(
            self._api_key, self._domain, self._video_path, self._motion_name
        )

        if not result.success:
            self.error.emit(result.message)
            return

        job_id = result.data.get("job_id")
        self.upload_complete.emit(result)

        # Phase 2: Poll
        poll_count = 0
        max_polls = 600

        while not self._cancelled and poll_count < max_polls:
            time.sleep(2.0)
            poll_count += 1

            status_result = client.get_job_status(self._api_key, self._domain, job_id)
            if not status_result.success:
                self.error.emit(status_result.message)
                return

            status = status_result.data.get("status", "UNKNOWN")
            progress = min(95, 10 + (poll_count * 0.5))
            self.job_status_updated.emit(status, progress)

            if status == "FINISHED":
                job_result = status_result.data.get("result", {})
                motion_id = None
                if isinstance(job_result, dict):
                    motion_id = job_result.get("motion", {}).get("id")
                    if not motion_id:
                        motion_id = job_result.get("motion_id")

                if motion_id:
                    self.motion_ready.emit(motion_id, self._motion_name)
                else:
                    self.error.emit("Job finished but no motion ID in result")
                return

            elif status == "FAILED":
                error_msg = "Unknown error"
                job_result = status_result.data.get("result", {})
                if isinstance(job_result, dict):
                    error_msg = job_result.get("error", error_msg)
                self.error.emit(f"Job failed: {error_msg}")
                return

        if self._cancelled:
            logger.info("Video-to-motion job cancelled by user")
        else:
            self.error.emit("Job timed out")


class CharacterUploadWorker(QThread):
    """Worker for character file upload."""

    finished = Signal(object)  # OperationResult
    error = Signal(str)

    def __init__(self, api_key, domain, file_path, name, auto_rig):
        super().__init__()
        self._api_key = api_key
        self._domain = domain
        self._file_path = file_path
        self._name = name
        self._auto_rig = auto_rig

    def run(self):
        try:
            result = client.create_character(
                self._api_key, self._domain, self._file_path, self._name, self._auto_rig
            )
            if result.success:
                self.finished.emit(result)
            else:
                self.error.emit(result.message)
        except Exception as e:
            self.error.emit(str(e))
