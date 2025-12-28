import bpy
import mathutils
from . import utils

class MECH_RIG_OT_ValidateHierarchy(bpy.types.Operator):
    """Checks the selected hierarchy for common errors before rigging."""
    bl_idname = "mech_rig.validate_hierarchy"
    bl_label = "Validate Hierarchy"
    bl_options = {'REGISTER'}

    def execute(self, context):
        errors = utils.validate_selection(context)

        if not errors:
            self.report({'INFO'}, "Validation Passed! Hierarchy is good to rig.")
            return {'FINISHED'}

        # Show errors in a popup
        def draw_popup(self, context):
            layout = self.layout
            layout.label(text="Validation Errors:", icon='ERROR')
            for err in errors:
                layout.label(text=f"- {err}")
            layout.label(text="Please fix these issues before rigging.")

        context.window_manager.popup_menu(draw_popup, title="Validation Failed", icon='ERROR')
        return {'CANCELLED'}

class MECH_RIG_OT_AutoRig(bpy.types.Operator):
    """Detects hierarchy, handles collections, mirroring, and generates a rigid mechanical rig."""
    bl_idname = "mech_rig.auto_rig"
    bl_label = "Build / Update Rig"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        # Validation
        errors = utils.validate_selection(context)
        if errors:
            self.report({'ERROR'}, "Validation Failed. Run 'Validate Hierarchy' for details.")
            return {'CANCELLED'}

        symmetric_origin = context.scene.mech_rig_symmetric_origin

        try:
            # Check if we are updating an existing rig in the selection
            existing_armature = None
            mesh_selection = []

            for obj in selected_objects:
                if obj.type == 'ARMATURE':
                    existing_armature = obj
                else:
                    mesh_selection.append(obj)

            # If the user selected only the rig, we can't do much unless we know the objects.
            # But the user might be adding NEW objects.
            # The analyze_hierarchy expects a list of objects to build the tree.
            # If we include the armature in analyze_hierarchy, it might choke because it expects parent-child 
            # relationships of the *source objects*, not the rig.

            # Strategy: Pass only Mesh objects to analyze_hierarchy.
            if not mesh_selection:
                # If no meshes selected, maybe user just wants to re-process attached meshes?
                # Too complex for now. Assume user selects Rig + New/Old Meshes.
                if not existing_armature:
                    self.report({'ERROR'}, "No meshes selected to rig.")
                    return {'CANCELLED'}
                # If only Rig selected, warn?
                # But if user selected Rig + New Mesh, mesh_selection is not empty.

            # 1. Analyze (Pass only meshes)
            if mesh_selection:
                rig_data = utils.analyze_hierarchy(mesh_selection)
            else:
                # If only armature selected, we can't rebuild hierarchy from nothing.
                self.report({'ERROR'}, "Please select the objects to rig (along with the Armature if updating).")
                return {'CANCELLED'}

            # 2. Update/Create Armature
            armature_obj = utils.create_armature(context, rig_data, symmetric_origin, armature_obj=existing_armature)

            # 3. Interactive Binding (Non-Destructive)
            utils.bind_objects_interactive(context, rig_data, armature_obj, symmetric_origin, mesh_selection)

            # Select the armature
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = armature_obj
            armature_obj.select_set(True)
            bpy.ops.object.mode_set(mode='POSE') # Ready for controls

            self.report({'INFO'}, "Rig Updated! (Interactive Mode)")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Rigging Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

class MECH_RIG_OT_BakeRig(bpy.types.Operator):
    """Combines meshes and rig into a single skinned mesh for export."""
    bl_idname = "mech_rig.bake_rig"
    bl_label = "Bake for Export"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = context.active_object
        if not rig or rig.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select the Rig to bake.")
            return {'CANCELLED'}

        try:
            # 1. Store Pose & Reset to Rest Pose
            bpy.ops.object.mode_set(mode='POSE')
            # Save matrix_basis (local transform relative to parent) for all bones
            stored_matrices = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}

            # Reset to Rest Pose
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.transforms_clear()
            bpy.ops.pose.user_transforms_clear()
            context.view_layer.update()

            # 2. Duplicate Rig
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            rig.select_set(True)
            bpy.ops.object.duplicate()
            new_rig = context.active_object
            new_rig.name = f"{rig.name}_Export"

            # 2. Collect bound objects
            # Interactive bind uses BONE parenting.
            # We must collect ALL descendant meshes, not just direct children, 
            # because some might be parented to other meshes (hierarchy preservation).

            def get_all_mesh_descendants(obj):
                meshes = []
                for child in obj.children:
                    if child.type in {'MESH', 'CURVE'}:
                        meshes.append(child)
                    meshes.extend(get_all_mesh_descendants(child))
                return meshes

            bound_objects = get_all_mesh_descendants(rig)

            if not bound_objects:
                self.report({'WARNING'}, "No bound meshes found.")
                return {'CANCELLED'}

            # 3. Process Objects (Duplicate, Apply Transforms, Handle Mirroring)
            # Use utility to ensure modifiers are baked
            symmetric_origin = context.scene.mech_rig_symmetric_origin
            processed_objs = utils.prepare_meshes_for_bake(context, bound_objects, symmetric_origin)

            # 4. Join and Skin
            utils.finalize_mesh_and_skin(context, processed_objs, new_rig, original_selection=[])

            # Select Result
            bpy.ops.object.select_all(action='DESELECT')
            new_rig.select_set(True)
            context.view_layer.objects.active = new_rig

            # 5. Restore Original Rig Pose
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = rig
            rig.select_set(True)
            bpy.ops.object.mode_set(mode='POSE')

            for name, mat in stored_matrices.items():
                if name in rig.pose.bones:
                    rig.pose.bones[name].matrix_basis = mat

            bpy.ops.object.mode_set(mode='OBJECT')

            # Re-select new rig for user convenience
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = new_rig
            new_rig.select_set(True)

            self.report({'INFO'}, "Bake Complete! Ready to Export.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Bake Failed: {str(e)}")
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

class MECH_RIG_OT_BakeAnimations(bpy.types.Operator):
    """Bakes all actions from the Control Rig to a clean Export Rig."""
    bl_idname = "mech_rig.bake_animations"
    bl_label = "Bake Animations"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = context.active_object
        if not rig or rig.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select the Control Rig.")
            return {'CANCELLED'}

        try:
            print("--- Starting Animation Bake ---")

            # 1. Duplicate Rig (Armature Only)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            rig.select_set(True)
            bpy.ops.object.duplicate()
            export_rig = context.active_object
            export_rig.name = f"{rig.name}_Export_Anim"

            # Remove all constraints/drivers/custom props from export rig?
            # Ideally yes, we want a clean FK rig.
            # But the structure must match.
            # We can rely on 'Visual Keying' during bake to handle constraints.
            # But we must constrain Export Rig -> Control Rig first.

            # 2. Constrain Export Rig to Control Rig
            # We add COPY_TRANSFORMS to every bone in Export Rig targeting Control Rig
            context.view_layer.objects.active = export_rig
            bpy.ops.object.mode_set(mode='POSE')

            for pbone in export_rig.pose.bones:
                # Clear existing constraints first (IK, etc)
                for c in pbone.constraints:
                    pbone.constraints.remove(c)

                # Add Copy Transforms
                c = pbone.constraints.new('COPY_TRANSFORMS')
                c.target = rig
                c.subtarget = pbone.name

            bpy.ops.object.mode_set(mode='OBJECT')

            # 3. Iterate Actions
            actions_to_bake = []
            if bpy.data.actions:
                actions_to_bake = [a for a in bpy.data.actions] # Bake all?

            # Filter? Maybe only those used by the rig?
            # Hard to know. Let's bake all user actions.

            # Store original action
            original_action = rig.animation_data.action if rig.animation_data else None

            # Ensure Control Rig is in Pose Mode for reliable updates?
            # Or just Object Mode. Object mode is fine if we set Action.

            for action in actions_to_bake:
                print(f"Baking Action: {action.name}")

                # Assign Action to Control Rig
                if not rig.animation_data:
                    rig.animation_data_create()
                rig.animation_data.action = action

                # Create New Action for Export Rig
                export_action_name = f"Export_{action.name}"
                if export_action_name in bpy.data.actions:
                    bpy.data.actions.remove(bpy.data.actions[export_action_name])

                # We need to assign a dummy action or ensure one is created by Bake
                # Actually, nla.bake creates a new action on the object tracks

                # Set Scene Frame Range to match Action
                start, end = action.frame_range
                context.scene.frame_start = int(start)
                context.scene.frame_end = int(end)

                # Select Export Rig
                bpy.ops.object.select_all(action='DESELECT')
                export_rig.select_set(True)
                context.view_layer.objects.active = export_rig

                # Bake!
                # visual_keying=True: Bakes the result of the constraint
                # clear_constraints=False: We need to keep constraint for next action? 
                # Wait, if we clear constraints, we lose the link for the next loop!
                # So clear_constraints=False.

                bpy.ops.object.mode_set(mode='POSE')
                bpy.ops.nla.bake(
                    frame_start=int(start),
                    frame_end=int(end),
                    only_selected=False,
                    visual_keying=True,
                    clear_constraints=False,
                    use_current_action=True,
                    bake_types={'POSE'}
                )

                # Rename the generated action
                if export_rig.animation_data and export_rig.animation_data.action:
                    baked_action = export_rig.animation_data.action
                    baked_action.name = export_action_name
                    # Push to NLA stack or stash so we can bake next one?
                    # Or just unlink it?
                    # If we don't stash, assigning next action might lose it if no users?
                    baked_action.use_fake_user = True

                    # Unlink from rig so we don't overwrite it next loop
                    export_rig.animation_data.action = None

            # 4. Cleanup Export Rig
            # Remove the Copy Transforms constraints
            for pbone in export_rig.pose.bones:
                for c in pbone.constraints:
                    if c.type == 'COPY_TRANSFORMS':
                        pbone.constraints.remove(c)

            # Restore
            bpy.ops.object.mode_set(mode='OBJECT')
            if original_action:
                rig.animation_data.action = original_action

            self.report({'INFO'}, f"Baked {len(actions_to_bake)} animations to {export_rig.name}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Animation Bake Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

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
    bpy.utils.register_class(MECH_RIG_OT_ValidateHierarchy)
    bpy.utils.register_class(MECH_RIG_OT_AutoRig)
    bpy.utils.register_class(MECH_RIG_OT_BakeRig)
    bpy.utils.register_class(MECH_RIG_OT_BakeAnimations)
    bpy.utils.register_class(MECH_RIG_OT_AddControls)
    bpy.utils.register_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.register_class(MECH_RIG_OT_ApplyWidgetTransform)
    bpy.utils.register_class(MECH_RIG_OT_ReloadAddon)

def unregister():
    bpy.utils.unregister_class(MECH_RIG_OT_ValidateHierarchy)
    bpy.utils.unregister_class(MECH_RIG_OT_AutoRig)
    bpy.utils.unregister_class(MECH_RIG_OT_BakeRig)
    bpy.utils.unregister_class(MECH_RIG_OT_BakeAnimations)
    bpy.utils.unregister_class(MECH_RIG_OT_AddControls)
    bpy.utils.unregister_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.unregister_class(MECH_RIG_OT_ApplyWidgetTransform)
    bpy.utils.unregister_class(MECH_RIG_OT_ReloadAddon)
