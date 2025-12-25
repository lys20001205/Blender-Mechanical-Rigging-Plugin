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

# --- Developer Utilities ---
class MECH_RIG_OT_ReloadAddon(bpy.types.Operator):
    """Reloads the addon scripts without restarting Blender"""
    bl_idname = "mech_rig.reload_addon"
    bl_label = "Reload Addon"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import importlib
        from . import operators, ui, utils

        print("\n--- Reloading Mechanical Rigger ---")

        # 1. Unregister old classes to prevent 'class already registered' errors
        try:
            ui.unregister()
            operators.unregister()
        except Exception as e:
            print(f"Unregister warning: {e}")

        # 2. Reload modules in dependency order
        # Utils usually has no dependencies, so it goes first.
        importlib.reload(utils)
        # Operators depend on utils
        importlib.reload(operators)
        # UI depends on operators/utils
        importlib.reload(ui)

        # 3. Register new classes
        operators.register()
        ui.register()

        print("--- Reload Complete ---\n")
        self.report({'INFO'}, "Mechanical Rigger Reloaded")
        return {'FINISHED'}

def register():
    operators.register()
    ui.register()
    bpy.utils.register_class(MECH_RIG_OT_ReloadAddon)

def unregister():
    bpy.utils.unregister_class(MECH_RIG_OT_ReloadAddon)
    ui.unregister()
    operators.unregister()