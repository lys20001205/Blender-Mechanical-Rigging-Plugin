bl_info = {
    "name": "Mechanical Rigger",
    "author": "Jules",
    "version": (1, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > Mechanical Rigger",
    "description": "Auto-rig mechanical hierarchies for Unreal Engine. Detects 'Hinge_' naming, handles '_Mirrored' collections, and generates IK/FK controls.",
    "category": "Rigging",
}

import sys
import bpy

# --- Remote Debugging Setup ---
# This looks for the debug server running in Rider.
try:
    import pydevd_pycharm
    # Set suspend=False so Blender doesn't freeze on startup if the debugger isn't attached
    pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
except ImportError:
    # This is normal for users who don't have the debugger installed
    pass
except ConnectionRefusedError:
    # This is normal if you (the dev) simply haven't hit "Debug" in Rider yet
    print("Mechanical Rigger: Debug server not found. Continuing execution.")
except Exception as e:
    print(f"Mechanical Rigger: Debug connection failed: {e}")

from . import operators
from . import ui
from . import utils

def register():
    operators.register()
    ui.register()

def unregister():
    ui.unregister()
    operators.unregister()
