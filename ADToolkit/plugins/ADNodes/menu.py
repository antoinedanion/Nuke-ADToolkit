import nuke

adtools = nuke.menu('Nodes').addMenu('ADTools')
adtools.addCommand('ADMattepaint', 'nuke.createNode("ADMattepaint_1_1_2")', 'alt+m')