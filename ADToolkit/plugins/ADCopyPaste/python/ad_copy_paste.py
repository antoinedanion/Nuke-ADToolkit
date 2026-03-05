"""
ADCopyPaste Core Module

Version 1.0.2

Copyright (c) 2026 Antoine Danion
MIT License — see LICENSE in this plugin's folder
"""

# =============================================================================

# This script allows copying and pasting nodes in Nuke while preserving their input connections,
# even if the input nodes are not selected during the copy operation.

# It supports complex node graphs and ensures that connections are restored correctly upon pasting.
# Cloned nodes are not handled properly.
# A solution would be to store clones data into dots which would be connected to the clone.
# In NukeNC, we can't delete more than 10 nodes at once. So the current version just skips reconnections for clones.

# It uses TCL commands to ensure compatibility with Nuke Indie and Non-Commercial versions.

import logging
import sys
import os
import json
import tempfile

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
logger = logging.getLogger('ADCopyPaste')
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

# Path for temp storage of dependencies
_DEPENDENCIES_FILE = os.path.join(tempfile.gettempdir(), 'nuke_copy_paste_dependencies.json')

def copy():
    # Get selected node IDs
    try:
        nodes_result = nuke.tcl('selected_nodes')
        if not nodes_result:
            logger.warning("No nodes selected")
            return
        nodes_ids = nodes_result.split()
    except Exception as e:
        logger.error(f"Failed to get selected nodes: {e}")
        return
    
    # Detect clones (nodes with duplicate names) to avoid reconnection issues
    node_names = {}
    clone_names = set()
    for node_id in nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        if node_name in node_names:
            clone_names.add(node_name)
            logger.info(f"Detected clone: {node_name}")
        else:
            node_names[node_name] = node_id
    
    # Store original IDs in hidden knobs
    for node_id in nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        try:
            knobs_result = nuke.tcl(f'knobs {node_id}')
            if not knobs_result or 'orig_id' not in knobs_result.split():
                # Create hidden string knob if it doesn't exist
                nuke.tcl(f'addUserKnob node {node_id} 20 temp_copy_data l "INVISIBLE"')
                nuke.tcl(f'addUserKnob node {node_id} 1 orig_id')

            nuke.tcl(f'knob {node_id}.orig_id {node_id}')
            
            logger.debug(f"Stored original ID for node {node_name} ({node_id})")

        except Exception as e:
            logger.error(f"Error storing original ID for node {node_name} ({node_id}): {e}")
            continue
    
    # for node_id in nodes_ids:
    #     print(f'orig_id of {nuke.tcl(f"knob {node_id}.name")} is {nuke.tcl(f"value {node_id}.orig_id")}')
    
    # Gather input and output node connections for each selected node
    nodes_dependencies = {}
    nodes_outputs = {}
    
    for node_id in nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        
        # Store input dependencies
        dep_ids = []
        try:
            num_inputs = int(nuke.tcl(f'inputs {node_id}'))
            for i in range(num_inputs):
                try:
                    input_id = nuke.tcl(f'input {node_id} {i}')
                    dep_ids.append(input_id if input_id else "none")
                except Exception:
                    dep_ids.append("none")

            nodes_dependencies[node_id] = dep_ids

            logger.debug(f"Stored input dependencies for node {node_name} ({node_id})")
            for i, dep_id in enumerate(dep_ids):
                if dep_id != "none":
                    try:
                        dep_node_name = nuke.tcl(f'knob {dep_id}.name')
                        logger.debug(f" - input {i} to {dep_node_name} ({dep_id})")
                    except Exception:
                        logger.debug(f" - input {i} to unknown node ({dep_id})")
                else:
                    logger.debug(f" - input {i} to none")
                  
        except Exception:
            continue
            
        # Store output connections (nodes that use this node as input)
        output_connections = []
        try:
            all_nodes_result = nuke.tcl('nodes')
            if not all_nodes_result:
                nodes_outputs[node_id] = []
                continue
            all_nodes = all_nodes_result.split()
            for other_node_id in all_nodes:
                if other_node_id == node_id:
                    continue
                try:
                    num_inputs = int(nuke.tcl(f'inputs {other_node_id}'))
                    for input_index in range(num_inputs):
                        try:
                            input_node_id = nuke.tcl(f'input {other_node_id} {input_index}')
                            if input_node_id == node_id and other_node_id not in nodes_ids:
                                output_connections.append({
                                    'node_id': other_node_id,
                                    'input_index': input_index
                                })
                        except Exception:
                            continue
                except Exception:
                    continue
            
            nodes_outputs[node_id] = output_connections
            if output_connections:
                logger.debug(f"Stored output connections for node {node_name} ({node_id})")
                for connection in output_connections:
                    out_node_name = nuke.tcl(f'knob {connection["node_id"]}.name')
                    logger.debug(f" - input {connection['input_index']} to {out_node_name} ({connection['node_id']})") 
                
        except Exception as e:
            logger.error(f"Error storing output connections for node {node_name} ({node_id}): {e}")
    # Store dependencies, outputs, and clone info in temp file
    try:
        data_to_store = {
            'dependencies': nodes_dependencies,
            'outputs': nodes_outputs,
            'clone_names': list(clone_names),
        }
        with open(_DEPENDENCIES_FILE, 'w') as f:
            json.dump(data_to_store, f)
    except Exception as e:
        logger.error(f"Error saving dependencies: {e}")
    
    # Copy nodes to clipboard
    nuke.nodeCopy('%clipboard%')

def paste():
    # Check if we have stored dependencies
    if not os.path.exists(_DEPENDENCIES_FILE):
        return
        
    # Load dependencies, outputs, and clone info from temp file
    try:
        with open(_DEPENDENCIES_FILE, 'r') as f:
            data = json.load(f)
            nodes_dependencies = data['dependencies']
            nodes_outputs = data['outputs']
            clone_names = set(data.get('clone_names', []))
    except Exception as e:
        logger.error(f"Error loading dependencies: {e}")
        return
    
    # Paste nodes from clipboard
    nuke.nodePaste('%clipboard%')
    pasted_nodes_ids = nuke.tcl('selected_nodes').split()
    
    # # Disconnect all inputs of pasted nodes to clear Nuke's automatic connections
    # for node_id in pasted_nodes_ids:
    #     node_name = nuke.tcl(f'knob {node_id}.name')
    #     try:
    #         num_inputs = int(nuke.tcl(f'inputs {node_id}'))
    #         for i in range(num_inputs):
    #             nuke.tcl(f'input {node_id} {i} 0')
    #         print(f"Disconnected inputs for node {node_name} ({node_id})")
    #     except Exception as e:
    #         print(f"Error disconnecting inputs for node {node_name} ({node_id})")
    #         continue
    
    # Disconnect any nodes that were connected to the original nodes as outputs
    for node_id in pasted_nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        try:
            # Get the original ID from the hidden knob
            knobs_result = nuke.tcl(f'knobs {node_id}')
            if knobs_result and 'orig_id' in knobs_result.split():
                orig_id = nuke.tcl(f'value {node_id}.orig_id')
                if orig_id in nodes_outputs:
                    output_connections = nodes_outputs[orig_id]
                    for connection in output_connections:
                        output_node_id = connection['node_id']
                        input_index = connection['input_index']
                        try:
                            nuke.tcl(f'input {output_node_id} {input_index} 0')
                            output_node_name = nuke.tcl(f'knob {output_node_id}.name')
                            logger.debug(f"Disconnected output: {output_node_name} input {input_index}")
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Error handling outputs for node {node_name} ({node_id}): {e}")
            continue
    
    # Restore input connections for pasted nodes
    for node_id in pasted_nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        
        # Skip clones to avoid reconnection issues
        if node_name in clone_names:
            logger.info(f"Skipping input reconnection for clone: {node_name} ({node_id})")
            continue
            
        try:
            # Get the original ID from the hidden knob
            knobs_result = nuke.tcl(f'knobs {node_id}')
            if knobs_result and 'orig_id' in knobs_result.split():
                orig_id = nuke.tcl(f'value {node_id}.orig_id')
                if orig_id in nodes_dependencies:
                    dependencies = nodes_dependencies[orig_id]
                    # print(f'Dependencies for pasted node {node_name} ({node_id}) from original {orig_id}: {[nuke.tcl(f"knob {dep_id}.name") for dep_id in dependencies]}')
                    # Restore each input connection
                    for input_index, dep_id in enumerate(dependencies):
                        # Only reconnect if input is empty
                        if nuke.tcl(f'input {node_id} {input_index}') == "0":
                            if dep_id != "none":
                                try:
                                    dep_node_name = nuke.tcl(f'knob {dep_id}.name')
                                    orig_name = nuke.tcl(f'knob {orig_id}.name')
                                    logger.debug(f"Reconnecting input {input_index} of node {node_name} ({node_id}) pasted from {orig_name} ({orig_id}) to {dep_node_name} ({dep_id})")
                                    nuke.tcl(f'input {node_id} {input_index} {dep_id}')
                                except Exception:
                                    continue
                            else:
                                logger.debug(f"Input {input_index} of node {node_name} ({node_id}) remains disconnected: dep_id = {dep_id}")

        except Exception as e:
            logger.error(f"Error restoring connections for node {node_name} ({node_id}): {e}")
            continue
    
    # Restore output connections (reconnect nodes that should connect to the original nodes)
    for node_id in pasted_nodes_ids:
        node_name = nuke.tcl(f'knob {node_id}.name')
        try:
            # Get the original ID from the hidden knob
            knobs_result = nuke.tcl(f'knobs {node_id}')
            if knobs_result and 'orig_id' in knobs_result.split():
                orig_id = nuke.tcl(f'value {node_id}.orig_id')
                orig_name = nuke.tcl(f'knob {orig_id}.name')
                if orig_id in nodes_outputs:
                    output_connections = nodes_outputs[orig_id]
                    for connection in output_connections:
                        output_node_id = connection['node_id']
                        input_index = connection['input_index']
                        try:
                            output_node_name = nuke.tcl(f'knob {output_node_id}.name')
                            logger.debug(f"Reconnecting output: {output_node_name} input {input_index} to original {orig_name} ({orig_id})")
                            nuke.tcl(f'input {output_node_id} {input_index} {orig_id}')
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Error restoring output connections for node {node_name} ({node_id}): {e}")
            continue