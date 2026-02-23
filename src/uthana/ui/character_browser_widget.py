"""Character browser widget for listing and importing characters."""

import maya.utils

from uthana import maya_motion
from uthana.core import client
from uthana.core.assets import AssetManager
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.workers import ApiWorker


class CharacterBrowserWidget(CollapsibleSection):
    """QListWidget for characters with refresh and import."""

    # Emitted when user clicks "Use for Generation" with the character ID
    character_selected = QtCore.Signal(str)

    def __init__(self, auth_widget, parent=None):
        super().__init__("Characters", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # List + actions row
        list_row = QtWidgets.QHBoxLayout()

        self.char_list = QtWidgets.QListWidget()
        self.char_list.setMinimumHeight(120)
        self.char_list.currentRowChanged.connect(self._on_selection_changed)
        list_row.addWidget(self.char_list)

        btn_col = QtWidgets.QVBoxLayout()

        self.refresh_btn = QtWidgets.QPushButton("R")
        self.refresh_btn.setToolTip("Refresh characters")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.clicked.connect(self._on_refresh)
        btn_col.addWidget(self.refresh_btn)

        btn_col.addSpacing(8)

        self.import_btn = QtWidgets.QPushButton("I")
        self.import_btn.setToolTip("Import character")
        self.import_btn.setFixedWidth(30)
        self.import_btn.clicked.connect(self._on_import)
        btn_col.addWidget(self.import_btn)

        btn_col.addStretch()
        list_row.addLayout(btn_col)
        layout.addLayout(list_row)

        # Info
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Use for generation button
        self.use_btn = QtWidgets.QPushButton("Use for generation")
        self.use_btn.clicked.connect(self._on_use_for_generation)
        layout.addWidget(self.use_btn)

        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        self._worker = None
        self._download_worker = None

    def _get_selected_character(self):
        idx = self.char_list.currentRow()
        manager = AssetManager.instance()
        characters = manager.get_characters()
        if 0 <= idx < len(characters):
            return characters[idx]
        return None

    def _on_selection_changed(self, idx):
        char = self._get_selected_character()
        if char:
            self.info_label.setText(f"ID: {char.id}\nCreated: {char.created}")
        else:
            self.info_label.setText("")

    def _on_refresh(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        if not api_key:
            self.status_label.setText("API Key is required")
            return

        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Refreshing...")

        manager = AssetManager.instance()
        self._worker = ApiWorker(manager.refresh_characters, api_key, domain, True)
        self._worker.finished.connect(self._on_refresh_complete)
        self._worker.error.connect(lambda e: self._on_error(e))
        self._worker.start()

    def _on_refresh_complete(self, result):
        self.refresh_btn.setEnabled(True)
        if result.success:
            self._sync_list()
            self.status_label.setText(f"Refreshed ({result.data.get('count', 0)} characters)")
        else:
            self.status_label.setText(f"Refresh failed: {result.message}")

    def _sync_list(self):
        self.char_list.clear()
        manager = AssetManager.instance()
        for char in manager.get_characters():
            date_str = f"  ({char.created[:10]})" if char.created else ""
            self.char_list.addItem(f"{char.name}{date_str}")

    def _on_import(self):
        char = self._get_selected_character()
        if not char:
            self.status_label.setText("No character selected")
            return

        self.import_btn.setEnabled(False)
        self.status_label.setText(f"Downloading {char.name}...")

        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()

        self._download_worker = ApiWorker(
            client.download_character, api_key, domain, char.id, "fbx"
        )
        self._download_worker.finished.connect(self._on_download_complete)
        self._download_worker.error.connect(self._on_error)
        self._download_worker.start()

    def _on_download_complete(self, result):
        self.import_btn.setEnabled(True)
        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                maya.utils.executeDeferred(self._do_import, file_path)
        else:
            self.status_label.setText(f"Download failed: {result.message}")

    def _do_import(self, file_path):
        result = maya_motion.import_fbx_to_maya(file_path)
        if result.success:
            self.status_label.setText("Character imported!")
        else:
            self.status_label.setText(f"Import failed: {result.message}")

    def _on_use_for_generation(self):
        char = self._get_selected_character()
        if char:
            self.character_selected.emit(char.id)
            self.status_label.setText(f"Using character: {char.name}")

    def _on_error(self, error_msg):
        self.refresh_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")
