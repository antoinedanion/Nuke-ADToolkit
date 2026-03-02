import nuke

nuke.pluginAddPath('./gizmos')
nuke.pluginAddPath('./python')

from ad_copy_parameters import knob_changed

nuke.addKnobChanged(knob_changed)