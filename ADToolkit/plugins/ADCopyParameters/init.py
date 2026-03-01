import nuke

nuke.pluginAddPath('./gizmos')
nuke.pluginAddPath('./python')

from ad_copy_parameters import copy_parameters

nuke.addKnobChanged(copy_parameters)