ADToolkit is a Nuke plugin bundle that includes several sub-plugins.
Some of them solve some of Nuke's most impacting QoL issues, and others add nodes and functionality to boost productivity.



# Installation

Add the `ADToolkit` folder to your Nuke plugin path. In your `init.py`:

```python
import nuke
nuke.pluginAddPath('./plugins/ADToolkit')
```

All sub-plugins are loaded automatically by the toolkit.


# Plugins

- [ADCopyParameters](#adcopyparameters)
- [ADCopyPaste](#adcopypaste)
- [ADFixErrors](#adfixxerrors)
- [ADNodes](#adnodes)



## ADCopyParameters

Copies a knob value from one node to all other selected nodes by holding `Alt` and clicking the knob.

### How to

1. Select all target nodes in the node graph.
2. Hold `Alt` and click any knob on a node.
3. The knob value is propagated to the matching knob on every other selected node.



## ADCopyPaste

An enhanced copy/paste for Nuke that preserves node input connections, even when the upstream nodes are not part of the selection.

### Shortcuts

| Action | Shortcut |
|---|---|
| Copy | `Ctrl+C` |
| Paste | `Ctrl+V` |
| Paste with inputs | `Ctrl+Shift+V` |


## ADFixErrors

Finds and fixes broken file paths and font errors across an entire Nuke script. Originally by Magno Borgo, extended by Antoine Danion from v1.15 onward.

### Menu

`Fix Errors` menu in the Nuke menu bar.

| Command | Description |
|---|---|
| Find all missing files | Scans all nodes for broken file paths and attempts to relocate the files automatically. |
| Find missing files (Selective) | Same as above, but opens a panel to include/exclude specific node types from the search. |
| Replace missing fonts by default font | Resets the font knob on any Text node with a font error to Nuke's default font. |



## ADNodes

A collection of custom Nuke gizmos and nodes.

### ADMattepaint

Shortcut: `Alt+M`

A self-contained mattepaint workflow node that manages the full round-trip between Nuke and Photoshop.






## Author

Antoine Danion — contact@antoinedanion.com
