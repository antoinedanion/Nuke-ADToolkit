import nuke

menu = nuke.menu('Nuke').addMenu('Tools')
menu.addCommand('Copy with inputs', 'import ad_copy_paste; ad_copy_paste.copy()', 'Ctrl+C')
menu.addCommand('Paste with inputs', 'import ad_copy_paste; ad_copy_paste.paste()', 'Ctrl+Shift+V')