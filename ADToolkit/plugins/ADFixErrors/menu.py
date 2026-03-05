import nuke

from ad_fix_errors import (
    fix_paths_errors,
    fix_fonts_errors,
)

menubar = nuke.menu("Nuke")
a = menubar.addMenu("ADToolkit/Fix Errors")
a.addCommand('Find all missing files', 'fix_paths_errors(selective=False)')
a.addCommand('Find missing files (Selective)', 'fix_paths_errors(selective=True)')
a.addCommand('Replace missing fonts by default font', 'fix_fonts_errors()')