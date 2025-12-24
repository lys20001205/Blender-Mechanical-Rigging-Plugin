import bpy
from . import utils

class MECH_RIG_OT_AutoRig(bpy.types.Operator):
    """Detects hierarchy, handles collections, mirroring, and generates a rigid mechanical rig."""
    bl_idname = "mech_rig.auto_rig"
    bl_label = "Auto Rig Hierarchy"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        symmetric_origin = context.scene.mech_rig_symmetric_origin
        
        try:
            rig_data = utils.analyze_hierarchy(selected_objects)
            processed_objects = utils.process_meshes(context, rig_data, symmetric_origin)
            armature_obj = utils.create_armature(context, rig_data, symmetric_origin)
            utils.finalize_mesh_and_skin(context, processed_objects, armature_obj)
            
            # Select the new armature to show UI
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = armature_obj
            armature_obj.select_set(True)
            
            self.report({'INFO'}, "Rigging Complete! Configure controls in panel.")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Rigging Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class MECH_RIG_OT_AddControls(bpy.types.Operator):
    """Apply the configured control shapes and IK constraints."""
    bl_idname = "mech_rig.add_controls"
    bl_label = "Apply Controls"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select the generated Armature.")
            return {'CANCELLED'}
        
        try:
            utils.apply_controls(context, obj)
            self.report({'INFO'}, "Controls Applied!")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Control Application Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(MECH_RIG_OT_AutoRig)
    bpy.utils.register_class(MECH_RIG_OT_AddControls)

def unregister():
    bpy.utils.unregister_class(MECH_RIG_OT_AutoRig)
    bpy.utils.unregister_class(MECH_RIG_OT_AddControls)
