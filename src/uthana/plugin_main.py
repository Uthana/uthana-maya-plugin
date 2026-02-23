"""Uthana Maya Plugin - UI lifecycle management.

Manages the dockable workspace control for the Uthana plugin.
"""

import maya.cmds as cmds

_ui_instance = None


def show_ui():
    """Show or create the Uthana dockable UI."""
    global _ui_instance

    from uthana.ui.main_window import UthanaMainWindow

    control_name = UthanaMainWindow.UI_NAME + "WorkspaceControl"

    # Close existing if it exists
    if cmds.workspaceControl(control_name, exists=True):
        cmds.deleteUI(control_name, control=True)

    _ui_instance = UthanaMainWindow()
    _ui_instance.show(dockable=True, area="right", floating=False)


def close_ui():
    """Close the Uthana UI."""
    global _ui_instance

    from uthana.ui.main_window import UthanaMainWindow

    control_name = UthanaMainWindow.UI_NAME + "WorkspaceControl"
    if cmds.workspaceControl(control_name, exists=True):
        cmds.deleteUI(control_name, control=True)
    _ui_instance = None
