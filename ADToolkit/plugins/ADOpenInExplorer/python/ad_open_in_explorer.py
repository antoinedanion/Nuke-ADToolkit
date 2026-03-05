"""
ADOpenInExplorer Core Module

Version 1.0.0

Copyright (c) 2026 Antoine Danion
MIT License — see LICENSE in this plugin's folder
"""

# =============================================================================

# Opens Windows Explorer at the folder of the selected node's 'file' knob.
# Works with any node that has a 'file' knob (Read, Write, ReadGeo, etc.).
# If the path contains frame tokens (e.g. %04d), falls back to the parent directory.

# It uses TCL commands to ensure compatibility with Nuke Indie and Non-Commercial versions.

# =============================================================================

import logging
import sys
import os
import subprocess

import nuke


# ============================================================================
# LOGGING SETUP
# ============================================================================

class _DynamicStdoutHandler(logging.StreamHandler):
    """Always writes to the current sys.stdout, even if Nuke replaces it."""
    def emit(self, record):
        self.stream = sys.stdout
        super().emit(record)

# Create logger for this module
logger = logging.getLogger('ADOpenInExplorer')
logger.setLevel(logging.DEBUG)

# Only add handler if it doesn't exist (prevents duplicate logs on script reload)
if not logger.handlers:
    handler = _DynamicStdoutHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# MAIN
# ============================================================================

def open_in_explorer():
    """Open Windows Explorer at the folder of the 'file' knob of the selected node."""

    # Get selected nodes via TCL to bypass NukeNC limitations
    try:
        nodes_result = nuke.tcl('selected_nodes')
        if not nodes_result:
            logger.warning("No node selected.")
            nuke.message("No node selected.")
            return
        node_ids = nodes_result.split()
    except Exception as e:
        logger.error(f"Failed to get selected nodes: {e}")
        return

    node_id = node_ids[0]
    node_name = nuke.tcl(f'knob {node_id}.name')

    # Check the node has a 'file' knob
    try:
        knobs_result = nuke.tcl(f'knobs {node_id}')
        if not knobs_result or 'file' not in knobs_result.split():
            logger.warning(f"Node '{node_name}' has no 'file' knob.")
            nuke.message(f"Node '{node_name}' has no 'file' knob.")
            return
    except Exception as e:
        logger.error(f"Failed to list knobs for node '{node_name}': {e}")
        return

    # Read the evaluated file path via TCL
    try:
        raw_path = nuke.tcl(f'value {node_id}.file')
    except Exception as e:
        logger.error(f"Failed to read 'file' knob of '{node_name}': {e}")
        return

    if not raw_path:
        logger.warning(f"The 'file' knob of '{node_name}' is empty.")
        nuke.message(f"The 'file' knob of '{node_name}' is empty.")
        return

    # Normalize path separators for Windows
    path = os.path.normpath(raw_path)
    logger.debug(f"Resolved path: {path}")

    if os.path.isfile(path):
        # Select the file in Explorer
        logger.info(f"Opening Explorer and selecting: {path}")
        subprocess.Popen(["explorer", "/select,", path])
    elif os.path.isdir(path):
        logger.info(f"Opening Explorer at directory: {path}")
        subprocess.Popen(["explorer", path])
    else:
        # Path may contain frame number tokens; try the parent directory
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            logger.info(f"Opening Explorer at parent directory: {parent}")
            subprocess.Popen(["explorer", parent])
        else:
            logger.warning(f"Path not found: {path}")
            nuke.message(f"Path not found:\n{path}")
