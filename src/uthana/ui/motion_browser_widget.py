"""Motion browser widget for listing, managing, and importing motions."""

import maya.utils

from uthana import maya_motion
from uthana.core import client
from uthana.core.assets import AssetManager
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.workers import ApiWorker, DownloadAndImportWorker


class MotionBrowserWidget(CollapsibleSection):
    """QListWidget for motions with refresh, import, rename, delete, favorite, copy ID."""

    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Motions", parent=parent, collapsed=False)
        self._auth = auth_widget

        layout = self.content_layout()

        # List + actions row
        list_row = QtWidgets.QHBoxLayout()

        # Motion list
        self.motion_list = QtWidgets.QListWidget()
        self.motion_list.setMinimumHeight(150)
        self.motion_list.currentRowChanged.connect(self._on_selection_changed)
        list_row.addWidget(self.motion_list)

        # Action buttons column
        btn_col = QtWidgets.QVBoxLayout()

        self.refresh_btn = QtWidgets.QPushButton("R")
        self.refresh_btn.setToolTip("Refresh motions list")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.clicked.connect(self._on_refresh)
        btn_col.addWidget(self.refresh_btn)

        btn_col.addSpacing(8)

        self.import_btn = QtWidgets.QPushButton("I")
        self.import_btn.setToolTip("Import selected motion")
        self.import_btn.setFixedWidth(30)
        self.import_btn.clicked.connect(self._on_import)
        btn_col.addWidget(self.import_btn)

        self.fav_btn = QtWidgets.QPushButton("\u2605")
        self.fav_btn.setToolTip("Toggle favorite")
        self.fav_btn.setFixedWidth(30)
        self.fav_btn.clicked.connect(self._on_toggle_favorite)
        btn_col.addWidget(self.fav_btn)

        self.rename_btn = QtWidgets.QPushButton("N")
        self.rename_btn.setToolTip("Rename motion")
        self.rename_btn.setFixedWidth(30)
        self.rename_btn.clicked.connect(self._on_rename)
        btn_col.addWidget(self.rename_btn)

        btn_col.addSpacing(8)

        self.copy_btn = QtWidgets.QPushButton("C")
        self.copy_btn.setToolTip("Copy motion ID")
        self.copy_btn.setFixedWidth(30)
        self.copy_btn.clicked.connect(self._on_copy_id)
        btn_col.addWidget(self.copy_btn)

        self.delete_btn = QtWidgets.QPushButton("X")
        self.delete_btn.setToolTip("Delete motion")
        self.delete_btn.setFixedWidth(30)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_col.addWidget(self.delete_btn)

        btn_col.addStretch()
        list_row.addLayout(btn_col)
        layout.addLayout(list_row)

        # Selected motion info
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Status
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        self._worker = None
        self._download_worker = None

    def _get_selected_motion(self):
        """Get the currently selected motion data."""
        idx = self.motion_list.currentRow()
        manager = AssetManager.instance()
        motions = manager.get_motions()
        if 0 <= idx < len(motions):
            return motions[idx]
        return None

    def _on_selection_changed(self, idx):
        motion = self._get_selected_motion()
        if motion:
            fav = " \u2605" if motion.is_favorite else ""
            self.info_label.setText(f"ID: {motion.id}{fav}\nCreated: {motion.created}")
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
        self._worker = ApiWorker(manager.refresh_motions, api_key, domain, True)
        self._worker.finished.connect(self._on_refresh_complete)
        self._worker.error.connect(lambda e: self._on_refresh_error(e))
        self._worker.start()

    def _on_refresh_complete(self, result):
        self.refresh_btn.setEnabled(True)
        if result.success:
            self._sync_list()
            self.status_label.setText(f"Refreshed ({result.data.get('count', 0)} motions)")
        else:
            self.status_label.setText(f"Refresh failed: {result.message}")

    def _on_refresh_error(self, error_msg):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")

    def _sync_list(self):
        """Sync the QListWidget with cached motion data."""
        self.motion_list.clear()
        manager = AssetManager.instance()
        for motion in manager.get_motions():
            prefix = "\u2605 " if motion.is_favorite else ""
            date_str = f"  ({motion.created[:10]})" if motion.created else ""
            self.motion_list.addItem(f"{prefix}{motion.name}{date_str}")

    def _on_import(self):
        motion = self._get_selected_motion()
        if not motion:
            self.status_label.setText("No motion selected")
            return

        self.import_btn.setEnabled(False)
        self.status_label.setText(f"Downloading {motion.name}...")

        character_id = "cXi2eAP19XwQ"  # Default
        self._download_worker = DownloadAndImportWorker(
            self._auth.get_domain(),
            self._auth.get_api_key(),
            character_id,
            motion.id,
        )
        self._download_worker.download_finished.connect(
            lambda r: self._on_import_download_complete(r, motion.id)
        )
        self._download_worker.error.connect(self._on_import_error)
        self._download_worker.start()

    def _on_import_download_complete(self, result, motion_id):
        self.import_btn.setEnabled(True)
        if result.success:
            file_path = result.data.get("file_path")
            if file_path:
                maya.utils.executeDeferred(self._do_import, file_path, motion_id)
        else:
            self.status_label.setText(f"Download failed: {result.message}")

    def _do_import(self, file_path, motion_id):
        result = maya_motion.import_fbx_to_maya(file_path, motion_id)
        if result.success:
            self.status_label.setText("Motion imported!")
            self.motion_imported.emit()
        else:
            self.status_label.setText(f"Import failed: {result.message}")

    def _on_import_error(self, error_msg):
        self.import_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")

    def _on_toggle_favorite(self):
        motion = self._get_selected_motion()
        if not motion:
            return

        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        new_state = not motion.is_favorite

        self._worker = ApiWorker(client.set_motion_favorite, api_key, domain, motion.id, new_state)
        self._worker.finished.connect(lambda r: self._on_fav_complete(r, new_state))
        self._worker.start()

    def _on_fav_complete(self, result, new_state):
        if result.success:
            action = "added to" if new_state else "removed from"
            self.status_label.setText(f"Motion {action} favorites")
            # Refresh to update list
            self._on_refresh()

    def _on_rename(self):
        motion = self._get_selected_motion()
        if not motion:
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Motion", "New name:", text=motion.name
        )
        if ok and new_name.strip():
            api_key = self._auth.get_api_key()
            domain = self._auth.get_domain()
            self._worker = ApiWorker(
                client.rename_motion, api_key, domain, motion.id, new_name.strip()
            )
            self._worker.finished.connect(lambda r: self._on_rename_complete(r, new_name))
            self._worker.start()

    def _on_rename_complete(self, result, new_name):
        if result.success:
            self.status_label.setText(f"Renamed to '{new_name}'")
            self._on_refresh()
        else:
            self.status_label.setText(f"Rename failed: {result.message}")

    def _on_copy_id(self):
        motion = self._get_selected_motion()
        if not motion:
            return

        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(motion.id)
        self.status_label.setText(f"Copied: {motion.id}")

    def _on_delete(self):
        motion = self._get_selected_motion()
        if not motion:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Motion",
            f"Delete motion '{motion.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            api_key = self._auth.get_api_key()
            domain = self._auth.get_domain()
            self._worker = ApiWorker(client.delete_motion, api_key, domain, motion.id)
            self._worker.finished.connect(self._on_delete_complete)
            self._worker.start()

    def _on_delete_complete(self, result):
        if result.success:
            self.status_label.setText("Motion deleted")
            self._on_refresh()
        else:
            self.status_label.setText(f"Delete failed: {result.message}")
