"""Load Motion widget for importing a motion by ID."""

import maya.utils

from uthana import maya_motion
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.workers import DownloadAndImportWorker


class LoadMotionWidget(CollapsibleSection):
    """Motion ID + character ID fields, load button."""

    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Load Motion", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # Motion ID
        layout.addWidget(QtWidgets.QLabel("Motion ID:"))
        self.motion_id_input = QtWidgets.QLineEdit()
        self.motion_id_input.setPlaceholderText("Enter motion ID to load")
        layout.addWidget(self.motion_id_input)

        # Character ID
        layout.addWidget(QtWidgets.QLabel("Character ID:"))
        self.character_id_input = QtWidgets.QLineEdit()
        self.character_id_input.setText("cXi2eAP19XwQ")
        layout.addWidget(self.character_id_input)

        # Load button
        self.load_btn = QtWidgets.QPushButton("Load Motion")
        self.load_btn.setMinimumHeight(36)
        self.load_btn.clicked.connect(self._on_load)
        layout.addWidget(self.load_btn)

        # Result
        self.result_label = QtWidgets.QLabel("")
        layout.addWidget(self.result_label)

        self._worker = None

    def _on_load(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        motion_id = self.motion_id_input.text().strip()
        character_id = self.character_id_input.text().strip()

        if not api_key:
            self.result_label.setText("API Key is required")
            return
        if not motion_id:
            self.result_label.setText("Motion ID is required")
            return
        if not character_id:
            self.result_label.setText("Character ID is required")
            return

        self.load_btn.setEnabled(False)
        self.result_label.setText("Downloading...")

        self._worker = DownloadAndImportWorker(domain, api_key, character_id, motion_id)
        self._worker.download_finished.connect(lambda r: self._on_download_complete(r, motion_id))
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_download_complete(self, result, motion_id):
        self.load_btn.setEnabled(True)
        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                maya.utils.executeDeferred(self._do_import, file_path, motion_id)
        else:
            self.result_label.setText(f"Download failed: {result.message}")

    def _do_import(self, file_path, motion_id):
        result = maya_motion.import_fbx_to_maya(file_path, motion_id)
        if result.success:
            self.result_label.setText(f"Motion loaded: {motion_id}")
            self.motion_imported.emit()
        else:
            self.result_label.setText(f"Import failed: {result.message}")

    def _on_error(self, error_msg):
        self.load_btn.setEnabled(True)
        self.result_label.setText(f"Error: {error_msg}")
