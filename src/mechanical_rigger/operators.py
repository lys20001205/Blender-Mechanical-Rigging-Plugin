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
    """Combines meshes and rig, bakes animations (IK), and applies Unreal transforms."""
    bl_idname = "mech_rig.bake_rig"
    bl_label = "Bake & Export"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = context.active_object
        if not rig or rig.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select the Rig to bake.")
            return {'CANCELLED'}

        try:
            print("--- Starting Bake & Export Workflow ---")

            # Store original pose to restore later
            bpy.ops.object.mode_set(mode='POSE')
            stored_matrices = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
            bpy.ops.object.mode_set(mode='OBJECT')

            # -------------------------------------------------------------------------
            # 1. CREATE EXPORT RIG & MESH (Static Geometry)
            # -------------------------------------------------------------------------

            # Reset Pose to Rest Pose temporarily for clean mesh binding
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.transforms_clear()
            bpy.ops.pose.user_transforms_clear()
            rig.data.pose_position = 'POSE'
            context.view_layer.update()

            # Duplicate Rig
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            rig.select_set(True)
            bpy.ops.object.duplicate()
            export_rig = context.active_object
            export_rig.name = f"{rig.name}_Export"

            # Collect and Process Meshes
            def get_all_mesh_descendants(obj):
                meshes = []
                for child in obj.children:
                    if child.type in {'MESH', 'CURVE'}:
                        meshes.append(child)
                    meshes.extend(get_all_mesh_descendants(child))
                return meshes

            bound_objects = get_all_mesh_descendants(rig)
            symmetric_origin = context.scene.mech_rig_symmetric_origin
            processed_objs = utils.prepare_meshes_for_bake(context, bound_objects, symmetric_origin)

            # Join Meshes and Parent to Export Rig
            utils.finalize_mesh_and_skin(context, processed_objs, export_rig, original_selection=[])

            # Retrieve the combined mesh (it is now a child of export_rig)
            export_mesh = None
            for child in export_rig.children:
                if child.type == 'MESH':
                    export_mesh = child
                    break

            # Restore Original Rig Pose (We need it active for constraint targeting)
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = rig
            rig.select_set(True)
            bpy.ops.object.mode_set(mode='POSE')
            for name, mat in stored_matrices.items():
                if name in rig.pose.bones:
                    rig.pose.bones[name].matrix_basis = mat
            bpy.ops.object.mode_set(mode='OBJECT')

            # -------------------------------------------------------------------------
            # 2. BAKE ANIMATION (First, in Original Coordinates)
            # -------------------------------------------------------------------------
            # Constrain Export Rig to Control Rig
            context.view_layer.objects.active = export_rig
            bpy.ops.object.mode_set(mode='POSE')

            for pbone in export_rig.pose.bones:
                # Clear existing constraints
                for c in list(pbone.constraints):
                    pbone.constraints.remove(c)

                # Add Copy Transforms to follow Control Rig
                c = pbone.constraints.new('COPY_TRANSFORMS')
                c.target = rig
                c.subtarget = pbone.name
            
            # Bake Action
            # Use Active Action frame range if available
            start = context.scene.frame_start
            end = context.scene.frame_end
            
            original_action = None
            if rig.animation_data and rig.animation_data.action:
                original_action = rig.animation_data.action
                start = int(original_action.frame_range[0])
                end = int(original_action.frame_range[1])

            print(f"Baking frames {start} to {end}...")
            
            # Switch to Object Mode to safely handle object selection/data clearing
            bpy.ops.object.mode_set(mode='OBJECT')

            # CLEANUP: Clear ONLY Pose animation data on Export Rig before baking
            # We want a fresh bake for bones (FK keys only), but we MUST preserve Object keys (Root Motion)
            if export_rig.animation_data and export_rig.animation_data.action:
                act = export_rig.animation_data.action
                fcurves_to_remove = []
                for fc in act.fcurves:
                    # Remove bone animation, keep object animation
                    if "pose.bones" in fc.data_path:
                        fcurves_to_remove.append(fc)

                for fc in fcurves_to_remove:
                    act.fcurves.remove(fc)

            # Constrain Export Object to Source Object (to ensure we capture Root Motion updates)
            # Even if we have keys, baking ensures we burn it all into a clean action
            c_obj = export_rig.constraints.new('COPY_TRANSFORMS')
            c_obj.target = rig

            # Ensure ONLY Export Rig is selected for Baking
            # (Safety against 'original rig constraints gone' issue)
            bpy.ops.object.select_all(action='DESELECT')
            export_rig.select_set(True)
            context.view_layer.objects.active = export_rig

            # Switch back to Pose Mode for Baking (since we bake 'POSE')
            bpy.ops.object.mode_set(mode='POSE')

            # Prevent Scale Baking by locking channels
            prev_lock_scale = export_rig.lock_scale[:]
            export_rig.lock_scale = (True, True, True)

            # Bake
            # use_current_action=True will create a new Action if none exists
            bpy.ops.nla.bake(
                frame_start=start,
                frame_end=end,
                only_selected=True, # STRICTLY only selected (Export Rig)
                visual_keying=True,
                clear_constraints=True,
                use_current_action=True,
                clean_curves=True,
                bake_types={'POSE', 'OBJECT'}
            )
            
            # Restore Scale locks
            export_rig.lock_scale = prev_lock_scale

            # Rename Action
            if export_rig.animation_data and export_rig.animation_data.action:
                act = export_rig.animation_data.action
                act.name = f"Export_{original_action.name if original_action else 'Action'}"

            bpy.ops.object.mode_set(mode='OBJECT')

            # -------------------------------------------------------------------------
            # 3. UNREAL COORDINATE FIX (Post-Bake, Explicit Unparenting)
            # -------------------------------------------------------------------------
            print("Applying Unreal Transforms (Post-Bake)...")

            # Step A: Unparent Mesh to treat transforms independently
            if export_mesh:
                bpy.ops.object.select_all(action='DESELECT')
                export_mesh.select_set(True)
                context.view_layer.objects.active = export_mesh
                # Clear parent, keep transformation
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

                # Step B: MESH FIX - Rotate -90 Z, Scale 100
                # User requested explicit -90 Z rotation for the mesh artifact
                bpy.ops.transform.rotate(value=-1.570796, orient_axis='Z')
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

                # Scale 100
                bpy.ops.transform.resize(value=(100, 100, 100))
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            # Step C: RIG FIX - Rotate -90 Z, Scale 100
            bpy.ops.object.select_all(action='DESELECT')
            export_rig.select_set(True)
            context.view_layer.objects.active = export_rig

            # Rotate -90 Z
            bpy.ops.transform.rotate(value=-1.570796, orient_axis='Z')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

            # ROTATION FIX: Rotate Object Animation Curves by -90 Z
            if export_rig.animation_data and export_rig.animation_data.action:
                act = export_rig.animation_data.action

                # --- Location ---
                # Retrieve X and Y location curves (indices 0 and 1)
                loc_x = next((fc for fc in act.fcurves if fc.data_path == "location" and fc.array_index == 0), None)
                loc_y = next((fc for fc in act.fcurves if fc.data_path == "location" and fc.array_index == 1), None)

                if loc_x and loc_y:
                    # Assume synchronized keyframes (bake result). Iterate by index.
                    # Safety: Iterate min length
                    count = min(len(loc_x.keyframe_points), len(loc_y.keyframe_points))

                    for i in range(count):
                        pt_x = loc_x.keyframe_points[i]
                        pt_y = loc_y.keyframe_points[i]

                        # Capture old values
                        # Co = (Frame, Value)
                        old_x = pt_x.co[1]
                        old_y = pt_y.co[1]

                        old_hl_x = pt_x.handle_left[1]
                        old_hl_y = pt_y.handle_left[1]

                        old_hr_x = pt_x.handle_right[1]
                        old_hr_y = pt_y.handle_right[1]

                        # Apply Rotation -90 Z (X' = Y, Y' = -X)
                        pt_x.co[1] = old_y
                        pt_y.co[1] = -old_x

                        pt_x.handle_left[1] = old_hl_y
                        pt_y.handle_left[1] = -old_hl_x

                        pt_x.handle_right[1] = old_hr_y
                        pt_y.handle_right[1] = -old_hr_x

                    loc_x.update()
                    loc_y.update()

                # --- Rotation ---
                # Check Mode
                mode = export_rig.rotation_mode

                if mode == 'QUATERNION':
                    # W, X, Y, Z indices 0, 1, 2, 3
                    rot_w = next((fc for fc in act.fcurves if fc.data_path == "rotation_quaternion" and fc.array_index == 0), None)
                    rot_x = next((fc for fc in act.fcurves if fc.data_path == "rotation_quaternion" and fc.array_index == 1), None)
                    rot_y = next((fc for fc in act.fcurves if fc.data_path == "rotation_quaternion" and fc.array_index == 2), None)
                    rot_z = next((fc for fc in act.fcurves if fc.data_path == "rotation_quaternion" and fc.array_index == 3), None)

                    if rot_w and rot_x and rot_y and rot_z:
                         count = min(len(rot_w.keyframe_points), len(rot_x.keyframe_points), len(rot_y.keyframe_points), len(rot_z.keyframe_points))

                         rot_mat_q = mathutils.Quaternion((0, 0, 1), -1.570796) # -90 Z

                         for i in range(count):
                             pw = rot_w.keyframe_points[i]
                             px = rot_x.keyframe_points[i]
                             py = rot_y.keyframe_points[i]
                             pz = rot_z.keyframe_points[i]

                             old_q = mathutils.Quaternion((pw.co[1], px.co[1], py.co[1], pz.co[1]))
                             new_q = rot_mat_q @ old_q

                             pw.co[1] = new_q.w
                             px.co[1] = new_q.x
                             py.co[1] = new_q.y
                             pz.co[1] = new_q.z

                             # Handles ignored for Quats (complex), but dense bake makes them irrelevant usually.

                         rot_w.update()
                         rot_x.update()
                         rot_y.update()
                         rot_z.update()

                elif mode == 'XYZ': # Euler XYZ
                    # Z is index 2. Just subtract 90 deg.
                    rot_z = next((fc for fc in act.fcurves if fc.data_path == "rotation_euler" and fc.array_index == 2), None)
                    if rot_z:
                        for k in rot_z.keyframe_points:
                             k.co[1] -= 1.570796
                             k.handle_left[1] -= 1.570796
                             k.handle_right[1] -= 1.570796
                        rot_z.update()


            # Scale 100
            bpy.ops.transform.resize(value=(100, 100, 100))
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            # Step D: Reparent Mesh
            if export_mesh:
                bpy.ops.object.select_all(action='DESELECT')
                export_rig.select_set(True) # Active
                export_mesh.select_set(True) # Selected
                context.view_layer.objects.active = export_rig
                # Parent mesh to Rig (Object) or Armature? 
                # Bake result usually expects Mesh parented to Armature Object with modifier.
                bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

            # Step E: Final Export Scale (0.01)
            export_rig.scale = (0.01, 0.01, 0.01)


            # -------------------------------------------------------------------------
            # 4. FIX ANIMATION CURVES (Scale Correction)
            # -------------------------------------------------------------------------
            # Applying Scale (100) to the Armature scales the Rest Pose bones.
            # However, Location Keyframes are values (e.g., 0.5 meters).
            # Now that the bone is 100x bigger, 0.5 meters is 1/100th the relative distance.
            # We must multiply all Location F-Curves by 100.

            if export_rig.animation_data and export_rig.animation_data.action:
                action = export_rig.animation_data.action
                print(f"Scaling Animation Curves for {action.name}...")

                for fcurve in action.fcurves:
                    # Check if it targets location
                    if "location" in fcurve.data_path:
                        for kf in fcurve.keyframe_points:
                            kf.co[1] *= 100.0  # Scale Value (Y-axis of the curve editor)
                            # Handle handles if Bezier?
                            kf.handle_left[1] *= 100.0
                            kf.handle_right[1] *= 100.0


            # Ensure Export Mesh inherits this (it should if parented)

            # -------------------------------------------------------------------------
            # FINALIZE
            # -------------------------------------------------------------------------

            # Select only the export rig for convenience
            bpy.ops.object.select_all(action='DESELECT')
            export_rig.select_set(True)
            context.view_layer.objects.active = export_rig

            self.report({'INFO'}, "Bake & Export Prep Complete!")
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

class MECH_RIG_OT_ConvertRootMotion(bpy.types.Operator):
    """Converts Root Bone animation to Armature Object animation."""
    bl_idname = "mech_rig.convert_root_motion"
    bl_label = "Convert Root Motion"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an Armature.")
            return {'CANCELLED'}

        scene = context.scene
        root_name = scene.mech_rig_root_bone

        # Auto-detect root if not specified
        if not root_name:
            roots = [b.name for b in armature.data.bones if not b.parent]
            if not roots:
                self.report({'ERROR'}, "No root bone found.")
                return {'CANCELLED'}
            root_name = roots[0]
            self.report({'INFO'}, f"Auto-detected root bone: {root_name}")

        # Verify bone exists
        if root_name not in armature.pose.bones:
             self.report({'ERROR'}, f"Bone '{root_name}' not found in pose.")
             return {'CANCELLED'}

        # Check for Stashed Action (NLA) if no active action
        # If a strip is selected/active, ensure it's the active action for editing
        target_strip = None
        if armature.animation_data and armature.animation_data.nla_tracks:
             for track in armature.animation_data.nla_tracks:
                 for strip in track.strips:
                     if strip.select or strip.active:
                         target_strip = strip
                         break

        if target_strip:
             # Check if object is linked (read-only)
             if armature.library:
                 self.report({'ERROR'}, "Cannot edit linked object.")
                 return {'CANCELLED'}

             try:
                 # Strategy: Enter NLA Tweak Mode to edit the action.
                 # This works even if 'animation_data.action' is read-only (e.g. overrides).

                 # 1. Ensure strip is uniquely selected (defines 'Active' for Tweak Mode)
                 # We cannot set .active directly (read-only), so we rely on selection.
                 for track in armature.animation_data.nla_tracks:
                     for s in track.strips:
                         s.select = False

                 target_strip.select = True

                 # 2. Enter Tweak Mode
                 armature.animation_data.use_tweak_mode = True

                 # 3. Verify
                 # Note: In Tweak Mode, .action reflects the tweaked action.
                 if armature.animation_data.action != target_strip.action:
                     # Fallback: If tweak mode failed to pick the right one, try direct assignment
                     # (This might fail if read-only, but it's our last resort)
                     armature.animation_data.use_tweak_mode = False
                     try:
                        armature.animation_data.action = target_strip.action
                     except AttributeError:
                        self.report({'WARNING'}, "Could not force active action. Proceeding with Tweak Mode result.")

                 self.report({'INFO'}, f"Editing Action via NLA: {target_strip.action.name}")

             except Exception as e:
                 self.report({'ERROR'}, f"Error preparing action: {e}")
                 return {'CANCELLED'}

        # Determine Frame Range
        start = scene.frame_start
        end = scene.frame_end
        if armature.animation_data and armature.animation_data.action:
            action = armature.animation_data.action
            start = int(action.frame_range[0])
            end = int(action.frame_range[1])

        print(f"Converting Root Motion using '{root_name}' (Frames {start}-{end})...")

        try:
            # --- Phase 1: Capture Relative Motion ---

            # Ensure Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')

            # Create Empty
            bpy.ops.object.select_all(action='DESELECT')
            empty = bpy.data.objects.new("Temp_Root_Tracker", None)
            context.collection.objects.link(empty)
            empty.empty_display_type = 'PLAIN_AXES'

            # Match Armature Transform
            empty.matrix_world = armature.matrix_world.copy()

            # Add Child Of Constraint
            context.view_layer.objects.active = empty
            empty.select_set(True)

            c = empty.constraints.new('CHILD_OF')
            c.target = armature
            c.subtarget = root_name

            # Set Inverse (Fix Offset)
            # Logic: inverse_matrix = (TargetWorld * BoneMatrix)^-1 * OwnerWorld
            # OwnerWorld is currently == ArmatureWorld

            pbone = armature.pose.bones[root_name]
            # Bone World Matrix
            bone_world = armature.matrix_world @ pbone.matrix

            # Set Inverse: We want VisualWorld to remain EmptyWorld (which is currently ArmatureWorld)
            # Child Of Formula: World = TargetWorld @ Inverse @ Local
            # If we set Inverse = TargetWorld.inverted(), then World = TargetWorld @ TargetWorld.inv() @ Local = Local.
            # Since Local matches our desired World position (ArmatureWorld), this is correct.
            c.inverse_matrix = bone_world.inverted()

            # --- Phase 2: Bake Empty ---

            # Select Empty (already active/selected)
            # Bake Action
            bpy.ops.nla.bake(
                frame_start=start,
                frame_end=end,
                only_selected=True,
                visual_keying=True,
                clear_constraints=True,
                use_current_action=True,
                bake_types={'OBJECT'}
            )

            # --- Phase 3: Transfer to Armature & Reset ---

            # Select Armature
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = armature
            armature.select_set(True)

            # Add Copy Transforms
            c_arm = armature.constraints.new('COPY_TRANSFORMS')
            c_arm.target = empty

            # Bake Armature
            # Note: We are baking Object transforms, so bake_types={'OBJECT'}
            bpy.ops.nla.bake(
                frame_start=start,
                frame_end=end,
                only_selected=True,
                visual_keying=True,
                clear_constraints=True,
                use_current_action=True,
                bake_types={'OBJECT'}
            )

            # Reset Root Bone
            # Switch to Pose Mode
            bpy.ops.object.mode_set(mode='POSE')

            # Remove keys
            if armature.animation_data and armature.animation_data.action:
                action = armature.animation_data.action
                fcurves_to_remove = []

                # Robust path matching
                pbone_path = armature.pose.bones[root_name].path_from_id()

                for fc in action.fcurves:
                    # Check if the F-Curve belongs to this bone (location, rotation, etc.)
                    if fc.data_path.startswith(pbone_path):
                        fcurves_to_remove.append(fc)

                for fc in fcurves_to_remove:
                    action.fcurves.remove(fc)

            # Reset Transforms
            pbone = armature.pose.bones[root_name]
            pbone.location = (0, 0, 0)
            pbone.rotation_euler = (0, 0, 0)
            pbone.rotation_quaternion = (1, 0, 0, 0)
            pbone.scale = (1, 1, 1)

            # --- Cleanup ---
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects.remove(empty, do_unlink=True)

            # Select Armature
            armature.select_set(True)
            context.view_layer.objects.active = armature

            # Exit Tweak Mode if we entered it
            if target_strip and armature.animation_data:
                armature.animation_data.use_tweak_mode = False

            self.report({'INFO'}, "Root Motion Converted Successfully!")
            return {'FINISHED'}

        except Exception as e:
            # Exit Tweak Mode if we entered it (on failure)
            if 'target_strip' in locals() and target_strip and armature.animation_data:
                 armature.animation_data.use_tweak_mode = False

            self.report({'ERROR'}, f"Conversion Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

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
    bpy.utils.register_class(MECH_RIG_OT_AddControls)
    bpy.utils.register_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.register_class(MECH_RIG_OT_ApplyWidgetTransform)
    bpy.utils.register_class(MECH_RIG_OT_ConvertRootMotion)
    bpy.utils.register_class(MECH_RIG_OT_ReloadAddon)

def unregister():
    bpy.utils.unregister_class(MECH_RIG_OT_ValidateHierarchy)
    bpy.utils.unregister_class(MECH_RIG_OT_AutoRig)
    bpy.utils.unregister_class(MECH_RIG_OT_BakeRig)
    bpy.utils.unregister_class(MECH_RIG_OT_AddControls)
    bpy.utils.unregister_class(MECH_RIG_OT_EditWidgetTransform)
    bpy.utils.unregister_class(MECH_RIG_OT_ApplyWidgetTransform)
    bpy.utils.unregister_class(MECH_RIG_OT_ConvertRootMotion)
    bpy.utils.unregister_class(MECH_RIG_OT_ReloadAddon)
