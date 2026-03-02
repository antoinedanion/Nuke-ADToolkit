"""
ADCopyParameters Core Module

Version 1.0.1

Antoine Danion
"""

import ctypes
import logging
import sys

import nuke
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2.QtWidgets import QApplication
    from PySide2.QtCore import Qt


# ============================================================================
# LOGGING SETUP
# ============================================================================

class _DynamicStdoutHandler(logging.StreamHandler):
    """Always writes to the current sys.stdout, even if Nuke replaces it."""
    def emit(self, record):
        self.stream = sys.stdout
        super().emit(record)

# Create logger for this module
logger = logging.getLogger('ADCopyParameters')
logger.setLevel(logging.DEBUG)

# Only add handler if it doesn't exist (prevents duplicate logs on script reload)
if not logger.handlers:
    handler = _DynamicStdoutHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

IGNORED_KNOBS = [
    'xpos',
    'ypos',
    'selected',
]

def copy_parameters():

    RETURN = False

    modifiers = QApplication.keyboardModifiers()
    mouse_buttons = QApplication.mouseButtons()
    lmb = bool(mouse_buttons & Qt.LeftButton)
    enter = bool(ctypes.windll.user32.GetAsyncKeyState(0x0D) & 0x8000)
    if modifiers & Qt.AltModifier and (lmb or enter):
        node = nuke.thisNode()
        knob = nuke.thisKnob()
        if not node or not knob:
            RETURN = True
        if knob.name() in IGNORED_KNOBS:
            RETURN = True
        if hasattr(knob, 'isAnimated') and knob.isAnimated():
            RETURN = True
        if hasattr(knob, 'isReadOnly') and knob.isReadOnly():
            RETURN = True
        
        logger.debug(f"Alt+click on '{knob.name()}' of node '{node.name()}'")

        if RETURN:
            return
        
        value = knob.getValue()

        node_ids = nuke.tcl('selected_nodes').split()
        for node_id in node_ids:
            node_name = nuke.tcl(f'knob {node_id}.name')
            try:
                try:
                    float(value)
                    is_numeric = True
                except (ValueError, TypeError):
                    is_numeric = False

                if is_numeric:
                    nuke.tcl(f'knob {node_id}.{knob.name()} {value}')
                else:
                    nuke.tcl(f'knob {node_id}.{knob.name()} "{value}"')

                logger.info(f"Copied value '{value}' of knob '{knob.name()}' from node '{node.name()}' to node '{node_name}'")

            except Exception as e:
                logger.warning(f"Could not copy value '{value}' of knob '{knob.name()}' from node '{node.name()}' to node '{node_name}':\n{e}")