"""
ADCloneGroup Core Module

Version 1.0.1

Copyright (c) 2026 Antoine Danion
MIT License - see LICENSE in this plugin's folder
"""

# =============================================================================

# When Alt+K is pressed on a Group node, creates an independent copy of the group
# (preserving its internal node graph) and marks it as a clone by storing the
# source group name in a hidden knob '_adclonegroup_clone_source'.

# A global nuke.addKnobChanged callback (sync_knob_changed) watches all knob
# changes. When the changed node has the '_adclonegroup_source_name' hidden knob it is
# a registered source; the callback propagates the value to all clones and
# tracks renames.

# For non-Group nodes, falls back to standard Nuke clone behaviour (nuke.clone).

# It uses TCL commands to ensure compatibility with Nuke Indie and Non-Commercial versions.

# =============================================================================

import logging
import sys

import nuke


# ============================================================================
# LOGGING SETUP
# ============================================================================

class _DynamicStdoutHandler(logging.StreamHandler):
    """Always writes to the current sys.stdout, even if Nuke replaces it."""
    def emit(self, record):
        self.stream = sys.stdout
        super().emit(record)

logger = logging.getLogger('ADCloneGroup')
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = _DynamicStdoutHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# CONSTANTS
# ============================================================================

# Hidden knob on the clone - stores the source group's name
_SOURCE_KNOB = '_adclonegroup_clone_source'

# Hidden knob on the source - stores its own current name for rename tracking
_SOURCE_REGISTERED_NAME = '_adclonegroup_source_name'

# Hidden knob on the source - space-separated list of all clone names
_CLONE_LIST_KNOB = '_adclonegroup_clone_list'

# Sentinel to avoid re-injecting scripts
_SENTINEL = '# [ADCloneGroup]'

# Knobs ignored by the group-level sync script ('name' handled separately for rename tracking)
_GROUP_SKIP_KNOBS = frozenset({
    'xpos',
	'ypos',
	'selected',
	'hide_input',
	'label',
    'note_font',
	'note_font_size',
	'note_font_color',
	'tile_color',
    'gl_color',
	'postage_stamp',
	'bookmark',
	'indicators',
	'cached',
    'disable',
	'dope_sheet',
	'onCreate',
	'onDestroy',
	'knobChanged',
    'updateUI',
	'autolabel',
	'help',
    'show_group_view',
    'group_view_position',
    'disable_group_view',
	'_adclonegroup_clone_source',
	'_adclonegroup_source_name',
    '_adclonegroup_clone_list',
})


# Knobs ignored by the internal-node sync script ('name' also skipped here, unlike group script)
_SYNC_SKIP_KNOBS = _GROUP_SKIP_KNOBS | {'name'}

# Injected into each internal node's knobChanged on ALL family members.
# Bidirectional: any family member internal node change syncs all siblings.
# TCL context is always "inside the group", so:
#   parent          = the containing group node
#   parent.parent   = root (where all peer groups live)
_EMBEDDED_SYNC_SCRIPT = f'''
# [ADCloneGroup]
try:
    _k = nuke.thisKnob()
    _n = nuke.thisNode()
    if _k and _n:
        _kn = _k.name()
        _skip = {_SYNC_SKIP_KNOBS}
        if _kn in _skip:
            pass
        else:
            _full = _n.fullName()
            if '.' not in _full:
                pass
            else:
                _parts = _full.split('.')
                _gname = _parts[0]
                _nname = _full.split('.', 1)[1]
                _depth = len(_parts)
                # _group_prefix reaches the top-level group's knobs from this node
                # _root_prefix  reaches root from this node
                # e.g. depth=2 (Group.Node):           group=parent.  root=parent.parent.
                #      depth=3 (Group.Sub.Node):        group=parent.parent.  root=parent.parent.parent.
                _group_prefix = 'parent.' * (_depth - 1)
                _root_prefix  = 'parent.' * _depth
                _fam = ''
                try:
                    _fam = nuke.tcl('value ' + _group_prefix + '_adclonegroup_clone_source')
                except Exception:
                    pass
                if not _fam:
                    try:
                        _src = nuke.tcl('value ' + _group_prefix + '_adclonegroup_source_name')
                        if _src:
                            _fam = _gname
                    except Exception:
                        pass
                if not _fam:
                    pass
                else:
                    try:
                        nuke.tcl('if {{[info exists _adcg_sync]}} {{error "skip"}}')
                    except Exception:
                        pass  # loop guard active
                    else:
                        nuke.tcl('set _adcg_sync 1')
                        try:
                            try:
                                _arr = _k.arraySize()
                            except Exception:
                                _arr = 1
                            if _arr > 1:
                                _vs = ' '.join(str(_k.value(_i)) for _i in range(_arr))
                            else:
                                _v = _k.value()
                                _vs = _v if isinstance(_v, str) else str(_v)
                            try:
                                _cl = nuke.tcl('value ' + _root_prefix + _fam + '._adclonegroup_clone_list')
                            except Exception:
                                _cl = ''
                            # Self-register: if this group is a clone but not in the
                            # source's clone list (e.g. it was copy-pasted), add it now.
                            if _fam != _gname and _gname not in _cl.split():
                                _cl_new = (_cl.strip() + ' ' + _gname).strip()
                                try:
                                    nuke.tcl('knob ' + _root_prefix + _fam + '._adclonegroup_clone_list {{' + _cl_new + '}}')
                                    _cl = _cl_new
                                except Exception as _re:
                                    print('[ADCG-sync] self-register FAIL: %r' % _re)
                            _siblings = []
                            if _fam != _gname:
                                _siblings.append(_fam)
                            for _cn in _cl.split():
                                if _cn and _cn != _gname:
                                    _siblings.append(_cn)
                            for _sg in _siblings:
                                _cmd = 'knob ' + _root_prefix + _sg + '.' + _nname + '.' + _kn + ' {{' + _vs + '}}'
                                try:
                                    nuke.tcl(_cmd)
                                except Exception as _e:
                                    print('[ADCG-sync] sync FAIL %r: %r' % (_cmd, _e))
                        finally:
                            nuke.tcl('unset _adcg_sync')
except Exception as _top_e:
    import traceback as _tb
    print('[ADCG-sync] ERROR: %r' % _top_e)
    _tb.print_exc()
'''

# Injected into the source group's own knobChanged.
# Bidirectional: source or clone Group-level knob change syncs all siblings.
# TCL context for a group's knobChanged: the group IS at root level, so:
#   parent   = root  (where all peer groups live)
# (contrast with internal-node scripts where parent=group, parent.parent=root)
_EMBEDDED_GROUP_SCRIPT = f'''
# [ADCloneGroup-group]
try:
    _k = nuke.thisKnob()
    _n = nuke.thisNode()
    if _k and _n:
        _kn = _k.name()
        _skip = {_GROUP_SKIP_KNOBS}
        _src_knob = _n.knob('_adclonegroup_source_name')
        _cln_knob = _n.knob('_adclonegroup_clone_source')
        if _cln_knob and _cln_knob.value():
            _src_knob = None
        if not (_src_knob or _cln_knob):
            pass
        else:
            if _kn in _skip:
                pass
            elif _kn == 'name' and _src_knob:
                _old = _src_knob.value()
                _new = _n.name()
                if _old and _old != _new:
                    # Use TCL to iterate root-level nodes and update clone source knobs
                    # parent = root for a group-level knobChanged
                    for _rh in nuke.tcl('nodes parent').split():
                        try:
                            _cv = nuke.tcl('value ' + _rh + '._adclonegroup_clone_source')
                            if _cv == _old:
                                nuke.tcl('knob ' + _rh + '._adclonegroup_clone_source {{' + _new + '}}')
                        except Exception:
                            pass
                    _src_knob.setValue(_new)
            else:
                try:
                    nuke.tcl('if {{[info exists _adcg_sync]}} {{error "skip"}}')
                except Exception:
                    pass  # loop guard active
                else:
                    nuke.tcl('set _adcg_sync 1')
                    try:
                        _nn = _n.name()
                        _fam = _nn if _src_knob else (_cln_knob.value() if _cln_knob else '')
                        if not _fam:
                            pass
                        else:
                            try:
                                _arr = _k.arraySize()
                            except Exception:
                                _arr = 1
                            if _arr > 1:
                                _vs = ' '.join(str(_k.value(_i)) for _i in range(_arr))
                            else:
                                _v = _k.value()
                                _vs = _v if isinstance(_v, str) else str(_v)
                            # parent = root level for group knobChanged
                            try:
                                _cl = nuke.tcl('value parent.' + _fam + '._adclonegroup_clone_list')
                            except Exception:
                                _cl = ''
                            # Self-register: if this node is a clone but not in the
                            # source's clone list (e.g. it was copy-pasted), add it now.
                            if _cln_knob and _nn not in _cl.split():
                                _cl_new = (_cl.strip() + ' ' + _nn).strip()
                                try:
                                    nuke.tcl('knob parent.' + _fam + '._adclonegroup_clone_list {{' + _cl_new + '}}')
                                    _cl = _cl_new
                                except Exception as _re:
                                    print('[ADCG-group] self-register FAIL: %r' % _re)
                            _siblings = []
                            if _fam != _nn:
                                _siblings.append(_fam)
                            for _cn in _cl.split():
                                if _cn and _cn != _nn:
                                    _siblings.append(_cn)
                            for _sg in _siblings:
                                _cmd = 'knob parent.' + _sg + '.' + _kn + ' {{' + _vs + '}}'
                                try:
                                    nuke.tcl(_cmd)
                                except Exception as _e:
                                    print('[ADCG-group] sync FAIL %r: %r' % (_cmd, _e))
                    finally:
                        nuke.tcl('unset _adcg_sync')
except Exception as _top_e:
    import traceback as _tb
    print('[ADCG-group] ERROR: %r' % _top_e)
    _tb.print_exc()
'''


# ============================================================================
# MAIN
# ============================================================================

def clone_group():
    """
    Clone the selected Group by copying its internal graph and tagging the copy
    with '_adclonegroup_clone_source'. The global sync_knob_changed callback then handles
    value propagation and rename tracking.
    Falls back to standard nuke.clone() for non-Group nodes.
    """

    logger.info("Starting clone operation...")
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
    orig_node = nuke.toNode(node_name)

    if orig_node is None:
        logger.error(f"Could not resolve node '{node_name}'.")
        return

    # If the selected node is itself a clone, resolve to the real source so
    # the new copy joins the same family instead of forking a new one.
    source_knob = orig_node.knob(_SOURCE_KNOB)
    if source_knob and source_knob.value():
        real_source_name = source_knob.value()
        real_source = nuke.toNode(real_source_name)
        if real_source is not None:
            logger.info(f"'{node_name}' is a clone - using source '{real_source_name}' instead.")
            orig_node = real_source
            node_name = real_source_name

    # Gizmos pass the begin()/end() test but have protected internals - fall back to
    # standard clone for them. Only true Group nodes support internal injection.
    if orig_node.Class() != 'Group':
        logger.info(f"'{node_name}' is a {orig_node.Class()} (not a Group), falling back to standard clone.")
        try:
            nuke.clone(orig_node)
            logger.info(f"Standard clone of '{node_name}' succeeded.")
        except Exception as e:
            logger.error(f"Standard clone failed: {e}")
        return

    # Check node supports entering its context (sanity check for Group).
    try:
        orig_node.begin()
        orig_node.end()
    except Exception:
        logger.info(f"'{node_name}' does not support begin/end, falling back to standard clone.")
        try:
            nuke.clone(orig_node)
            logger.info(f"Standard clone of '{node_name}' succeeded.")
        except Exception as e2:
            logger.error(f"Standard clone failed: {e2}")
        return

    logger.info(f"Cloning group '{node_name}'...")

    # Capture all node names before paste so we can identify the new node afterwards.
    # TCL handles only support reads reliably; writes require the node name.
    _before_names = set()
    _raw_nodes = nuke.tcl('nodes') or ''
    for _h in _raw_nodes.split():
        _hn = nuke.tcl('knob ' + _h + '.name')
        if _hn:
            _before_names.add(_hn)

    # Isolate selection to only this group using names (not handles) for the write.
    for _hn in _before_names:
        nuke.tcl('knob ' + _hn + '.selected false')
    nuke.tcl('knob ' + node_name + '.selected true')

    # Copy / paste to create an independent copy (own internal graph)
    nuke.nodeCopy('%clipboard%')
    nuke.nodePaste('%clipboard%')

    # Identify the pasted node by finding a name that wasn't present before.
    _after_raw = nuke.tcl('nodes') or ''
    new_node_name = None
    for _h in _after_raw.split():
        _hn = nuke.tcl('knob ' + _h + '.name')
        if _hn and _hn not in _before_names:
            new_node_name = _hn
            break

    if not new_node_name:
        logger.error('nodePaste produced no new node.')
        return

    new_node = nuke.toNode(new_node_name)
    if new_node is None:
        logger.error(f"Could not resolve pasted node '{new_node_name}'.")
        return

    # The paste is a copy of the source - strip knobs that must only live on source.
    for _stale_knob in (_SOURCE_REGISTERED_NAME, _CLONE_LIST_KNOB):
        try:
            _sk = new_node.knob(_stale_knob)
            if _sk is not None:
                new_node.removeKnob(_sk)
        except Exception as _e:
            logger.warning(f"Could not remove stale knob '{_stale_knob}' from clone: {_e}")

    # Tag the clone with the source group name
    try:
        source_tag = new_node.knob(_SOURCE_KNOB)
        if source_tag is None:
            source_tag = nuke.String_Knob(_SOURCE_KNOB, _SOURCE_KNOB)
            new_node.addKnob(source_tag)
            source_tag.setFlag(nuke.INVISIBLE)
        source_tag.setValue(node_name)
    except Exception as e:
        logger.error(f"Failed to tag clone with source name: {e}")
        return

    # Register the source's current name on itself for rename tracking
    try:
        reg_knob = orig_node.knob(_SOURCE_REGISTERED_NAME)
        if reg_knob is None:
            reg_knob = nuke.String_Knob(_SOURCE_REGISTERED_NAME, _SOURCE_REGISTERED_NAME)
            orig_node.addKnob(reg_knob)
            reg_knob.setFlag(nuke.INVISIBLE)
        reg_knob.setValue(node_name)
    except Exception as e:
        logger.warning(f"Could not register source name for rename tracking: {e}")

    # Maintain a space-separated list of clone names on the source so embedded
    # sync scripts can find siblings without iterating root nodes.
    try:
        _list_knob = orig_node.knob(_CLONE_LIST_KNOB)
        if _list_knob is None:
            _list_knob = nuke.String_Knob(_CLONE_LIST_KNOB, _CLONE_LIST_KNOB)
            orig_node.addKnob(_list_knob)
            _list_knob.setFlag(nuke.INVISIBLE)
            _existing_list = []
        else:
            _existing_list = [x for x in (_list_knob.value() or '').split() if x]
        if new_node_name not in _existing_list:
            _existing_list.append(new_node_name)
        _list_knob.setValue(' '.join(_existing_list))
    except Exception as e:
        logger.warning(f"Could not update clone list on source: {e}")

    # Inject group-level and internal-node scripts into both source and clone.
    # The clone is a copy made before injection, so it needs scripts too.
    for _target_name in (node_name, new_node_name):
        # Group-level knobChanged - always strip and re-inject current script.
        try:
            _target_node = orig_node if _target_name == node_name else new_node
            _kc_knob = _target_node.knob('knobChanged')
            _existing_kc = _kc_knob.value() if _kc_knob else ''
            if '# [ADCloneGroup-group]' in _existing_kc:
                _existing_kc = _existing_kc[:_existing_kc.index('# [ADCloneGroup-group]')].rstrip()
            _new_kc = (_existing_kc + '\n' + _EMBEDDED_GROUP_SCRIPT).lstrip()
            nuke.tcl(f'knob {_target_name}.knobChanged {{{_new_kc}}}')
            logger.debug(f"Injected group script into '{_target_name}'.knobChanged.")
        except Exception as e:
            logger.warning(f"Could not inject group script into '{_target_name}': {e}")

        # Internal nodes' knobChanged - injected RECURSIVELY into all descendants.
        # Promoted knobs fire the knobChanged of the originating node (which may be
        # deeply nested), so we must reach every level, not just direct children.
        def _inject_recursive(parent_handle, depth=1):
            try:
                _int_nodes_raw = nuke.tcl(f'nodes {parent_handle}') or ''
            except Exception as _ne:
                logger.warning(f"Could not list nodes of '{parent_handle}': {_ne}")
                return
            for _handle in _int_nodes_raw.split():
                try:
                    _existing = nuke.tcl(f'knob {_handle}.knobChanged') or ''
                except Exception as _he:
                    logger.warning(f"Could not read knobChanged from '{_handle}': {_he}")
                    _existing = ''
                _had_sentinel = _SENTINEL in _existing
                if _had_sentinel:
                    _existing = _existing[:_existing.index(_SENTINEL)].rstrip()
                _new_int = (_existing + '\n' + _EMBEDDED_SYNC_SCRIPT).lstrip()
                try:
                    nuke.tcl(f'knob {_handle}.knobChanged {{{_new_int}}}')
                except Exception as _ie:
                    logger.warning(f"Could not inject sync script into '{_handle}': {_ie}")
                # Recurse into sub-groups
                _children_raw = ''
                try:
                    _children_raw = nuke.tcl(f'nodes {_handle}') or ''
                except Exception:
                    pass
                if _children_raw.strip():
                    _inject_recursive(_handle, depth + 1)
        try:
            _inject_recursive(_target_name)
        except Exception as e:
            logger.warning(f"Could not inject sync scripts into '{_target_name}' internals: {e}")

    logger.info(f"Done: '{new_node_name}' is now a clone of '{node_name}'.")
