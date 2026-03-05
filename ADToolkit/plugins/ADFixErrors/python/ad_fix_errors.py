'''
ADFixErrors Core Module

Version 2.1.2

Original work Copyright (c) 2012 Magno Borgo — BSD 3-Clause License
Modifications Copyright (c) 2026 Antoine Danion — MIT License

See LICENSE in this plugin's folder for full license terms.
'''

#===============================================================================
# Contributors :
#
# Magno Borgo - mborgo[at]boundaryvfx.com
#     v1.0 - 1.14
#     This script is an extension/inspired by the work of my friend Dubi, original at https://www.nukepedia.com/tools/python/misc/findpath/
#     PayPal : mborgo[at]boundaryvfx.com
#
# Antoine Danion - contact[at]antoinedanion.com
#     v1.15 - v2.1.1
#===============================================================================

#===============================================================================
# Version Log
#
# Please refer to the CHANGELOG.md file in this plugin's folder for newer versions
#
# v2.1.1 (2026/02/25)
# Added a clean logger for better output in the console and easier debugging
#
# v2.1.0 (2025/09/15)
# Optimized the search by checking if the search is already complete
# fixed the search going through system folders like RECYCLE.BIN
# improved the final message to show only 30 nodes and then "and more..." to avoid overwhelming the user
# improved output in the console to show clearly relevant information
#
# v2.0.0 (2025/09/14)
# Added a selective search panel to allow users to choose which node types to include/exclude from the search
# Added several progress bars to give feedback during long operations
# Separated the fix_fonts_errors function into its own function
# Bypassed Nuke Non Commercial limitations
# Largely refactored all the code to improve readability and maintainability
#
# v1.16 (2025/09/14)
# refactored the script to improve readability and maintainability
# changed fnmatch module to re for more precise matching and handling of %0Xd patterns (resolving an issue where the script would match files incorrectly)
# re module is also faster than fnmatch
#
# v1.15 (2025/09/12)
# improved handling of file extentions allowing for more or less than 3 characters (resolving an issue with .cube files)
#
# v1.14 (2014/04/01)
# fixing a font path issue that halts script on Nuke v8
# fix for multiple read nodes with same file reference
#
# v1.13 (2013/07/25)
# Reverted the check order to avoid asking for a directory to search if there was no error on nodes.
#
# v1.12 (2013/02/07)
# added vfield_file to search, should be better implemented later
# automatic fix for wrong font path on text nodes.
#
# v1 (2012/11/23)
# All Nodes that own a file propertie will be searched
# Single os.walk for faster searchs
# Changed the %0d to a more generic search
# Added task progress that can cancel the search
# Added loop breaks to speed script velocity
#===============================================================================

#===============================================================================
# TO DO LIST
# Options to make paths relative from script location
#===============================================================================

# Copyright (c) 2012, Magno Borgo
# All rights reserved.
#
# BSD-style license:
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Magno Borgo or its contributors may be used to
#       endorse or promote products derived from this software without
#       specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
import sys
import os
import time
import re

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
logger = logging.getLogger('ADFixErrors')
logger.setLevel(logging.DEBUG)

# Only add handler if it doesn't exist (prevents duplicate logs on script reload)
if not logger.handlers:
    handler = _DynamicStdoutHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# CONFIGURATION
# ============================================================================

SUPORTED_KNOBS_NAMES = [
    "file",
    "vfield_file",
]

REGEX_FRAME_PATTERN_HASH_PAD_GRP = re.compile(r'(#+)')
REGEX_FRAME_PATTERN_PERCENT_PAD_GRP = re.compile(r'%(\d+)d')
REGEX_FRAME_PATTERN_HASH = re.compile(r'(#+)')
REGEX_FRAME_PATTERN_PERCENT = re.compile(r'(%\d+d)')

def fix_fonts_errors():
    finalmessage = ""

    try:
        errors = [node for node in nuke.allNodes() if node.error() == True]
        fonts_error_nodes = [node for node in errors for n in range(node.getNumKnobs()) if node.knob(n).name() == "font"]
        
        if len(fonts_error_nodes) == 0:
            nuke.message("You don't have any text nodes with font errors!")
            return True
        else:
            fix_fonts_task = nuke.ProgressTask('Fixing fonts')
            for i, node in enumerate(fonts_error_nodes):
                if fix_fonts_task.isCancelled():
                    break
                fix_fonts_task.setMessage('Fixing font on node ' + node.name())
                node.knob("font").setValue("[python nuke.defaultFontPathname()]")
                if finalmessage == "":
                    finalmessage = node.name()
                else:
                    finalmessage += '\n' + node.name()
                fix_fonts_task.setProgress(int(i/len(fonts_error_nodes)*100))
            nuke.message("Fixed fonts on nodes:\n" + finalmessage)
            return True
        
    except Exception as e:
        logger.error(f"Error fixing fonts: {e}")
        return False

def resolve_frame_pattern(path, regex=False):
    if not regex:
        frame = nuke.frame()

        # Remplace toutes les séquences de # par la current frame
        path = REGEX_FRAME_PATTERN_HASH_PAD_GRP.sub(lambda m: f"{frame:0{len(m.group(0))}d}", path)

        # Remplace %0Xd par la current frame
        path = REGEX_FRAME_PATTERN_PERCENT_PAD_GRP.sub(lambda m: f"{frame:0{int(m.group(1))}d}", path)

    else:
        # Remplace toutes les séquences de # par des \d
        path = REGEX_FRAME_PATTERN_HASH_PAD_GRP.sub(lambda m: r'\d' * len(m.group(0)), path)

        # Remplace %0Xd par des \d
        path = REGEX_FRAME_PATTERN_PERCENT_PAD_GRP.sub(lambda m: r'\d' * int(m.group(1)), path)

    return path

def get_searches():
    get_searches_task = nuke.ProgressTask('Getting nodes with missing paths')
    searches = []

    # Sadly we need to use tcl here because nuke.allNodes() is limited to 10 nodes in Nuke Non Commercial
    # Also we are limited to 10 nodes stored in memory so we will avoid using nuke.toNode() or anything that stores nodes in memory
    # This means we will use nuke.tcl() to get node information instead of a node object
    # This is a workaround for Nuke Non Commercial limitations
    
    node_ids = nuke.tcl('nodes').split()
    for i, node_id in enumerate(node_ids):
        node_name = nuke.tcl(f'knob {node_id}.name')
        for knob_name in SUPORTED_KNOBS_NAMES:
            try:
                path = nuke.tcl(f'knob {node_name}.{knob_name}')
            except Exception:
                continue
            if path == None:
                continue
            resolved_path = resolve_frame_pattern(path)
            if path and not os.path.exists(resolved_path):
                searches.append(
                {
                    'node_name': node_name,
                    'node_id': node_id,
                    'node_class': nuke.tcl(f'in {node_name} class'),
                    'knob_name': knob_name,
                    'old_path': path,
                    'old_resolved_path': resolved_path,
                    'old_filename': os.path.basename(path),
                }
            )
                get_searches_task.setMessage(f'Found {node_name}')
        get_searches_task.setProgress(int(i/len(node_ids)*100))

    # sort searches by node name and number if any after the name
    searches.sort(key=lambda x: x['node_name'])

    logger.info(f"Found {len(searches)} nodes with missing file paths.")
    for search in searches:
        logger.info(f"  - {search['node_name']}")
    return searches

def selective_search_panel(searches):
    if len(searches) == 0:
        nuke.message("You don't have any nodes with read file errors!")
        return
    else:
        # get unique node types
        types = list(set(search['node_class'] for search in searches))
        types.sort()

        # create panel
        panel = nuke.Panel("Selective Search Options")

        panel.addFilenameSearch("Search directory", "")

        for type in types:
            panel.addBooleanCheckBox(type, False)

        ret = panel.show()

        # if user pressed OK
        if ret:
            excluded_types = []

            for type in types:
                if not panel.value(type):
                    excluded_types.append(type)

            return {
                'search_path': panel.value("Search directory"),
                'excluded_types': excluded_types,
            }
        else:
            return None

def search_paths(search_path, searches):
    found_paths_task = nuke.ProgressTask('Found paths')
    search_paths_task = nuke.ProgressTask(str(search_path))
    found_searches = 0

    # prepare regex patterns for each search
    for i, search in enumerate(searches):
        search_paths_task.setMessage(f'({i}/{len(searches)})' + 'Preparing search pattern for ' + search['node_name'])

        # split the filename into parts, separating by frame patterns
        fileName_parts = []
        fileName_hash_parts = REGEX_FRAME_PATTERN_HASH.split(search['old_filename'])
        for item in fileName_hash_parts:
            item_percent_parts = REGEX_FRAME_PATTERN_PERCENT.split(item)
            fileName_parts.extend(item_percent_parts)
        
        # reconstruct the regex pattern
        fileName_regex = ''
        for part in fileName_parts:
            if REGEX_FRAME_PATTERN_HASH.match(part) or REGEX_FRAME_PATTERN_PERCENT.match(part):
                part_regex = resolve_frame_pattern(part, regex=True)
            else:
                part_regex = re.escape(part)
            fileName_regex += part_regex
        
        fileName_regex = '^' + fileName_regex + '$'

        regex = re.compile(fileName_regex)

        search['regex'] = regex

    # search through the directory
    walked_dir = 0
    dir_to_walk = 1
    for dirpath, dirnames, filenames in os.walk(search_path):
        # user can Cancel the task if its taking too long
        if search_paths_task.isCancelled() or found_paths_task.isCancelled():
            return -1
        if found_searches == len(searches):
            break

        # Skip system directories
        dir_lower = dirpath.lower()
        if any(skip_dir in dir_lower for skip_dir in [
            '$recycle.bin',
            'recycle.bin',
            'system volume information',
        ]):
            logger.debug(f"Skipping system directory: {dirpath}")
            continue
        
        dir_to_walk += len(filenames)
        search_paths_task.setMessage('Searching ' + dirpath )

        for file in filenames:
            # check if any search matches the current directory
            matched_searches = []
            for search in searches:
                if 'new_path' not in search:
                    if search['regex'].match(file):
                        matched_searches.append(search)
            
            # if matches found, update dictionary
            if len(matched_searches) > 0:
                for search in matched_searches:                
                    reformatPath = dirpath.replace("\\", "/")
                    search['new_path'] = reformatPath +'/'+ search['old_filename']
                    found_searches += 1

            walked_dir += 1

        search_paths_task.setProgress(int(walked_dir/dir_to_walk*100))
        found_paths_task.setMessage(f'Found {found_searches} paths')
        found_paths_task.setProgress(int(found_searches/len(searches)*100))
    return 1

def update_paths(searches):
    # update paths in nodes
    for search in searches:
        if 'new_path' in search:
            nuke.tcl(f'knob {search["node_name"]}.{search["knob_name"]} "{search["new_path"]}"')
            logger.info(f'Successfully updated path for {search["node_name"]}: {search["new_path"]}')
        else:
            logger.warning(f'Failed to find path for {search["node_name"]}: {search["old_path"]}')

    # prepare final message
    found = [search for search in searches if 'new_path' in search]
    not_found = [search for search in searches if 'new_path' not in search]
    found_message = f"Found {len(found)} files."
    not_found_message = f"\nCould not find {len(not_found)} files:\n"
    and_more = False
    more_message = ''
    for i, search in enumerate(not_found):
        if i < 30:
            not_found_message = not_found_message + "\n" + f"MISSING: {search['node_name']} - {search['knob_name']}"
        else:
            and_more = True
            break
    if and_more == True:
        more_message = f"And {len([search for search in searches if 'new_path' not in search])-60} more..."

    return {
        'found_message': found_message,
        'not_found_message': not_found_message,
        'more_message': more_message,
    }

def fix_paths_errors(selective=False):
    finalmessage = ""
    time_message = ""

    # get nodes with supported knobs and errors
    searches = get_searches()
    
    if selective:
        # exclude node types based on user selection
        result = selective_search_panel(searches)
        if result is not None:
            search_path = result['search_path']
            excluded_types = result['excluded_types']
            searches = [search for search in searches if search['node_class'] not in excluded_types]
        else:
            return
    else:
        search_path = nuke.getFilename('Search directory', " ", type = 'open')
        excluded_types = [
            "Write",
        ]
        searches = [search for search in searches if search['node_class'] not in excluded_types]

    if len(searches) == 0:
        if selective:
            finalmessage = "You don't have any selected node types with read file errors!"
        else:
            finalmessage = "You don't have any nodes with read file errors!"
    else:
        if search_path == '' or search_path == None:
            finalmessage = "You didn't select a directory to search!"
        else:
            start_time = time.time()
            search_paths_result = search_paths(search_path, searches)
            if search_paths_result == 1:
                update_paths_result = update_paths(searches)

                # prepare final message
                finalmessage = update_paths_result['found_message'] + '\n\n' + update_paths_result['not_found_message'] + '\n' + update_paths_result['more_message']

                # prepare time elapsed message
                elapsed = time.time() - start_time
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                time_message = f"\n\nTime elapsed: {minutes} min {seconds:.2f} sec"
            else:
                finalmessage = "Search cancelled by user."
            
    finalmessage = finalmessage + time_message
    nuke.message(finalmessage)