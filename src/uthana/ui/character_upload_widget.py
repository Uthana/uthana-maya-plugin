"""Character upload widget for uploading character files with auto-rigging."""

import maya.utils

from uthana import maya_motion
from uthana.core import client
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.workers import CharacterUploadWorker


class CharacterUploadWidget(CollapsibleSection):
    """Character file picker, name, auto-rig toggle, upload with progress."""

    character_uploaded = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Character Upload", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # File picker
        file_layout = QtWidgets.QHBoxLayout()
        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setPlaceholderText("Select character file (.fbx, .glb, .gltf)")
        file_layout.addWidget(self.file_path_input)

        self.browse_btn = QtWidgets.QPushButton("Browse")
        self.browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # Name
        layout.addWidget(QtWidgets.QLabel("Character Name:"))
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Name for the character")
        layout.addWidget(self.name_input)

        # Options
        self.auto_rig_cb = QtWidgets.QCheckBox("Auto-Rig")
        self.auto_rig_cb.setChecked(True)
        layout.addWidget(self.auto_rig_cb)

        self.auto_import_cb = QtWidgets.QCheckBox("Import to Scene after upload")
        self.auto_import_cb.setChecked(False)
        layout.addWidget(self.auto_import_cb)

        # Upload button
        self.upload_btn = QtWidgets.QPushButton("Upload Character")
        self.upload_btn.setMinimumHeight(36)
        self.upload_btn.clicked.connect(self._on_upload)
        layout.addWidget(self.upload_btn)

        # Status
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        self._worker = None

    def _on_browse(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Character File", "", "3D Files (*.fbx *.glb *.gltf);;All Files (*)"
        )
        if file_path:
            self.file_path_input.setText(file_path)

    def _on_upload(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        file_path = self.file_path_input.text().strip()
        name = self.name_input.text().strip() or "My Character"
        auto_rig = self.auto_rig_cb.isChecked()

        if not api_key:
            self.status_label.setText("API Key is required")
            return
        if not file_path:
            self.status_label.setText("Select a character file first")
            return

        self.upload_btn.setEnabled(False)
        self.status_label.setText("Uploading character...")

        self._worker = CharacterUploadWorker(api_key, domain, file_path, name, auto_rig)
        self._worker.finished.connect(self._on_upload_complete)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_upload_complete(self, result):
        self.upload_btn.setEnabled(True)

        if result.success:
            char_id = result.data.get("character_id")
            char_name = result.data.get("name", "Character")
            self.status_label.setText(f"Uploaded: {char_name} (ID: {char_id})")
            self.character_uploaded.emit()

            # Auto-import if requested
            if self.auto_import_cb.isChecked() and char_id:
                self._auto_import_character(char_id)
        else:
            self.status_label.setText(f"Upload failed: {result.message}")

    def _auto_import_character(self, character_id):
        """Download and import the uploaded character."""
        self.status_label.setText("Importing character...")

        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()

        result = client.download_character(api_key, domain, character_id, "fbx")
        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                maya.utils.executeDeferred(self._do_import, file_path)
        else:
            self.status_label.setText(f"Import failed: {result.message}")

    def _do_import(self, file_path):
        result = maya_motion.import_fbx_to_maya(file_path)
        if result.success:
            self.status_label.setText("Character imported!")
        else:
            self.status_label.setText(f"Import failed: {result.message}")

    def _on_error(self, error_msg):
        self.upload_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")
