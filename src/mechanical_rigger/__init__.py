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
try:
    import pydevd_pycharm
    # Make sure the port matches your Rider "Python Debug Server" configuration
    # suspend=False allows Blender to start without waiting for a breakpoint
    pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
    print("Mechanical Rigger: Connected to remote debugger.")
except ImportError:
    # Debug module not found - normal for end users
    pass
except ConnectionRefusedError:
    # Debug server not running - normal for devs not currently debugging
    print("Mechanical Rigger: Debug server not found. Continuing execution.")
except Exception as e:
    print(f"Mechanical Rigger: Debug connection failed: {e}")

from . import operators
from . import ui

# --- Developer Utilities ---
class MECHANIG_OT_reload_addon(bpy.types.Operator):
    """Reloads the addon scripts without restarting Blender"""
    bl_idname = "mechanig.reload_addon"
    bl_label = "Reload Addon"
    
    def execute(self, context):
        import importlib
        from . import operators, ui
        
        # Unregister old classes first
        ui.unregister()
        operators.unregister()
        
        # Reload modules
        importlib.reload(operators)
        importlib.reload(ui)
        
        # Register new classes
        operators.register()
        ui.register()
        
        self.report({'INFO'}, "Mechanical Rigger Reloaded")
        return {'FINISHED'}

def register():
    operators.register()
    ui.register()
    bpy.utils.register_class(MECHANIG_OT_reload_addon)

def unregister():
    bpy.utils.unregister_class(MECHANIG_OT_reload_addon)
    ui.unregister()
    operators.unregister()
