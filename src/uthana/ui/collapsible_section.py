"""Collapsible section widget for the Uthana Maya plugin.

Provides a QGroupBox-based collapsible section that mirrors
Blender's DEFAULT_CLOSED sub-panels.
"""

from uthana.ui import QtWidgets


class CollapsibleSection(QtWidgets.QWidget):
    """A collapsible section with a header button and hideable content area."""

    def __init__(self, title, parent=None, collapsed=False):
        super().__init__(parent)

        self._is_collapsed = collapsed

        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header button
        self._toggle_btn = QtWidgets.QPushButton(self._make_title(title, collapsed))
        self._toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 6px; "
            "background-color: #3a3a3a; border: 1px solid #555; border-radius: 3px; }"
            "QPushButton:hover { background-color: #4a4a4a; }"
        )
        self._toggle_btn.clicked.connect(self._on_toggle)
        self._title = title
        main_layout.addWidget(self._toggle_btn)

        # Content area
        self._content_widget = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.addWidget(self._content_widget)

        self._content_widget.setVisible(not collapsed)

    def _make_title(self, title, collapsed):
        arrow = "\u25b6" if collapsed else "\u25bc"
        return f" {arrow}  {title}"

    def _on_toggle(self):
        self._is_collapsed = not self._is_collapsed
        self._content_widget.setVisible(not self._is_collapsed)
        self._toggle_btn.setText(self._make_title(self._title, self._is_collapsed))

    def content_layout(self):
        """Get the layout to add child widgets to."""
        return self._content_layout

    def add_widget(self, widget):
        """Convenience: add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Convenience: add a layout to the content area."""
        self._content_layout.addLayout(layout)
