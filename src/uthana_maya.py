"""Uthana Maya Plugin - entry point loaded by Maya's Plug-in Manager.

Installation:
    1. Copy this file AND the 'uthana/' directory to your Maya plug-ins folder
       (e.g. ~/Documents/maya/<version>/plug-ins/)
    2. In Maya: Windows > Settings/Preferences > Plug-in Manager
    3. Find 'uthana_maya.py' and check 'Loaded' (and 'Auto load' if desired)
"""

import sys

import maya.api.OpenMaya as om2
import maya.cmds as cmds

# ── Maya API 2.0 ─────────────────────────────────────────────────────
maya_useNewAPI = True

_PLUGIN_NAME = "Uthana"
_PLUGIN_VERSION = "1.0.0"
_VENDOR = "Uthana, Inc."


class UthanaUICmd(om2.MPxCommand):
    """MEL command to open the Uthana UI."""

    kPluginCmdName = "uthanaUI"

    @staticmethod
    def creator():
        return UthanaUICmd()

    def doIt(self, args):
        from uthana.plugin_main import show_ui

        show_ui()


def initializePlugin(mobject):
    """Called by Maya when the plugin is loaded."""
    mplugin = om2.MFnPlugin(mobject, _VENDOR, _PLUGIN_VERSION)

    # Add the plugin directory to sys.path so the 'uthana' package is importable.
    # MFnPlugin.loadPath() reliably returns the directory Maya loaded this file from.
    plugin_dir = mplugin.loadPath()
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)

    # Ensure FBX plugin is available
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        try:
            cmds.loadPlugin("fbxmaya")
        except RuntimeError:
            om2.MGlobal.displayWarning(
                "Uthana: FBX plugin not available. FBX import/export may not work."
            )

    # Setup logger
    from uthana.core.logger import setup_logger

    setup_logger()

    # Ensure cache directory
    from uthana.core.config import ensure_cache_directory

    ensure_cache_directory()

    # Set client version for API headers (User-Agent, X-Uthana-Client)
    from uthana.core.auth import set_client_version

    set_client_version(_PLUGIN_VERSION)

    # Send initialization telemetry (best-effort, after config may be loaded)
    try:
        from uthana.core import config
        from uthana.core.telemetry import log_initialized_event

        loaded_config = config.load_config()
        if loaded_config.auth.domain and loaded_config.auth.api_key:
            log_initialized_event(
                domain=loaded_config.auth.domain,
                api_key=loaded_config.auth.api_key,
                version=_PLUGIN_VERSION,
            )
    except Exception:
        pass

    # Register the UI command
    try:
        mplugin.registerCommand(UthanaUICmd.kPluginCmdName, UthanaUICmd.creator)
    except RuntimeError as e:
        om2.MGlobal.displayError(f"Uthana: Failed to register command: {e}")

    # Create shelf button
    _create_shelf_button()

    om2.MGlobal.displayInfo("Uthana plugin loaded successfully")


def uninitializePlugin(mobject):
    """Called by Maya when the plugin is unloaded."""
    mplugin = om2.MFnPlugin(mobject)

    # Close UI if open
    try:
        from uthana.plugin_main import close_ui

        close_ui()
    except Exception:
        pass

    # Deregister command
    try:
        mplugin.deregisterCommand(UthanaUICmd.kPluginCmdName)
    except RuntimeError:
        pass

    # Remove shelf button
    _remove_shelf_button()

    om2.MGlobal.displayInfo("Uthana plugin unloaded")


def _create_shelf_button():
    """Add Uthana button to a shelf."""
    try:
        shelf_name = "Uthana"
        top_shelf = "ShelfLayout"

        if not cmds.shelfLayout(shelf_name, exists=True):
            cmds.shelfLayout(shelf_name, parent=top_shelf)

        # Check if button already exists
        existing = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
        for child in existing:
            if cmds.shelfButton(child, query=True, exists=True):
                label = cmds.shelfButton(child, query=True, label=True)
                if label == "Uthana":
                    return  # Already exists

        cmds.shelfButton(
            parent=shelf_name,
            label="Uthana",
            command="import maya.cmds; maya.cmds.uthanaUI()",
            image="pythonFamily.png",
            annotation="Open Uthana AI Motion Generation",
            sourceType="python",
        )
    except Exception:
        # Shelf creation can fail in batch mode or headless
        pass


def _remove_shelf_button():
    """Remove shelf button on unload."""
    try:
        shelf_name = "Uthana"
        if cmds.shelfLayout(shelf_name, exists=True):
            existing = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
            for child in existing:
                if cmds.shelfButton(child, query=True, exists=True):
                    cmds.deleteUI(child)
    except Exception:
        pass
