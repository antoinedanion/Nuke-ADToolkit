import os
import nuke

# DEFAULT PATHS
nuke.pluginAddPath('./gizmos')
nuke.pluginAddPath('./python')

# PLUGINS FOLDER
script_dir = os.path.dirname(os.path.abspath(__file__))
plugins_dir = os.path.join(script_dir, "plugins")

print(f"[ADToolkit] Importing plugins from {plugins_dir}:")

for subdir in os.listdir(plugins_dir):
    subdirPath = os.path.join(plugins_dir,subdir)
    if os.path.isdir(subdirPath):
        try:
            nuke.pluginAddPath(f'./plugins/{subdir}')
            print(f"[ADToolkit] SUCCESS importing {subdir}")
        except Exception as e:
            print(f"[ADToolkit] WARNING : Failed import {subdir}")
            print(e)
    else:
        pass

print('')