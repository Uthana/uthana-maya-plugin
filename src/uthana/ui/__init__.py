"""Uthana Maya Plugin UI Module.

PySide2/PySide6 compatibility shim and UI component exports.
Maya 2022-2024 ships PySide2 (Qt5), Maya 2025+ ships PySide6 (Qt6).
"""

# Re-exports for use by other modules (e.g. from uthana.ui import QtWidgets)
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import QThread, QTimer, Signal, Slot
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import QThread, QTimer, Signal, Slot
    from shiboken2 import wrapInstance
