import nuke
from ad_copy_parameters import copy_to_selected

nuke.menu('Animation').addCommand('Copy to Selected', "copy_to_selected()")