"""Text-to-Motion widget for generating motion from text prompts."""

import webbrowser

import maya.utils

from uthana import maya_motion, maya_utils
from uthana.core import client
from uthana.core.logger import logger
from uthana.core.types import MotionRequest
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.preview_widget import PreviewWidget
from uthana.ui.workers import ApiWorker, DownloadAndImportWorker


class TextToMotionWidget(CollapsibleSection):
    """Prompt input, generate, preview, and download motion."""

    # Signal emitted when a motion is imported (for other widgets to refresh)
    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Text to Motion", parent=parent, collapsed=False)
        self._auth = auth_widget

        layout = self.content_layout()

        # Prompt
        layout.addWidget(QtWidgets.QLabel("Prompt:"))
        self.prompt_input = QtWidgets.QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Describe the motion (e.g., 'A person walking forward')"
        )
        self.prompt_input.setMaximumHeight(80)
        self.prompt_input.setPlainText("A person ")
        layout.addWidget(self.prompt_input)

        # Character ID
        layout.addWidget(QtWidgets.QLabel("Character ID:"))
        self.character_id_input = QtWidgets.QLineEdit()
        self.character_id_input.setText("cXi2eAP19XwQ")
        layout.addWidget(self.character_id_input)

        # Generate button
        self.generate_btn = QtWidgets.QPushButton("Generate")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)

        # Result label
        self.result_label = QtWidgets.QLabel("")
        layout.addWidget(self.result_label)

        # Preview section (initially hidden)
        self.preview_group = QtWidgets.QGroupBox("Motion Preview")
        preview_layout = QtWidgets.QVBoxLayout(self.preview_group)

        self.preview_info = QtWidgets.QLabel("")
        preview_layout.addWidget(self.preview_info)

        # Animated preview player
        self.preview_player = PreviewWidget()
        self.preview_player.preview_error.connect(self._on_preview_error)
        preview_layout.addWidget(self.preview_player)

        # Warning
        self.warning_label = QtWidgets.QLabel("Downloading will charge your account")
        self.warning_label.setStyleSheet("color: #ffaa00;")
        preview_layout.addWidget(self.warning_label)

        # Browser preview button
        self.browser_btn = QtWidgets.QPushButton("Preview full animation in browser")
        self.browser_btn.setMinimumHeight(40)
        self.browser_btn.clicked.connect(self._on_open_browser)
        preview_layout.addWidget(self.browser_btn)

        # Download button
        self.download_btn = QtWidgets.QPushButton("Download & import (uses quota)")
        self.download_btn.setMinimumHeight(32)
        self.download_btn.clicked.connect(self._on_download)
        preview_layout.addWidget(self.download_btn)

        # Cancel button
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        preview_layout.addWidget(self.cancel_btn)

        layout.addWidget(self.preview_group)
        self.preview_group.setVisible(False)

        # State
        self._pending_motion_id = ""
        self._pending_motion_name = ""
        self._pending_character_id = ""
        self._worker = None
        self._download_worker = None

    def _on_generate(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        prompt = self.prompt_input.toPlainText().strip()
        character_id = self.character_id_input.text().strip()

        if not api_key:
            self.result_label.setText("API Key is required")
            return
        if not prompt:
            self.result_label.setText("Prompt is required")
            return

        self.generate_btn.setEnabled(False)
        self.result_label.setText("Generating motion...")

        request = MotionRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            prompt=prompt,
        )

        self._worker = ApiWorker(client.create_text_to_motion, request)
        self._worker.finished.connect(self._on_generate_complete)
        self._worker.error.connect(self._on_generate_error)
        self._worker.start()

    def _on_generate_complete(self, result):
        self.generate_btn.setEnabled(True)

        if result.success:
            motion_id = result.data.get("motion_id")
            motion_data = result.data.get("motion", {})
            motion_name = motion_data.get("name", "Generated Motion")

            self._pending_motion_id = motion_id
            self._pending_motion_name = motion_name
            self._pending_character_id = self.character_id_input.text().strip()

            self.result_label.setText(f"Motion created: {motion_name} (ID: {motion_id})")
            self.preview_info.setText(f"Motion: {motion_name}\nID: {motion_id}")
            self.preview_group.setVisible(True)

            # Start loading animated preview
            self.preview_player.load_preview(
                self._auth.get_domain(),
                self._auth.get_api_key(),
                self._pending_character_id,
                motion_id,
            )
        else:
            self.result_label.setText(f"Failed: {result.message}")

    def _on_generate_error(self, error_msg):
        self.generate_btn.setEnabled(True)
        self.result_label.setText(f"Error: {error_msg}")

    def _on_preview_error(self, error_msg):
        logger.error("Preview error: %s", error_msg)
        self.result_label.setText(f"Preview failed: {error_msg}")

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
        self.result_label.setText("Downloading motion...")

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
                # Import on main thread
                motion_id = self._pending_motion_id
                maya.utils.executeDeferred(self._do_import, file_path, motion_id)
        else:
            self.result_label.setText(f"Download failed: {result.message}")

    def _do_import(self, file_path, motion_id):
        result = maya_motion.import_fbx_to_maya(file_path, motion_id)
        if result.success:
            self.result_label.setText("Motion imported successfully!")
            self.preview_player.clear()
            self.preview_group.setVisible(False)
            self._pending_motion_id = ""
            self._pending_motion_name = ""
            self.motion_imported.emit()
        else:
            self.result_label.setText(f"Import failed: {result.message}")

    def _on_download_error(self, error_msg):
        self.download_btn.setEnabled(True)
        self.result_label.setText(f"Download error: {error_msg}")

    def _on_cancel(self):
        self.preview_player.clear()
        self.preview_group.setVisible(False)
        self._pending_motion_id = ""
        self._pending_motion_name = ""
        self.result_label.setText("Cancelled")
