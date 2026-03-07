"""
ADCopyParameters Core Module

Version 1.1.0

Antoine Danion
"""

import ctypes
import logging
import sys
import time

import nuke
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QObject, QEvent
except ImportError:
    from PySide2.QtWidgets import QApplication
    from PySide2.QtCore import Qt, QObject, QEvent


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
# ALT+LMB EVENT TRACKER
# ============================================================================

class _AltClickTracker(QObject):
    """
    Event filter installed on QApplication to catch Alt+LMB presses at the
    Qt level, before Nuke processes them.
    Stores the timestamp of the last Alt+LMB press so knobChanged (which fires
    after the release) can still detect it within a short window.
    """
    _WINDOW = 0.5  # seconds

    def __init__(self):
        super().__init__()
        self.alt = False
        self.lmb = False
        self._last_call = 0.0

    def test_validity(self):
        """Return True if Alt and LMB are currently pressed."""
        if self.alt and self.lmb:
            return True
        elif time.monotonic() - self._last_call < self._WINDOW:
            return True
        else:
            return False

    def store_time(self):
        self._last_call = time.monotonic()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Alt:
                self.alt = True
        if event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Alt:
                self.alt = False
        
        if self.alt:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.lmb = True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    self.lmb = False

        if self.alt and self.lmb:
            self.store_time()

        return False


# Install once; survive script reloads by storing on the nuke module
if not hasattr(nuke, '_ad_alt_click_tracker'):
    nuke._ad_alt_click_tracker = _AltClickTracker()
    QApplication.instance().installEventFilter(nuke._ad_alt_click_tracker)

_tracker = nuke._ad_alt_click_tracker


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

IGNORED_KNOBS = [
    'xpos',
    'ypos',
    'selected',
]

# Re-entrancy guard: setting a File_Knob via TCL triggers another knobChanged
# on the target node while Alt is still held, which would start a reverse copy.
_copying = False


def _is_knob_copyable(knob, check_animated=False):
    """Return True if the knob is eligible to be copied, False otherwise."""
    if knob.name() in IGNORED_KNOBS:
        logger.debug(f"Ignoring knob '{knob.name()}' as it's in the ignored list.")
        return False
    # File_Knob on Read nodes reports isAnimated() == True because the filename
    # pattern (e.g. file.%04d.exr) is frame-dependent, so we exempt File_Knob.
    if check_animated and hasattr(knob, 'isAnimated') and knob.isAnimated():
        if not isinstance(knob, nuke.File_Knob):
            logger.debug(f"Ignoring knob '{knob.name()}' as it is animated.")
            return False
    if hasattr(knob, 'isReadOnly') and knob.isReadOnly():
        logger.debug(f"Ignoring knob '{knob.name()}' as it is read-only.")
        return False
    return True


def _apply_knob_to_selected(source_node, knob, value):
    """Copy value to the same knob on all other selected nodes. Returns number of successful copies."""
    node_ids = nuke.tcl('selected_nodes').split()
    copied_count = 0
    for node_id in node_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        if node_name == source_node.name():
            continue

        try:
            float(value)
            is_numeric = True
        except Exception:
            is_numeric = False

        try:
            if is_numeric:
                nuke.tcl(f'knob {node_id}.{knob.name()} {value}')
            else:
                nuke.tcl(f'knob {node_id}.{knob.name()} "{value}"')
            logger.info(f"Copied value '{value}' of knob '{knob.name()}' from node '{source_node.name()}' to node '{node_name}'")
            copied_count += 1
        except Exception as e:
            logger.warning(f"Could not copy value '{value}' of knob '{knob.name()}' from node '{source_node.name()}' to node '{node_name}':\n{e}")
    return copied_count


def update_all_selected():
    global _copying
    if _copying:
        logger.debug("Already copying parameters; ignoring additional trigger.")
        return

    lmb = _tracker.test_validity()
    enter = bool(ctypes.windll.user32.GetAsyncKeyState(0x0D) & 0x8000)
    if not (lmb or enter):
        return

    node = nuke.thisNode()
    knob = nuke.thisKnob()
    if not node or not knob:
        logger.warning("No node or knob found in context; cannot copy parameters.")
        return

    logger.debug(f"Alt+{'Enter' if enter else 'LMB'} on '{knob.name()}' of node '{node.name()}'")

    if not _is_knob_copyable(knob, check_animated=True):
        return

    _copying = True
    try:
        _apply_knob_to_selected(node, knob, knob.getValue())
    finally:
        _copying = False


def copy_to_selected():
    """Copy the value of the right-clicked knob to the same knob on all other selected nodes."""
    global _copying
    if _copying:
        return

    node = nuke.thisNode()
    knob = nuke.thisKnob()
    if not node or not knob:
        logger.warning("No node or knob found in context; cannot copy parameters.")
        return

    if not _is_knob_copyable(knob):
        return

    _copying = True
    try:
        copied_count = _apply_knob_to_selected(node, knob, knob.getValue())
        if copied_count == 0:
            logger.info(f"No other selected nodes to copy '{knob.name()}' to.")
    finally:
        _copying = False


def knob_changed():
    modifiers = QApplication.keyboardModifiers()
    # logger.debug(f"Modifiers: {modifiers}")

    if modifiers & Qt.AltModifier:
        update_all_selected()