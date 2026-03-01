"""
ADMattepaint Core Module

Version 1.1.2

Copyright (c) 2026 Antoine Danion
MIT License — see LICENSE in this plugin's folder
"""

import sys
import os
import platform
import subprocess
import tempfile
import json
import threading
import time
import re
import shutil
import logging

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
logger = logging.getLogger('ADMattepaint')
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

def get_write_tiff_node(node=None):
    """Get reference to the internal Write node"""
    if node is None:
        node = nuke.thisNode()
    return nuke.toNode(f"{node.name()}.Writetiff")


def get_write_png_node(node=None):
    """Get reference to the internal Write PNG node"""
    if node is None:
        node = nuke.thisNode()
    return nuke.toNode(f"{node.name()}.Writepng")


def get_operating_system():
    """Get current operating system"""
    return platform.system()


def get_mattepaint_dir(node):
    """Get absolute mattepaint directory from node"""
    # Use nuke.tcl('subst', ...) to evaluate TCL expressions in the string
    rel_mattepaint_dir = nuke.tcl('subst', node.knob('mattepaint_dir').value())
    abs_mattepaint_dir = os.path.abspath(rel_mattepaint_dir)
    return abs_mattepaint_dir


def get_mattepaint_name(node):
    """Get mattepaint name from node"""
    ref_frame_value = int(node.knob('refFrame').value())
    name = node.knob('mattepaint_name').value()
    mattepaint_name = f"{name}_f{ref_frame_value:04}"
    return mattepaint_name


def get_mattepaint_version(node):
    """Get mattepaint version from node"""
    version = int(node.knob('mattepaint_version').value())
    return version


def increment_mattepaint_version(node):
    """Increment mattepaint version on node"""
    version = get_mattepaint_version(node)
    node.knob('mattepaint_version').setValue(version + 1)
    refresh_latest_export_path(node)


def decrement_mattepaint_version(node):
    """Decrement mattepaint version on node"""
    version = get_mattepaint_version(node)
    if version > 1:
        node.knob('mattepaint_version').setValue(version - 1)
        refresh_latest_export_path(node)


def get_current_mattepaint_dir(node):
    """Get current mattepaint directory from node"""
    abs_mattepaint_dir = get_mattepaint_dir(node)
    mattepaint_name = get_mattepaint_name(node)
    current_mattepaint_dir = os.path.join(abs_mattepaint_dir, mattepaint_name)
    return current_mattepaint_dir


def get_current_mattepaint_out_dir(node):
    """Get current mattepaint output directory from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    out_dir = os.path.join(current_mattepaint_dir, 'out')
    out_dir = os.path.normpath(out_dir)
    return out_dir


def get_current_mattepaint_in_dir(node):
    """Get current mattepaint input directory from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    in_dir = os.path.join(current_mattepaint_dir, 'in')
    in_dir = os.path.normpath(in_dir)
    return in_dir


def get_current_mattepaint_toai_dir(node):
    """Get current mattepaint toai directory from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    toai_dir = os.path.join(current_mattepaint_dir, 'toai')
    toai_dir = os.path.normpath(toai_dir)
    return toai_dir


def get_current_mattepaint_fromai_dir(node):
    """Get current mattepaint fromai directory from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    fromai_dir = os.path.join(current_mattepaint_dir, 'fromai')
    fromai_dir = os.path.normpath(fromai_dir)
    return fromai_dir


def update_latest_export_path(node, file_path):
    """Update the latest_export_path knob on the mattepaint node
    
    Args:
        node: ADMattepaint node
        file_path: Path to the latest export file
    """
    # Convert to forward slashes for Nuke and set the value
    file_path_nuke = file_path.replace('\\', '/')
    node['latest_export_path'].setValue(file_path_nuke)
    logger.info(f"Updated latest_export_path to: {file_path_nuke}")


def get_psd_path(node):
    """Get PSD path from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    mattepaint_name = get_mattepaint_name(node)
    mattepaint_version = get_mattepaint_version(node)
    psd_path = os.path.join(current_mattepaint_dir, f"{mattepaint_name}_v{mattepaint_version:04d}.psd")
    psd_path = os.path.normpath(psd_path)
    return psd_path


def get_last_psd_version_path(node):
    """Get last PSD version path from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    mattepaint_name = get_mattepaint_name(node)
    
    last_version = 0
    if os.path.exists(current_mattepaint_dir):
        existing_files = [f for f in os.listdir(current_mattepaint_dir) if f.startswith(mattepaint_name) and f.endswith('.psd')]
        if existing_files:
            # Extract version numbers from existing files
            versions = []
            for filename in existing_files:
                # Pattern: mattepaint_name_v0001.psd
                try:
                    version_part = filename.replace(mattepaint_name + '_v', '').replace('.psd', '')
                    if version_part.isdigit():
                        versions.append(int(version_part))
                except:
                    pass
            if versions:
                last_version = max(versions)
    
    if last_version > 0:
        psd_path = os.path.join(current_mattepaint_dir, f"{mattepaint_name}_v{last_version:04d}.psd")
        psd_path = os.path.normpath(psd_path)
        return psd_path
    else:
        return None


def get_source_image_path(node, extension):
    """Get image path from node"""
    mattepaint_name = get_mattepaint_name(node)
    image_path = os.path.join(get_current_mattepaint_in_dir(node), f"{mattepaint_name}.{extension}")
    image_path = os.path.normpath(image_path)
    return image_path


def get_output_tif_path(node):
    """Get versioned output TIFF path from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    mattepaint_name = get_mattepaint_name(node)
    psd_version = get_mattepaint_version(node)
    out_dir = os.path.join(current_mattepaint_dir, 'out')
    
    # Find next available export number for this PSD version
    export_number = 1
    if os.path.exists(out_dir):
        # Pattern: mattepaint_name_v{psd_version}.{export_number}.tif
        pattern_prefix = f"{mattepaint_name}_v{psd_version:04d}."
        existing_files = [f for f in os.listdir(out_dir) if f.startswith(pattern_prefix) and f.endswith('.tif')]
        
        if existing_files:
            # Extract export numbers from existing files
            export_numbers = []
            for filename in existing_files:
                try:
                    # Remove prefix and suffix to get export number
                    export_part = filename.replace(pattern_prefix, '').replace('.tif', '')
                    if export_part.isdigit():
                        export_numbers.append(int(export_part))
                except:
                    pass
            if export_numbers:
                export_number = max(export_numbers) + 1
    
    output_filename = f"{mattepaint_name}_v{psd_version:04d}.{export_number:04d}.tif"
    output_path = os.path.join(out_dir, output_filename)
    output_path = os.path.normpath(output_path)

    return output_path


def get_output_png_path_toai(node):
    """Get versioned output PNG path for AI export from node"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)
    mattepaint_name = get_mattepaint_name(node)
    toai_dir = os.path.join(current_mattepaint_dir, 'toai')
    
    # Find next available export number for this PSD version
    export_number = 1
    if os.path.exists(toai_dir):
        # Pattern: mattepaint_name.{export_number}.png
        pattern_prefix = f"{mattepaint_name}."
        existing_files = [f for f in os.listdir(toai_dir) if f.startswith(pattern_prefix) and f.endswith('.png')]
        
        if existing_files:
            # Extract export numbers from existing files
            export_numbers = []
            for filename in existing_files:
                try:
                    # Remove prefix and suffix to get export number
                    export_part = filename.replace(pattern_prefix, '').replace('.png', '')
                    if export_part.isdigit():
                        export_numbers.append(int(export_part))
                except:
                    pass
            if export_numbers:
                export_number = max(export_numbers) + 1
    
    output_filename = f"{mattepaint_name}.{export_number:04d}.png"
    output_path = os.path.join(toai_dir, output_filename)
    output_path = os.path.normpath(output_path)

    return output_path


def get_latest_export_for_version(mattepaint_dir, mattepaint_name, ref_frame, psd_version):
    """Get the latest export file path for the current mattepaint version
    
    This function finds the most recent export number for the current PSD version.
    Used for dynamic Read node linking.
    
    Args:
        mattepaint_dir: Absolute path to mattepaint directory
        mattepaint_name: Base name of the mattepaint
        ref_frame: Reference frame number
        psd_version: PSD version number
    
    Returns:
        Path to the latest export file, or empty string if none found
    """
    try:
        # Debug output
        logger.debug(f"get_latest_export_for_version called with:")
        logger.debug(f"  mattepaint_dir: {mattepaint_dir}")
        logger.debug(f"  mattepaint_name: {mattepaint_name}")
        logger.debug(f"  ref_frame: {ref_frame}")
        logger.debug(f"  psd_version: {psd_version}")
        
        # Build paths from stored parameters
        abs_mattepaint_dir = os.path.abspath(mattepaint_dir)
        full_mattepaint_name = f"{mattepaint_name}_f{ref_frame:04}"
        current_mattepaint_dir = os.path.join(abs_mattepaint_dir, full_mattepaint_name)
        out_dir = os.path.join(current_mattepaint_dir, 'out')
        
        logger.debug(f"  Constructed out_dir: {out_dir}")
        logger.debug(f"  out_dir exists: {os.path.exists(out_dir)}")
        
        if not os.path.exists(out_dir):
            return ""
        
        # Pattern: mattepaint_name_v{psd_version}.{export_number}.tif
        pattern_prefix = f"{full_mattepaint_name}_v{psd_version:04d}."
        logger.debug(f"  Searching for pattern: {pattern_prefix}*.tif")
        
        existing_files = [f for f in os.listdir(out_dir) if f.startswith(pattern_prefix) and f.endswith('.tif')]
        logger.debug(f"  Found files: {existing_files}")
        
        if not existing_files:
            return ""
        
        # Extract export numbers and find the maximum
        export_numbers = []
        for filename in existing_files:
            try:
                export_part = filename.replace(pattern_prefix, '').replace('.tif', '')
                if export_part.isdigit():
                    export_numbers.append((int(export_part), filename))
            except:
                pass
        
        if not export_numbers:
            return ""
        
        # Get the file with the highest export number
        export_numbers.sort(reverse=True)
        latest_filename = export_numbers[0][1]
        latest_path = os.path.join(out_dir, latest_filename)
        latest_path = os.path.normpath(latest_path)
        
        # Convert to forward slashes for Nuke
        latest_path = latest_path.replace('\\', '/')

        logger.debug(f"  Returning path: {latest_path}")
        return latest_path
    except Exception as e:
        logger.error(f"Error getting latest export: {e}")
        import traceback
        traceback.print_exc()
        return ""


def refresh_latest_export_path(node):
    """Refresh the latest_export_path knob by scanning for the latest export
    
    Args:
        node: ADMattepaint node
        
    Returns:
        Path to the latest export, or empty string if none found
    """
    try:
        # Get current parameters from node
        mattepaint_dir = nuke.tcl('subst', node.knob('mattepaint_dir').value())
        mattepaint_name = node.knob('mattepaint_name').value()
        ref_frame = int(node.knob('refFrame').value())
        psd_version = int(node.knob('mattepaint_version').value())
        
        # Find the latest export for current version
        latest_path = get_latest_export_for_version(mattepaint_dir, mattepaint_name, ref_frame, psd_version)
        
        update_latest_export_path(node, latest_path)
        
        return latest_path
    except Exception as e:
        logger.error(f"Error refreshing latest export path: {e}")
        import traceback
        traceback.print_exc()
        return ""


def get_ref_frame(node):
    """Get reference frame from node"""
    return int(node.knob('refFrame').value())


def is_nuke_using_ocio():
    """Check if Nuke is using OCIO color management"""
    try:
        cm = nuke.root().knob('colorManagement').value()
        return cm == 'OCIO'
    except (ValueError, RuntimeError, AttributeError):
        # Return default if root node isn't available yet
        return False


def set_to_current_frame(node):
    """Set reference frame to current frame"""
    curr_frame = nuke.frame()
    node.knob('refFrame').setValue(curr_frame)


def set_colorspace(node):
    """Set colorspace on internal Write nodes"""
    try:
        write_nodes = [
            get_write_tiff_node(node),
            get_write_png_node(node),
        ]

        if is_nuke_using_ocio():
            for write_node in write_nodes:
                write_node['colorspace'].setValue('data')
        else:
            for write_node in write_nodes:
                write_node['colorspace'].setValue('linear')
    except (ValueError, RuntimeError, AttributeError) as e:
        # Silently fail if nodes aren't ready yet during script loading
        pass


def set_mattepaint_name(node):
    """Set mattepaint name string knob"""
    try:
        name = node.knob('mattepaint_name').value()
        if not name:
            name = node.name()
            node.knob('mattepaint_name').setValue(name)
    except (ValueError, RuntimeError, AttributeError) as e:
        # Silently fail if nodes aren't ready yet during script loading
        pass


def set_datatype(node):
    """Set datatype on internal Write node"""
    data_types = {
        'png': {
            "8 bit": "8 bit",
            "16 bit": "16 bit",
        },
        'tiff': {
            "8 bit": "8 bit",
            "16 bit": "16 bit",
            "32 bit": "32 bit float",
        }
    }

    try:
        write_node_tiff = get_write_tiff_node(node)
        try:
            data_type = data_types['tiff'][node['out_image_datatype'].value()]
        except KeyError:
            data_type = data_types['tiff']["32 bit"]
        write_node_tiff['datatype'].setValue(data_type)

        write_node_png = get_write_png_node(node)
        try:
            data_type_png = data_types['png'][node['out_image_datatype'].value()]
        except KeyError:
            data_type_png = data_types['png']["16 bit"]
        write_node_png['datatype'].setValue(data_type_png)

    except (ValueError, RuntimeError, AttributeError) as e:
        # Silently fail if nodes aren't ready yet during script loading
        pass


def make_current_mattepaint_dirs(node):
    """Create necessary directories for current mattepaint"""
    current_mattepaint_dir = get_current_mattepaint_dir(node)

    subdirs = []

    subdirs_field = node['mattepaint_subdirectories'].value()
    if subdirs_field:
        subdirs = re.split(',|\n', subdirs_field)
    subdirs.append('in')
    subdirs.append('out')
    subdirs.append('toai')
    subdirs.append('fromai')
    for subdir in subdirs:
        os.makedirs(os.path.join(current_mattepaint_dir, subdir.strip()), exist_ok=True)


# ============================================================================
# CHANGE HANDLERS
# ============================================================================

def knob_changed(node, knob):
    """Main knob changed callback"""
    try:
        # print(f'Knob changed: {knob.name()}')
        if knob.name() == 'out_colorspace' or knob.name() == 'in_colorspace':
            set_colorspace(node)
        elif knob.name() == 'out_image_datatype':
            set_datatype(node)
        elif knob.name() == 'ps_version':
            # Show/hide custom path knob based on selection
            ps_version = node['ps_version'].value()
            if ps_version == 'Custom':  # Index 2
                node['custom_photoshop_path'].setVisible(True)
            else:
                node['custom_photoshop_path'].setVisible(False)
        elif knob.name() == 'mattepaint_version' or knob.name() == 'refFrame' or knob.name() == 'mattepaint_name' or knob.name() == 'mattepaint_dir':
            # Refresh the latest export path when version or other key parameters change
            refresh_latest_export_path(node)
    except Exception as e:
        # Silently handle errors
        pass


def on_create(node):
    """Main on create callback"""
    try:
        # Check if we're loading a script (node already has values from file)
        # vs creating a brand new node (values are at defaults)
        is_loading_script = False
        
        try:
            # If we can't access root or if root name is empty, we're likely loading
            root = nuke.root()
            if not root or not root.name():
                is_loading_script = True
        except:
            is_loading_script = True
        
        load_prefs(node)
        
        # Ensure this node has a unique ID
        # ensure_node_uid(node)
        
        # Initialize custom path visibility based on ps_version
        ps_version = node['ps_version'].value()
        if ps_version == 'Custom':
            node['custom_photoshop_path'].setVisible(True)
        else:
            node['custom_photoshop_path'].setVisible(False)

        # Only run initialization for newly created nodes, not when loading scripts
        if not is_loading_script:
            set_to_current_frame(node)
            set_colorspace(node)
            set_mattepaint_name(node)
        

    except Exception as e:
        # Silently handle errors during script loading
        pass


# ============================================================================
# JUMP TO DIRECTORY
# ============================================================================


def go_to_current_mattepaint_dir(node, subdir=''):
    """Open current mattepaint directory in file explorer"""

    saved = is_nk_file_saved()

    if saved:
        try:
            make_current_mattepaint_dirs(node)
            if subdir == '':
                dir = get_current_mattepaint_dir(node)
            else:
                dir = os.path.join(get_current_mattepaint_dir(node), subdir)

            if not os.path.exists(dir):
                nuke.message("Mattepaint directory does not exist.")
                return

            system = get_operating_system()

            if system == 'Windows':
                subprocess.Popen(f'explorer "{dir}"')
            elif system == 'Darwin':
                subprocess.Popen(['open', dir])
            else:
                nuke.message("Your operating system is not compatible.")
        except Exception as e:
            nuke.message(f"Error opening directory: {str(e)}")


# ============================================================================
# PHOTOSHOP FUNCTIONS
# ============================================================================


def ps_script_new_psd(image_path, output_path, background=False):
    """Create JSX script for Photoshop automation"""
    image_path_escaped = image_path.replace('\\', '/')
    output_path_escaped = output_path.replace('\\', '/')

    image_path_escaped = image_path_escaped.replace('"', '\\"')
    output_path_escaped = output_path_escaped.replace('"', '\\"')

    script_content = f'''
        var imagePath = "{image_path_escaped}";
        var outputPath = "{output_path_escaped}";

        var image = new File(imagePath);
        var doc = app.open(image);

        var psdPath = new File(outputPath);
        var saveOptions = new PhotoshopSaveOptions();
        saveOptions.layers = true;
        saveOptions.alphaChannels = true;
        saveOptions.embedColorProfile = true;

        doc.saveAs(psdPath, saveOptions, true, Extension.LOWERCASE);
        var psdDoc = app.open(psdPath);
        doc.close();

        // Add a new layer on top
        var newLayer = psdDoc.artLayers.add();
        newLayer.name = "Layer 1";
        psdDoc.activeLayer = newLayer;

        // Save the PSD with the new layer
        psdDoc.save();
        '''
    return script_content


def ps_script_open_psd(psd_path, background=False):
    """Create JSX script for Photoshop automation"""
    psd_path_escaped = psd_path.replace('\\', '/')
    psd_path_escaped = psd_path_escaped.replace('"', '\\"')

    script_content = f'''
        var psd_path = "{psd_path_escaped}";
        var fileObj = new File(psd_path);
        app.open(fileObj);
        '''
    return script_content


def ps_script_open_and_export_tiff(psd_path, output_path, close_when_done=True):
    """Create JSX script to open PSD and export it as TIFF
    
    Args:
        psd_path: Path to PSD file
        output_path: Path to output TIFF file
        close_when_done: If True, close the document after export; if False, leave it open
    """
    psd_path_escaped = psd_path.replace('\\', '/')
    psd_path_escaped = psd_path_escaped.replace('"', '\\"')
    output_path_escaped = output_path.replace('\\', '/')
    output_path_escaped = output_path_escaped.replace('"', '\\"')

    close_script = '''
        // Close original PSD without saving (already saved above if needed)
        doc.close(SaveOptions.DONOTSAVECHANGES);
    ''' if close_when_done else ''

    script_content = f'''
        var psdPath = "{psd_path_escaped}";
        var outputPath = "{output_path_escaped}";

        // Open the PSD
        var psdFile = new File(psdPath);
        var doc = app.open(psdFile);

        // Save if there are unsaved changes
        if (!doc.saved) {{
            doc.save();
        }}

        // Export as TIFF
        var saveFile = new File(outputPath);

        var tiffOptions = new TiffSaveOptions();
        tiffOptions.layers = false;
        tiffOptions.alphaChannels = true;
        tiffOptions.embedColorProfile = true;
        tiffOptions.imageCompression = TIFFEncoding.NONE;
        tiffOptions.byteOrder = ByteOrder.IBM;  // PC byte order

        // Flatten a copy
        var tempDoc = doc.duplicate();
        tempDoc.flatten();
        tempDoc.saveAs(saveFile, tiffOptions, true, Extension.LOWERCASE);
        tempDoc.close(SaveOptions.DONOTSAVECHANGES);
        {close_script}
        '''
    return script_content


def is_psd_file_open(psd_path):
    """
    Check if a specific PSD file is currently open in Photoshop.
    Returns True if open, False otherwise.

    """
    system = get_operating_system()
    psd_path_normalized = os.path.normpath(psd_path)
    
    try:
        if system == 'Windows':
            # Try win32com first
            try:
                import win32com.client
                # Try to connect to Photoshop
                ps_app = win32com.client.Dispatch("Photoshop.Application")
                
                # Check all open documents
                for i in range(1, ps_app.Documents.Count + 1):
                    doc = ps_app.Documents.Item(i)
                    doc_path = os.path.normpath(doc.FullName)
                    if doc_path == psd_path_normalized:
                        print(f"PSD file is already open in Photoshop: {psd_path}")
                        return True
                
                return False
            except ImportError:
                # Fallback to PowerShell if win32com not available
                logger.debug("win32com not available, using PowerShell to check if PSD is open...")
                
                # Use single backslashes for PowerShell
                psd_path_ps = psd_path_normalized.replace("\\", "\\")
                ps_script = f'''
                try {{
                    $ps = New-Object -ComObject Photoshop.Application
                    $targetPath = "{psd_path_ps}"
                    $docCount = $ps.Documents.Count
                    
                    for ($i = 1; $i -le $docCount; $i++) {{
                        $doc = $ps.Documents.Item($i)
                        $docPath = $doc.FullName
                        
                        # Normalize both paths for comparison
                        $docPathNorm = [System.IO.Path]::GetFullPath($docPath)
                        $targetPathNorm = [System.IO.Path]::GetFullPath($targetPath)
                        
                        if ($docPathNorm -eq $targetPathNorm) {{
                            Write-Output "OPEN"
                            Write-Output $docPathNorm
                            exit 0
                        }}
                    }}
                    Write-Output "CLOSED"
                    exit 0
                }} catch {{
                    Write-Output "ERROR: $_"
                    exit 1
                }}
                '''
                
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                return 'OPEN' in result.stdout
            except:
                # Photoshop not running
                return False
                
        elif system == 'Darwin':
            # On macOS, use AppleScript to check open documents
            script = f'''
            tell application "Adobe Photoshop 2024"
                set docCount to count of documents
                repeat with i from 1 to docCount
                    set docPath to file path of document i as string
                    if docPath is "{psd_path}" then
                        return true
                    end if
                end repeat
                return false
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True
            )
            return 'true' in result.stdout.lower()
    except Exception as e:
        logger.debug(f"Could not check if PSD is open: {e}")
        return False
    
    return False


def get_powershell_execute_jsx_script(script_path, background=True):
    """Generate PowerShell script to execute JSX in Photoshop
    
    Args:
        script_path: Path to the JSX script file
        background: If True, keeps Photoshop in background; if False, brings to foreground (not implemented)
    """
    return f'''
        $scriptContent = Get-Content -Path "{script_path}" -Raw
        $ps = New-Object -ComObject Photoshop.Application
        $ps.DoJavaScript($scriptContent)
        '''


def run_photoshop_workflow(system, ps, script_path, background=False):
    """Run Photoshop in background thread
    
    Args:
        system: Operating system name
        ps: Photoshop executable path
        script_path: Path to JSX script
        background: If True, keeps Photoshop in background; if False, brings to foreground (default: False)
    """
    try:
        if system == 'Windows':
            # On Windows, use COM to execute JSX
            try:
                import win32com.client
                # Read script content
                with open(script_path, 'r') as f:
                    script_content = f.read()
                # Execute via COM
                ps_app = win32com.client.Dispatch("Photoshop.Application")
                ps_app.DoJavaScript(script_content)
                logger.debug("Successfully executed JSX via COM")
                
                # Bring Photoshop to foreground by executing the exe
                if not background:
                    try:
                        subprocess.Popen([ps])
                        logger.debug("Brought Photoshop to foreground")
                    except Exception as e:
                        logger.debug(f"Could not bring Photoshop to foreground: {e}")
                else:
                    logger.debug("Keeping Photoshop in background")
                    
            except ImportError:
                # Fallback to PowerShell if win32com not available
                logger.debug("win32com not available, using PowerShell...")
                
                ps_script = get_powershell_execute_jsx_script(script_path, background=background)
                command = ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                process.wait()
                
                # Bring Photoshop to foreground by executing the exe
                if not background:
                    try:
                        subprocess.Popen([ps])
                        logger.debug("Brought Photoshop to foreground via PowerShell fallback")
                    except Exception as e:
                        logger.debug(f"Could not bring Photoshop to foreground: {e}")
                
        elif system == 'Darwin':
            # On macOS, osascript can execute JSX directly
            command = ['osascript', '-e', f'tell application "{ps}" to do javascript file "{script_path}"']
            process = subprocess.Popen(command)
            process.wait()
            
            # Activate Photoshop on macOS if requested
            if not background:
                try:
                    activate_command = ['osascript', '-e', f'tell application "{ps}" to activate']
                    subprocess.Popen(activate_command)
                    logger.debug("Brought Photoshop to foreground on macOS")
                except Exception as focus_error:
                    logger.debug(f"Could not bring Photoshop to foreground: {focus_error}")
            else:
                logger.debug("Keeping Photoshop in background")
        
        # Clean up temp script
        try:
            os.unlink(script_path)
        except:
            pass
    except Exception as e:
        logger.error(f"Error in Photoshop workflow: {e}")
        import traceback
        traceback.print_exc()


def open_psd(system, ps, mode, node, background=False):
    """Open file in Photoshop
    
    Args:
        system: Operating system name
        ps: Photoshop executable path
        mode: 'new' or 'open' mode
        node: Nuke node
        background: If True, keeps Photoshop in background; if False, brings to foreground (default: False)
    """
    try:
        file_path = get_source_image_path(node, 'tiff')
        psd_path = get_psd_path(node)

        os.makedirs(os.path.dirname(psd_path), exist_ok=True)

        if mode == 'new':
            script_content = ps_script_new_psd(file_path, psd_path, background)
        elif mode == 'open':
            script_content = ps_script_open_psd(psd_path, background)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsx', delete=False) as temp_file:
            temp_file.write(script_content)
            temp_script_path = temp_file.name
        
        # Start workflow in background thread to avoid freezing Nuke
        thread = threading.Thread(target=run_photoshop_workflow, args=(system, ps, temp_script_path, background))
        thread.daemon = True
        thread.start()

    except Exception as e:
        nuke.message(f"Error while opening Photoshop: {e}")


def pre_render_tiff(node):
    """Generate render image path"""

    parent = node.parent()
    output_tiff = get_source_image_path(parent, 'tiff')

    # Create directories if they don't exist
    os.makedirs(os.path.dirname(output_tiff), exist_ok=True)

    # Ensure proper path separators and escape backslashes for Nuke
    output_tiff = output_tiff.replace('\\', '/')
    logger.debug(f'output_tiff: {output_tiff}')

    node['file'].setValue(output_tiff)
    logger.debug('beforeRender : SUCCESS')


def pre_render_png(node):
    """Generate render image path with versioning"""

    parent = node.parent()
    output_png = get_output_png_path_toai(parent)

    # Create directories if they don't exist
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    # Ensure proper path separators and escape backslashes for Nuke
    output_png = output_png.replace('\\', '/')
    logger.debug(f'output_png: {output_png}')

    node['file'].setValue(output_png)
    logger.debug('beforeRender : SUCCESS')


def render_source_image_tiff(node):
    """Render the tiif image"""
    write_node = get_write_tiff_node(node)
    ref_frame = get_ref_frame(node)
    nuke.execute(write_node, ref_frame, ref_frame)


def render_source_image_png(node):
    """Render the png image"""
    write_node = get_write_png_node(node)
    ref_frame = get_ref_frame(node)
    nuke.execute(write_node, ref_frame, ref_frame)


def get_photoshop_executable(system):
    """Choose Photoshop executable based on version"""
    win_base_path = "C:\\Program Files\\Adobe"
    mac_base_path = "/Applications"

    if system == 'Windows':
        # Find the latest Photoshop version installed
        dir_search_name = "Adobe Photoshop"
        ps_versions = []
        
        for folder in os.listdir(win_base_path):
            if dir_search_name in folder and os.path.isdir(os.path.join(win_base_path, folder)):
                # Extract year from folder name like "Adobe Photoshop 2026"
                parts = folder.split()
                if len(parts) >= 3 and parts[-1].isdigit():
                    year = int(parts[-1])
                    ps_versions.append((year, folder))
        
        if ps_versions:
            # Sort by year and get the latest
            ps_versions.sort(reverse=True)
            last_ps = ps_versions[0][1]
            exe_path = f"{win_base_path}\\{last_ps}\\Photoshop.exe"
            return exe_path
        else:
            nuke.alert("No Photoshop version found!")
            return None
    elif system == 'Darwin':
        # Find the latest Photoshop version installed on macOS
        dir_search_name = "Adobe Photoshop"
        ps_versions = []
        
        for folder in os.listdir(mac_base_path):
            if dir_search_name in folder and os.path.isdir(os.path.join(mac_base_path, folder)):
                # Check if the .app exists
                app_path = os.path.join(mac_base_path, folder, f"{folder}.app")
                if os.path.exists(app_path):
                    # Extract year from folder name like "Adobe Photoshop 2026"
                    parts = folder.split()
                    if len(parts) >= 3 and parts[-1].isdigit():
                        year = int(parts[-1])
                        ps_versions.append((year, folder))
        
        if ps_versions:
            # Sort by year and get the latest
            ps_versions.sort(reverse=True)
            last_ps = ps_versions[0][1]
            return last_ps
        else:
            nuke.alert("No Photoshop version found!")
            return None
    else:
        nuke.message("Your operating system is not compatible.")


def get_custom_photoshop_path(node, from_prefs=False):
    """Get custom Photoshop path from node
    
    Args:
        node: ADMattepaint node
        from_prefs: If True, get from preferences knob; if False, get from one-time knob
    
    Returns:
        Path to Photoshop executable or None
    """
    knob_name = 'preferred_photoshop_path' if from_prefs else 'custom_photoshop_path'
    psd_path = node.knob(knob_name).value()
    if len(psd_path) == 0:
        nuke.alert("You need to specify the file path of your Photoshop executable file.")
        return None
    else:
        psd_path = os.path.normpath(psd_path)
        return psd_path


def open_file_in_photoshop(node, mode, background=False):
    """Open file in Photoshop
    
    Args:
        node: Nuke node
        mode: 'new' or 'open' mode
        background: If True, keeps Photoshop in background; if False, brings to foreground (default: False)
    """

    system = get_operating_system()
    ps_version = node.knob('ps_version').value()
    
    if ps_version == 'Auto':
        ps = get_photoshop_executable(system)
    elif ps_version == 'From Preferences':
        ps = get_custom_photoshop_path(node, from_prefs=True)
    else:  # 'Custom'
        ps = get_custom_photoshop_path(node, from_prefs=False)
    
    if not ps:
        return

    open_psd(system, ps, mode, node, background)


def is_input_connected(node):
    """Check if input is connected before opening Photoshop"""
    if node.inputs():
        return True
    else:
        nuke.message("Please connect the Source input before proceeding.")
        return False


def is_nk_file_saved():
    """Validate that nuke script is saved"""
    script_path = nuke.script_directory()

    if len(script_path) == 0:
        nuke.message("Please, save your .nk file before proceeding")
        return False
    else:
        return True


def create_read_node_from_file(node, file_path, dynamic=False):
    """Create a Read node for the given file path
    
    Args:
        node: ADMattepaint node
        file_path: Path to the image file
        dynamic: If True, use a TCL expression to reference the latest_export_path knob
    
    Returns:
        The created Read node
    """
    # Ensure we're in the root context, not inside the group
    with nuke.root():
        # Create Read node
        read_node = nuke.nodes.Read()
        read_node.setXpos(node.xpos())
        read_node.setYpos(node.ypos() + 50)
        read_node.setName(f"{get_mattepaint_name(node)}_Read")

        if dynamic:
            # Simply reference the latest_export_path knob from the mattepaint node
            mp_node_name = node.name()
            read_node['file'].setValue(f"[value {mp_node_name}.latest_export_path]")
        else:
            # Use static file path
            file_path_nuke = file_path.replace('\\', '/')
            read_node['file'].setValue(file_path_nuke)
        
        # Set colorspace from the ADMattepaint node's out_colorspace
        if is_nuke_using_ocio():
            read_node['colorspace'].setValue(node['out_colorspace'].value())
        else:
            read_node['colorspace'].setValue('linear')    
        
        return read_node


def open_in_photoshop(node, background=False):
    """Main function to open in Photoshop
    
    Args:
        node: Nuke node
        background: If True, keeps Photoshop in background; if False, brings to foreground (default: False)
    """
    saved = is_nk_file_saved()
    connected = is_input_connected(node)

    if saved and connected:
        try:
            make_current_mattepaint_dirs(node)

            psd_path = get_psd_path(node)

            if os.path.exists(psd_path):
                # PSD for current version exists, just open it
                open_file_in_photoshop(node, 'open', background)
            else:
                # Check if an older version exists
                last_psd_path = get_last_psd_version_path(node)
                
                if last_psd_path and os.path.exists(last_psd_path):
                    # Copy the last version to the new version
                    logger.info(f"Found previous version: {last_psd_path}")
                    logger.info(f"Copying to new version: {psd_path}")
                    
                    # Create directory if needed
                    os.makedirs(os.path.dirname(psd_path), exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(last_psd_path, psd_path)
                    
                    logger.info(f"Successfully copied previous version")
                    
                    # Open the copied version
                    open_file_in_photoshop(node, 'open', background)
                else:
                    # No previous version exists, create new from TIFF
                    render_source_image_tiff(node)
                    open_file_in_photoshop(node, 'new', background)
        except Exception as e:
            nuke.message(f"Error while opening in Photoshop: {str(e)}")


def get_from_photoshop(node):
    """Export current version from Photoshop and load it in Nuke"""
    
    psd_path = get_psd_path(node)
    
    # Check if PSD exists
    if not os.path.exists(psd_path):
        nuke.message("No PSD file found. Please open in Photoshop first.")
        return
    
    # Get output path with version number
    output_tiff_path = get_output_tif_path(node)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_tiff_path), exist_ok=True)
    
    # Check if this specific PSD file is already open in Photoshop
    psd_was_open = is_psd_file_open(psd_path)
    logger.debug(f"PSD file was {'already open' if psd_was_open else 'not open'} in Photoshop")
    
    # Create JSX script to open PSD and export TIFF
    # Only close the document if it was not already open
    script_content = ps_script_open_and_export_tiff(psd_path, output_tiff_path, close_when_done=not psd_was_open)
    
    try:
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsx', delete=False) as temp_file:
            temp_file.write(script_content)
            temp_script_path = temp_file.name
        
        # Get Photoshop executable
        system = get_operating_system()
        ps_version = node.knob('ps_version').value()
        
        if ps_version == 'Auto':
            ps = get_photoshop_executable(system)
        elif ps_version == 'From Preferences':
            ps = get_custom_photoshop_path(node, from_prefs=True)
        else:  # 'Custom'
            ps = get_custom_photoshop_path(node, from_prefs=False)
        
        if not ps:
            return
        
        # Define function to run and wait for file
        def export_and_wait():
            # Run Photoshop workflow (keep in background for export)
            run_photoshop_workflow(system, ps, temp_script_path, background=True)
            
            # Wait for file to be written
            logger.debug(f"Waiting for file: {output_tiff_path}")
            max_attempts = 120  # 60 seconds max
            for i in range(max_attempts):
                test = os.path.exists(output_tiff_path)
                if test:
                    # File exists, update the node's latest_export_path knob
                    logger.info(f"File successfully exported: {output_tiff_path}")
                    
                    # Update the latest export path on the mattepaint node (must run in main thread)
                    nuke.executeInMainThread(update_latest_export_path, (node, output_tiff_path))
                    
                    logger.info(f"Export complete.")
                    return
                
                logger.debug(f"Still waiting... Attempt ({i}/{max_attempts})")
                time.sleep(0.5)
            
            logger.warning("Timeout: File not created")
            nuke.executeInMainThread(nuke.message, ("Timeout: Export file was not created",))
        
        # Start in background thread
        logger.info(f"Opening PSD and exporting to: {output_tiff_path}")
        thread = threading.Thread(target=export_and_wait)
        thread.daemon = True
        thread.start()
            
    except Exception as e:
        nuke.message(f"Error: {str(e)}")
        logger.error(f"Error details: {e}")
        import traceback
        traceback.print_exc()


def get_from_exports(node):
    """Get specific export version from exports directory and load in Nuke"""

    saved = is_nk_file_saved()

    if saved:
        try:
            make_current_mattepaint_dirs(node)

            out_dir = get_current_mattepaint_out_dir(node)
            if not os.path.exists(out_dir):
                nuke.message("No exports directory found.")
                return
            out_dir = out_dir + '\\'

            # Open file dialog to select TIFF
            selected_file = nuke.getFilename("Select Exported TIFF", default=out_dir)
            if not selected_file:
                return

            if not os.path.exists(selected_file):
                nuke.message("Selected file does not exist.")
                return

            # Create Read node with static file path
            read_node = create_read_node_from_file(node, selected_file, dynamic=False)
            
            logger.info(f"Successfully created Read node with: {selected_file}")
        except Exception as e:
            nuke.message(f"Error creating Read node: {str(e)}")


def create_linked_read_node(node):
    """Create a Read node dynamically linked to the latest export path
    
    Args:
        node: ADMattepaint node
    """
    try:
        # Search for latest export directly
        found_path = refresh_latest_export_path(node)
        
        if not found_path:
            nuke.message("No export files found.\nPlease Get from Photoshop to update linked Read nodes.")
        
        # Create Read node with dynamic linking
        read_node = create_read_node_from_file(node, found_path, dynamic=True)
        
        logger.info(f"Successfully created dynamic Read node linked to: {found_path}")
        
    except Exception as e:
        nuke.message(f"Error creating Read node: {str(e)}")
        logger.error(f"Error details: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# AI (ARTIFICIAL INTELLIGENCE) EXPORT
# ============================================================================

def export_to_ai(node):
    """Export png to "toai" directory for AI processing"""
    is_saved = is_nk_file_saved()

    if is_saved:
        try:
            make_current_mattepaint_dirs(node)
            render_source_image_png(node)
            go_to_current_mattepaint_dir(node, subdir='toai')
        except Exception as e:
            nuke.message(f"Error exporting to AI: {str(e)}")
    else:
        nuke.message("Please, save your .nk file before proceeding")


# ============================================================================
# PREFERENCES
# ============================================================================


def save_prefs(node):
    """Save preferences to file"""

    # Save prefs to .nuke user folder
    nuke_user_dir = os.path.expanduser('~/.nuke')
    prefs_file = os.path.join(nuke_user_dir, f'ADMattepaint_prefs.json')
    prefs_file = os.path.normpath(prefs_file)

    # Collect preferences
    prefs = {
        'mattepaint_dir': node['mattepaint_dir'].value(),
        'preferred_photoshop_path': node['preferred_photoshop_path'].value(),
        'mattepaint_subdirectories': node['mattepaint_subdirectories'].value(),
    }

    # Save to JSON
    try:
        with open(prefs_file, 'w') as f:
            json.dump(prefs, f, indent=2)
        logger.info(f'Preferences saved to: {prefs_file}')
    except Exception as e:
        nuke.message(f'Error saving preferences: {str(e)}')


def load_prefs(node):
    """Load preferences from file"""

    script_dir = nuke.script_directory()

    # Default mattepaint directory
    default_mattepaint_dir = os.path.join('[file dirname [value root.name]]/mattepaint')
    default_preferred_photoshop_path = ''
    default_mattepaint_subdirectories = ''

    nuke_user_dir = os.path.expanduser('~/.nuke')
    prefs_file = os.path.join(nuke_user_dir, f'ADMattepaint_prefs.json')
    prefs_file = os.path.normpath(prefs_file)
    
    try:
        with open(prefs_file, 'r') as f:
            prefs = json.load(f)
            temp_mattepaint_dir = prefs.get('mattepaint_dir', default_mattepaint_dir)
            node['mattepaint_dir'].setValue(temp_mattepaint_dir)
            temp_preferred_photoshop_path = prefs.get('preferred_photoshop_path', default_preferred_photoshop_path)
            node['preferred_photoshop_path'].setValue(temp_preferred_photoshop_path)
            temp_mattepaint_subdirectories = prefs.get('mattepaint_subdirectories', default_mattepaint_subdirectories)
            node['mattepaint_subdirectories'].setValue(temp_mattepaint_subdirectories)
            logger.info(f'Preferences loaded from: {prefs_file}')
    except:
        node['mattepaint_dir'].setValue(default_mattepaint_dir)
        node['preferred_photoshop_path'].setValue(default_preferred_photoshop_path)
        node['mattepaint_subdirectories'].setValue(default_mattepaint_subdirectories)
        logger.info('No preferences file found, using default')

def reset_prefs(node):
    """Reset preferences"""

    # Reset temp directory to system default
    default_mattepaint_dir = '[file dirname [value root.name]]/mattepaint'
    node['mattepaint_dir'].setValue(default_mattepaint_dir)
    default_preferred_photoshop_path = ''
    node['preferred_photoshop_path'].setValue(default_preferred_photoshop_path)
    default_mattepaint_subdirectories = ''
    node['mattepaint_subdirectories'].setValue(default_mattepaint_subdirectories)

    # Delete preferences file
    nuke_user_dir = os.path.expanduser('~/.nuke')
    prefs_file = os.path.join(nuke_user_dir, f'ADMattepaint_prefs.json')
    prefs_file = os.path.normpath(prefs_file)

    try:
        if os.path.exists(prefs_file):
            os.remove(prefs_file)
            logger.info(f'Preferences file deleted: {prefs_file}')
        else:
            logger.info('No preferences file found to delete')
    except Exception as e:
        nuke.message(f'Error resetting preferences: {str(e)}')