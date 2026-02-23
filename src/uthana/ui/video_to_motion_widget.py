"""Video-to-Motion widget for extracting motion from video files."""

import webbrowser

import maya.utils

from uthana import maya_motion, maya_utils
from uthana.core.logger import logger
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.preview_widget import PreviewWidget
from uthana.ui.workers import DownloadAndImportWorker, VideoToMotionWorker


class VideoToMotionWidget(CollapsibleSection):
    """Video file picker, upload, progress, and import."""

    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Video to Motion", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # Video file picker
        file_layout = QtWidgets.QHBoxLayout()
        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setPlaceholderText("Select a video file (.mp4, .mov)")
        file_layout.addWidget(self.file_path_input)

        self.browse_btn = QtWidgets.QPushButton("Browse")
        self.browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # Motion name
        layout.addWidget(QtWidgets.QLabel("Motion Name:"))
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Name for the generated motion")
        layout.addWidget(self.name_input)

        # Upload button
        self.upload_btn = QtWidgets.QPushButton("Generate motion from video")
        self.upload_btn.setMinimumHeight(36)
        self.upload_btn.clicked.connect(self._on_upload)
        layout.addWidget(self.upload_btn)

        # Progress
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # Preview section (hidden until motion is ready)
        self.preview_group = QtWidgets.QGroupBox("Motion Preview")
        preview_layout = QtWidgets.QVBoxLayout(self.preview_group)

        self.preview_info = QtWidgets.QLabel("")
        preview_layout.addWidget(self.preview_info)

        # Animated preview player
        self.preview_player = PreviewWidget()
        self.preview_player.preview_error.connect(self._on_preview_error)
        preview_layout.addWidget(self.preview_player)

        self.warning_label = QtWidgets.QLabel("Downloading will charge your account")
        self.warning_label.setStyleSheet("color: #ffaa00;")
        preview_layout.addWidget(self.warning_label)

        self.browser_btn = QtWidgets.QPushButton("Preview full animation in browser")
        self.browser_btn.setMinimumHeight(40)
        self.browser_btn.clicked.connect(self._on_open_browser)
        preview_layout.addWidget(self.browser_btn)

        self.download_btn = QtWidgets.QPushButton("Download & import (uses quota)")
        self.download_btn.setMinimumHeight(32)
        self.download_btn.clicked.connect(self._on_download)
        preview_layout.addWidget(self.download_btn)

        self.cancel_preview_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_preview_btn.clicked.connect(self._on_cancel_preview)
        preview_layout.addWidget(self.cancel_preview_btn)

        layout.addWidget(self.preview_group)
        self.preview_group.setVisible(False)

        # State
        self._worker = None
        self._download_worker = None
        self._pending_motion_id = ""
        self._pending_motion_name = ""
        self._pending_character_id = ""

    def _on_browse(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)"
        )
        if file_path:
            self.file_path_input.setText(file_path)

    def _on_upload(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        video_path = self.file_path_input.text().strip()
        motion_name = self.name_input.text().strip() or "Video Motion"

        if not api_key:
            self.status_label.setText("API Key is required")
            return
        if not video_path:
            self.status_label.setText("Select a video file first")
            return

        self.upload_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Uploading video...")

        self._worker = VideoToMotionWorker(api_key, domain, video_path, motion_name)
        self._worker.upload_complete.connect(self._on_upload_complete)
        self._worker.job_status_updated.connect(self._on_job_status)
        self._worker.motion_ready.connect(self._on_motion_ready)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_upload_complete(self, result):
        self.progress_bar.setValue(10)
        self.status_label.setText("Video uploaded, processing...")

    def _on_job_status(self, status, progress):
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"Status: {status}")

    def _on_motion_ready(self, motion_id, motion_name):
        self.upload_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Motion ready: {motion_name} (ID: {motion_id})")

        self._pending_motion_id = motion_id
        self._pending_motion_name = motion_name
        self._pending_character_id = "cXi2eAP19XwQ"  # Default character

        self.preview_info.setText(f"Motion: {motion_name}\nID: {motion_id}")
        self.preview_group.setVisible(True)

        # Start loading animated preview
        self.preview_player.load_preview(
            self._auth.get_domain(),
            self._auth.get_api_key(),
            self._pending_character_id,
            motion_id,
        )

    def _on_error(self, error_msg):
        self.upload_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_msg}")

    def _on_preview_error(self, error_msg):
        logger.error("Preview error: %s", error_msg)
        self.status_label.setText(f"Preview failed: {error_msg}")

    def _on_open_browser(self):
        if self._pending_motion_id:
            url = maya_utils.build_web_viewer_url(
                self._auth.get_domain(),
                self._pending_character_id,
                self._pending_motion_id,
            )
            webbrowser.open(url)

    def _on_download(self):
        if not self._pending_motion_id:
            return

        self.download_btn.setEnabled(False)
        self.status_label.setText("Downloading motion...")

        self._download_worker = DownloadAndImportWorker(
            self._auth.get_domain(),
            self._auth.get_api_key(),
            self._pending_character_id,
            self._pending_motion_id,
        )
        self._download_worker.download_finished.connect(self._on_download_complete)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_download_complete(self, result):
        self.download_btn.setEnabled(True)

        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                motion_id = self._pending_motion_id
                maya.utils.executeDeferred(self._do_import, file_path, motion_id)
        else:
            self.status_label.setText(f"Download failed: {result.message}")

    def _do_import(self, file_path, motion_id):
        result = maya_motion.import_fbx_to_maya(file_path, motion_id)
        if result.success:
            self.status_label.setText("Motion imported successfully!")
            self.preview_player.clear()
            self.preview_group.setVisible(False)
            self._pending_motion_id = ""
            self.motion_imported.emit()
        else:
            self.status_label.setText(f"Import failed: {result.message}")

    def _on_download_error(self, error_msg):
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"Download error: {error_msg}")

    def _on_cancel_preview(self):
        self.preview_player.clear()
        self.preview_group.setVisible(False)
        self._pending_motion_id = ""
        self.status_label.setText("Cancelled")
