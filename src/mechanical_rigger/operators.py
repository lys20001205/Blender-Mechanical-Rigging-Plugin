import bpy
import mathutils
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
            utils.finalize_mesh_and_skin(context, processed_objects, armature_obj, selected_objects)

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

class MECH_RIG_OT_EditWidgetTransform(bpy.types.Operator):
    """Create a temporary object to visually edit the widget's transform."""
    bl_idname = "mech_rig.edit_widget_transform"
    bl_label = "Edit Widget Transform"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE' or obj.mode != 'POSE':
            self.report({'ERROR'}, "Select an Armature in Pose Mode.")
            return {'CANCELLED'}

        pbone = context.active_pose_bone
        if not pbone or not pbone.custom_shape:
            self.report({'ERROR'}, "Select a bone with a custom shape.")
            return {'CANCELLED'}

        # Calculate current world matrix of the custom shape
        # Shape Matrix = Bone Matrix @ Custom Shape Transform
        # Custom Shape Transform is built from location, rotation, scale props

        # NOTE: pbone.custom_shape_transform is a matrix property in older API?
        # In recent Blender, it's properties: custom_shape_translation, _rotation_euler, _scale_xyz.

        # Build Local Transform Matrix
        t = mathutils.Matrix.Translation(pbone.custom_shape_translation)
        r = pbone.custom_shape_rotation_euler.to_matrix().to_4x4()
        s = mathutils.Matrix.Diagonal(pbone.custom_shape_scale_xyz).to_4x4()

        # Order: Translation * Rotation * Scale (Standard Blender)
        # Verify order: usually T * R * S
        local_mat = t @ r @ s

        # World Matrix
        # Bone Matrix (Armature Space)
        bone_mat = pbone.matrix
        # Armature World Matrix
        arm_mat = obj.matrix_world

        final_mat = arm_mat @ bone_mat @ local_mat

        # Create Temp Object
        mesh = pbone.custom_shape.data.copy() # Copy mesh to avoid editing the shared original
        temp_obj = bpy.data.objects.new(f"TEMP_WIDGET_{pbone.name}", mesh)
        context.collection.objects.link(temp_obj)

        temp_obj.matrix_world = final_mat
        temp_obj.show_wire = True
        temp_obj.display_type = 'WIRE'

        # Store metadata
        temp_obj["mech_temp_type"] = "WIDGET_EDIT"
        temp_obj["mech_armature"] = obj.name
        temp_obj["mech_bone"] = pbone.name

        # Switch to Object Mode to handle object selection
        bpy.ops.object.mode_set(mode='OBJECT')

        # Select Temp Object
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = temp_obj
        temp_obj.select_set(True)

        self.report({'INFO'}, "Edit the widget transform, then click 'Apply Custom Transform'.")
        return {'FINISHED'}

class MECH_RIG_OT_ApplyWidgetTransform(bpy.types.Operator):
    """Apply the temporary object's transform to the bone's custom shape settings."""
    bl_idname = "mech_rig.apply_widget_transform"
    bl_label = "Apply Custom Transform"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        temp_obj = context.active_object
        if not temp_obj or temp_obj.get("mech_temp_type") != "WIDGET_EDIT":
            self.report({'ERROR'}, "Active object is not a widget edit object.")
            return {'CANCELLED'}

        arm_name = temp_obj.get("mech_armature")
        bone_name = temp_obj.get("mech_bone")

        arm_obj = bpy.data.objects.get(arm_name)
        if not arm_obj:
            self.report({'ERROR'}, "Armature not found.")
            return {'CANCELLED'}

        pbone = arm_obj.pose.bones.get(bone_name)
        if not pbone:
            self.report({'ERROR'}, "Bone not found.")
            return {'CANCELLED'}

        # Calculate new local parameters
        # Final = Arm @ Bone @ Local
        # Local = (Arm @ Bone)^-1 @ Final

        parent_mat = arm_obj.matrix_world @ pbone.matrix
        local_mat = parent_mat.inverted() @ temp_obj.matrix_world

        loc, rot, scale = local_mat.decompose()

        # Apply to Bone
        pbone.custom_shape_translation = loc
        pbone.custom_shape_rotation_euler = rot.to_euler()
        pbone.custom_shape_scale_xyz = scale

        # Save to settings
        settings = pbone.mech_rig_settings
        settings.override_transform = True
        settings.visual_location = loc
        settings.visual_rotation = rot.to_euler()
        settings.visual_scale = scale

        # Cleanup
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        # Note: We copied the mesh data, should we remove that too?
        # Yes, if we don't want to leak meshes.
        # But 'remove' on object doesn't remove mesh if users=0 immediately?
        # Safe to leave mesh to GC or remove if single user.
        # Let's rely on Blender's orphan cleanup or just reuse standard shapes next time.

        # Restore Selection
        context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')

        # Ensure bone is active
        arm_obj.data.bones.active = pbone.bone

        self.report({'INFO'}, "Widget Transform Applied.")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(MECH_RIG_OT_AutoRig)
    bpy.utils.register_class(MECH_RIG_OT_AddControls)
    bpy.utils.register_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.register_class(MECH_RIG_OT_ApplyWidgetTransform)

def unregister():
    bpy.utils.unregister_class(MECH_RIG_OT_AutoRig)
    bpy.utils.unregister_class(MECH_RIG_OT_AddControls)
    bpy.utils.unregister_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.unregister_class(MECH_RIG_OT_ApplyWidgetTransform)
