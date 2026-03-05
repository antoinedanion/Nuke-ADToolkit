import nuke

adtools = nuke.menu('Nodes').addMenu('ADToolkit')
adtools.addCommand('ADMattepaint', 'nuke.createNode("ADMattepaint_1_1_3")', 'alt+m')