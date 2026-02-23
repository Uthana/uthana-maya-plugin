"""Uthana Main Window - dockable panel assembling all plugin widgets."""

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from uthana.core import config
from uthana.core.logger import logger
from uthana.ui import QtWidgets
from uthana.ui.auth_widget import AuthWidget
from uthana.ui.bake_widget import BakeWidget
from uthana.ui.character_browser_widget import CharacterBrowserWidget
from uthana.ui.character_upload_widget import CharacterUploadWidget
from uthana.ui.load_motion_widget import LoadMotionWidget
from uthana.ui.motion_browser_widget import MotionBrowserWidget
from uthana.ui.stitch_widget import StitchWidget
from uthana.ui.text_to_motion_widget import TextToMotionWidget
from uthana.ui.video_to_motion_widget import VideoToMotionWidget


class UthanaMainWindow(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    """Dockable main panel for the Uthana Maya plugin."""

    UI_NAME = "UthanaPluginWindow"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(self.UI_NAME)
        self.setWindowTitle("Uthana")
        self.setMinimumWidth(320)

        # Root layout
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area so the panel works at any height
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # -- Widgets --
        self.auth_widget = AuthWidget(parent=container)
        layout.addWidget(self.auth_widget)

        self.text_to_motion = TextToMotionWidget(self.auth_widget, parent=container)
        layout.addWidget(self.text_to_motion)

        self.video_to_motion = VideoToMotionWidget(self.auth_widget, parent=container)
        layout.addWidget(self.video_to_motion)

        self.motion_browser = MotionBrowserWidget(self.auth_widget, parent=container)
        layout.addWidget(self.motion_browser)

        self.character_browser = CharacterBrowserWidget(self.auth_widget, parent=container)
        layout.addWidget(self.character_browser)

        self.character_upload = CharacterUploadWidget(self.auth_widget, parent=container)
        layout.addWidget(self.character_upload)

        self.bake_widget = BakeWidget(self.auth_widget, parent=container)
        layout.addWidget(self.bake_widget)

        self.stitch_widget = StitchWidget(self.auth_widget, parent=container)
        layout.addWidget(self.stitch_widget)

        self.load_motion = LoadMotionWidget(self.auth_widget, parent=container)
        layout.addWidget(self.load_motion)

        layout.addStretch()

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        # -- Cross-widget signals --

        # When any widget imports a motion, refresh the motion browser list
        self.text_to_motion.motion_imported.connect(self._refresh_motions)
        self.video_to_motion.motion_imported.connect(self._refresh_motions)
        self.load_motion.motion_imported.connect(self._refresh_motions)
        self.bake_widget.motion_imported.connect(self._refresh_motions)
        self.stitch_widget.motion_imported.connect(self._refresh_motions)
        self.motion_browser.motion_imported.connect(self._refresh_motions)

        # When a character is uploaded, refresh the character browser
        self.character_upload.character_uploaded.connect(self._refresh_characters)

        # When the character browser emits "Use for Generation", set the character ID
        # on the text-to-motion widget
        self.character_browser.character_selected.connect(self._on_character_selected)

    def _refresh_motions(self):
        """Trigger a motion list refresh if the auth widget has an API key."""
        if self.auth_widget.get_api_key():
            self.motion_browser._on_refresh()

    def _refresh_characters(self):
        """Trigger a character list refresh if the auth widget has an API key."""
        if self.auth_widget.get_api_key():
            self.character_browser._on_refresh()

    def _on_character_selected(self, character_id):
        """Set the selected character ID on generation widgets."""
        self.text_to_motion.character_id_input.setText(character_id)

    def dockCloseEventTriggered(self):
        """Called when the dockable workspace control is closed. Auto-save config."""
        try:
            cfg = config.load_config()
            cfg.auth.api_key = self.auth_widget.get_api_key()
            cfg.auth.domain = self.auth_widget.get_domain()
            config.save_config(cfg)
            logger.info("Config auto-saved on close")
        except Exception as e:
            logger.warning("Failed to auto-save config: %s", e)
        super().dockCloseEventTriggered()
