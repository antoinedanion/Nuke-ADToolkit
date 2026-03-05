import nuke

from ad_clone_group import clone_group

nuke.menu("Nuke").addCommand("ADToolkit/Clone Group (linked)", "clone_group()", "alt+k")
