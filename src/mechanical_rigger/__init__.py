bl_info = {
    "name": "Mechanical Rigger",
    "author": "Jules",
    "version": (1, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > Mechanical Rigger",
    "description": "Auto-rig mechanical hierarchies for Unreal Engine. Detects 'Hinge_' naming, handles '_Mirrored' collections, and generates IK/FK controls.",
    "category": "Rigging",
}

from . import operators
from . import ui

def register():
    operators.register()
    ui.register()

def unregister():
    ui.unregister()
    operators.unregister()
