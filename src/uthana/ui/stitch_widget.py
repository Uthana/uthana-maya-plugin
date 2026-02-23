"""Stitch motions widget with two modes: joint-based and ID-based."""

from uthana import maya_motion, maya_utils
from uthana.core.types import StitchMotionIdsRequest, StitchMotionsRequest
from uthana.ui import QtCore, QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection


class StitchWidget(CollapsibleSection):
    """Two-tab widget for stitching motions: by joints or by motion IDs."""

    motion_imported = QtCore.Signal()

    def __init__(self, auth_widget, parent=None):
        super().__init__("Stitch Motions", parent=parent, collapsed=True)
        self._auth = auth_widget

        layout = self.content_layout()

        # Tab widget
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: Stitch Joints
        self.joints_tab = QtWidgets.QWidget()
        self._build_joints_tab()
        self.tabs.addTab(self.joints_tab, "By Joints")

        # Tab 2: Stitch Motion IDs
        self.ids_tab = QtWidgets.QWidget()
        self._build_ids_tab()
        self.tabs.addTab(self.ids_tab, "By Motion IDs")

        layout.addWidget(self.tabs)

    def _build_joints_tab(self):
        layout = QtWidgets.QVBoxLayout(self.joints_tab)

        # Character ID
        layout.addWidget(QtWidgets.QLabel("Character ID:"))
        self.j_character_id = QtWidgets.QLineEdit("cXi2eAP19XwQ")
        layout.addWidget(self.j_character_id)

        # Duration
        layout.addWidget(QtWidgets.QLabel("Transition Duration (seconds):"))
        self.j_duration = QtWidgets.QDoubleSpinBox()
        self.j_duration.setRange(0.1, 10.0)
        self.j_duration.setValue(1.0)
        self.j_duration.setSingleStep(0.1)
        layout.addWidget(self.j_duration)

        # Frame range
        self.j_frame_range_cb = QtWidgets.QCheckBox("Use Playback Frame Range")
        self.j_frame_range_cb.setChecked(False)
        layout.addWidget(self.j_frame_range_cb)

        # Selection info
        self.j_selection_label = QtWidgets.QLabel(
            "Select 2 joint roots (first=leading, second=trailing)"
        )
        layout.addWidget(self.j_selection_label)

        self.j_refresh_btn = QtWidgets.QPushButton("Refresh Selection")
        self.j_refresh_btn.clicked.connect(self._update_joint_selection)
        layout.addWidget(self.j_refresh_btn)

        # Stitch button
        self.j_stitch_btn = QtWidgets.QPushButton("Stitch armatures")
        self.j_stitch_btn.setMinimumHeight(36)
        self.j_stitch_btn.clicked.connect(self._on_stitch_joints)
        layout.addWidget(self.j_stitch_btn)

        self.j_result_label = QtWidgets.QLabel("")
        layout.addWidget(self.j_result_label)

    def _build_ids_tab(self):
        layout = QtWidgets.QVBoxLayout(self.ids_tab)

        # Character ID
        layout.addWidget(QtWidgets.QLabel("Character ID:"))
        self.i_character_id = QtWidgets.QLineEdit("cXi2eAP19XwQ")
        layout.addWidget(self.i_character_id)

        # Leading Motion ID
        layout.addWidget(QtWidgets.QLabel("Leading Motion ID:"))
        leading_row = QtWidgets.QHBoxLayout()
        self.i_leading_id = QtWidgets.QLineEdit()
        self.i_leading_id.setPlaceholderText("Motion ID for leading animation")
        leading_row.addWidget(self.i_leading_id)
        self.i_paste_leading = QtWidgets.QPushButton("Paste")
        self.i_paste_leading.setFixedWidth(50)
        self.i_paste_leading.clicked.connect(lambda: self._paste_to(self.i_leading_id))
        leading_row.addWidget(self.i_paste_leading)
        layout.addLayout(leading_row)

        # Trailing Motion ID
        layout.addWidget(QtWidgets.QLabel("Trailing Motion ID:"))
        trailing_row = QtWidgets.QHBoxLayout()
        self.i_trailing_id = QtWidgets.QLineEdit()
        self.i_trailing_id.setPlaceholderText("Motion ID for trailing animation")
        trailing_row.addWidget(self.i_trailing_id)
        self.i_paste_trailing = QtWidgets.QPushButton("Paste")
        self.i_paste_trailing.setFixedWidth(50)
        self.i_paste_trailing.clicked.connect(lambda: self._paste_to(self.i_trailing_id))
        trailing_row.addWidget(self.i_paste_trailing)
        layout.addLayout(trailing_row)

        # Duration
        layout.addWidget(QtWidgets.QLabel("Transition Duration (seconds):"))
        self.i_duration = QtWidgets.QDoubleSpinBox()
        self.i_duration.setRange(0.1, 10.0)
        self.i_duration.setValue(1.0)
        self.i_duration.setSingleStep(0.1)
        layout.addWidget(self.i_duration)

        # Status
        self.i_status_label = QtWidgets.QLabel("")
        layout.addWidget(self.i_status_label)

        # Stitch button
        self.i_stitch_btn = QtWidgets.QPushButton("Stitch Motion IDs")
        self.i_stitch_btn.setMinimumHeight(36)
        self.i_stitch_btn.clicked.connect(self._on_stitch_ids)
        layout.addWidget(self.i_stitch_btn)

        self.i_result_label = QtWidgets.QLabel("")
        layout.addWidget(self.i_result_label)

    def _paste_to(self, line_edit):
        clipboard = QtWidgets.QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            line_edit.setText(text)

    def _update_joint_selection(self):
        try:
            roots = maya_utils.get_selected_joints()
            if len(roots) >= 2:
                self.j_selection_label.setText(
                    f"Leading: {roots[0]}\nTrailing: {roots[1]}\nReady to stitch!"
                )
            elif len(roots) == 1:
                self.j_selection_label.setText(f"Selected: {roots[0]}\nSelect one more joint root")
            else:
                self.j_selection_label.setText("Select 2 joint roots")
        except Exception:
            self.j_selection_label.setText("Select 2 joint roots")

    def _on_stitch_joints(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        character_id = self.j_character_id.text().strip()

        if not api_key:
            self.j_result_label.setText("API Key is required")
            return

        request = StitchMotionsRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            duration=self.j_duration.value(),
            use_frame_range=self.j_frame_range_cb.isChecked(),
        )

        self.j_stitch_btn.setEnabled(False)
        self.j_result_label.setText("Stitching motions...")

        try:
            result = maya_motion.stitch_motions(request)
            self.j_stitch_btn.setEnabled(True)

            if result.success:
                motion_id = result.data.get("stitched_motion_id", "") if result.data else ""
                self.j_result_label.setText(f"Stitched! Motion ID: {motion_id}")
                self.motion_imported.emit()
            else:
                self.j_result_label.setText(f"Failed: {result.message}")
        except Exception as e:
            self.j_stitch_btn.setEnabled(True)
            self.j_result_label.setText(f"Error: {str(e)}")

    def _on_stitch_ids(self):
        api_key = self._auth.get_api_key()
        domain = self._auth.get_domain()
        character_id = self.i_character_id.text().strip()
        leading_id = self.i_leading_id.text().strip()
        trailing_id = self.i_trailing_id.text().strip()

        if not api_key:
            self.i_result_label.setText("API Key is required")
            return
        if not leading_id or not trailing_id:
            self.i_result_label.setText("Both Motion IDs are required")
            return

        request = StitchMotionIdsRequest(
            domain=domain,
            api_key=api_key,
            character_id=character_id,
            leading_motion_id=leading_id,
            trailing_motion_id=trailing_id,
            duration=self.i_duration.value(),
        )

        self.i_stitch_btn.setEnabled(False)
        self.i_result_label.setText("Stitching motion IDs...")

        try:
            result = maya_motion.stitch_motion_ids(request)
            self.i_stitch_btn.setEnabled(True)

            if result.success:
                motion_id = result.data.get("stitched_motion_id", "") if result.data else ""
                self.i_result_label.setText(f"Stitched! Motion ID: {motion_id}")
                self.motion_imported.emit()
            else:
                self.i_result_label.setText(f"Failed: {result.message}")
        except Exception as e:
            self.i_stitch_btn.setEnabled(True)
            self.i_result_label.setText(f"Error: {str(e)}")
