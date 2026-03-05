import nuke

from ad_open_in_explorer import open_in_explorer

menubar = nuke.menu("Nuke")
a = menubar.addMenu("ADToolkit")
a.addCommand("Open in Explorer", "open_in_explorer()", "Ctrl+E")

