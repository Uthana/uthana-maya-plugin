"""Bake motion widget for exporting animation and uploading to Uthana."""

import maya.cmds as cmds

from uthana import maya_motion, maya_utils
from uthana.core.types import BakeAndUploadRequest
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection


class BakeWidget(CollapsibleSection):
    """Export selected joint animation -> upload -> re-import."""

    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Bake Motion", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # Character ID
        layout.addWidget(QtWidgets.QLabel("Character ID:"))
        self.character_id_input = QtWidgets.QLineEdit()
        self.character_id_input.setText("cXi2eAP19XwQ")
        layout.addWidget(self.character_id_input)

        # Frame range
        self.frame_range_cb = QtWidgets.QCheckBox("Use Playback Frame Range")
        self.frame_range_cb.setChecked(True)
        self.frame_range_cb.toggled.connect(self._update_frame_info)
        layout.addWidget(self.frame_range_cb)

        self.frame_info_label = QtWidgets.QLabel("")
        self.frame_info_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self.frame_info_label)

        # Selected joint info
        self.joint_info_label = QtWidgets.QLabel("Select a joint hierarchy to bake")
        layout.addWidget(self.joint_info_label)

        # Refresh selection button
        self.refresh_selection_btn = QtWidgets.QPushButton("Refresh Selection")
        self.refresh_selection_btn.clicked.connect(self._update_selection_info)
        layout.addWidget(self.refresh_selection_btn)

        # Bake button
        self.bake_btn = QtWidgets.QPushButton("Bake")
        self.bake_btn.setMinimumHeight(36)
        self.bake_btn.clicked.connect(self._on_bake)
        layout.addWidget(self.bake_btn)

        # Result
        self.result_label = QtWidgets.QLabel("")
        layout.addWidget(self.result_label)

        self._update_frame_info()

    def _update_frame_info(self):
        if self.frame_range_cb.isChecked():
            try:
                start, end = maya_utils.get_frame_range()
                self.frame_info_label.setText(f"Frame Range: {start}-{end}")
            except Exception:
                self.frame_info_label.setText("Frame Range: N/A")
        else:
            self.frame_info_label.setText("Full animation")

    def _update_selection_info(self):
        try:
            selected = cmds.ls(selection=True, type="joint")
            if selected:
                root = maya_utils.get_root_joint(selected[0])
                self.joint_info_label.setText(f"Selected: {root}")
            else:
                self.joint_info_label.setText("No joints selected")
        except Exception:
            self.joint_info_label.setText("Select a joint hierarchy to bake")

    def _on_bake(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        character_id = self.character_id_input.text().strip()

        if not api_key:
            self.result_label.setText("API Key is required")
            return
        if not character_id:
            self.result_label.setText("Character ID is required")
            return

        # Check selection
        try:
            selected = cmds.ls(selection=True, type="joint")
            if not selected:
                self.result_label.setText("Select joints to bake")
                return
        except Exception:
            self.result_label.setText("Invalid Maya scene")
            return

        self.bake_btn.setEnabled(False)
        self.result_label.setText("Baking motion...")

        request = BakeAndUploadRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            use_frame_range=self.frame_range_cb.isChecked(),
        )

        # Run bake on main thread since it uses maya.cmds
        try:
            result = maya_motion.bake_and_upload_motion(request)
            self.bake_btn.setEnabled(True)

            if result.success:
                motion_id = result.data.get("motion_id", "") if result.data else ""
                self.result_label.setText(f"Baked! Motion ID: {motion_id}")
                self.motion_imported.emit()
            else:
                self.result_label.setText(f"Bake failed: {result.message}")
        except Exception as e:
            self.bake_btn.setEnabled(True)
            self.result_label.setText(f"Error: {str(e)}")
