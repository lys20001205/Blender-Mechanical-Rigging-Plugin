import bpy
from bpy.app.handlers import persistent

# --- UI List & Panel ---

class MechRigBoneItem(bpy.types.PropertyGroup):
    """Data class for the UI List."""
    pass

class MECH_RIG_UL_BoneList(bpy.types.UIList):
    """List of bones to configure controls."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        bone = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(bone, "name", text="", emboss=False, icon='BONE_DATA')
            if bone.mech_rig_settings.use_ik:
                layout.label(text="IK", icon='CONSTRAINT_BONE')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='BONE_DATA')

class VIEW3D_PT_MechanicalRigger(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Mechanical Rigger"
    bl_idname = "VIEW3D_PT_mechanical_rigger"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mechanical Rigger"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Developer Tools (Top for accessibility)
        box = layout.box()
        box.label(text="Developer")
        box.operator("mech_rig.reload_addon", text="Reload Scripts", icon='FILE_REFRESH')

        # Rigging Section
        box = layout.box()
        box.label(text="Step 1: Auto Rig")
        box.prop(scene, "mech_rig_symmetric_origin", text="Symmetric Origin")
        box.operator("mech_rig.auto_rig", text="Rig Hierarchy", icon='ARMATURE_DATA')

        # Control Section
        box = layout.box()
        box.label(text="Step 2: Controls Config")

        obj = context.active_object

        # Mode: Editing Widget Transform
        if obj and obj.get("mech_temp_type") == "WIDGET_EDIT":
            box = layout.box()
            box.label(text=f"Editing Widget: {obj.name}", icon='EDITMODE_HLT')
            box.operator("mech_rig.apply_widget_transform", text="Apply Custom Transform", icon='CHECKMARK')
            return

        # Mode: Armature Configuration
        if obj and obj.type == 'ARMATURE':
            # Global Settings
            box.prop(scene, "mech_rig_widget_scale", text="Widget Scale")

            # Bone List
            row = box.row()
            row.template_list("MECH_RIG_UL_BoneList", "", obj.pose, "bones", scene, "mech_rig_active_bone_index")

            # Selected Bone Settings
            if 0 <= scene.mech_rig_active_bone_index < len(obj.pose.bones):
                active_bone = obj.pose.bones[scene.mech_rig_active_bone_index]
                settings = active_bone.mech_rig_settings

                col = box.column(align=True)
                col.label(text=f"Settings for: {active_bone.name}")
                col.prop(settings, "control_shape", text="Shape")

                col.separator()
                row = col.row()
                row.prop(settings, "override_transform")
                if active_bone.custom_shape:
                    row.operator("mech_rig.edit_widget_transform", text="", icon='GIZMO')

                if settings.override_transform:
                    col.prop(settings, "visual_scale")
                    col.prop(settings, "visual_location")
                    col.prop(settings, "visual_rotation")

                col.separator()
                col.prop(settings, "use_ik", text="Enable IK")
                if settings.use_ik:
                    col.prop(settings, "ik_chain_length", text="Chain Length")

            box.separator()
            box.operator("mech_rig.add_controls", text="Apply Controls", icon='POSE_HLT')
        else:
            box.label(text="Select the Rig to configure.", icon='INFO')

# --- Data Properties ---

class MechRigBoneSettings(bpy.types.PropertyGroup):
    use_ik: bpy.props.BoolProperty(
        name="Use IK", description="Create an Inverse Kinematics setup for this bone", default=False
    )
    ik_chain_length: bpy.props.IntProperty(
        name="Chain Length", description="Number of bones in the IK chain", default=2, min=1
    )
    control_shape: bpy.props.EnumProperty(
        items=[
            ('NONE', "None", "No Control Shape"),
            ('CIRCLE', "Circle", ""),
            ('BOX', "Box", ""),
            ('SPHERE', "Sphere", ""),
        ],
        name="Shape",
        default='CIRCLE'
    )

    # Custom Widget Transform
    override_transform: bpy.props.BoolProperty(
        name="Customize Transform",
        description="Manually set scale/location/rotation for the control widget",
        default=False
    )
    visual_scale: bpy.props.FloatVectorProperty(
        name="Scale", default=(1.0, 1.0, 1.0), size=3
    )
    visual_location: bpy.props.FloatVectorProperty(
        name="Location", default=(0.0, 0.0, 0.0), size=3
    )
    visual_rotation: bpy.props.FloatVectorProperty(
        name="Rotation", default=(0.0, 0.0, 0.0), size=3, unit='ROTATION'
    )

# --- Selection Sync Logic ---

_is_updating_selection = False

def update_bone_index(self, context):
    """Called when the UI list index changes (user clicked in list). Syncs 3D View."""
    global _is_updating_selection
    if _is_updating_selection:
        return

    obj = context.active_object
    if obj and obj.type == 'ARMATURE' and obj.mode == 'POSE':
        idx = self.mech_rig_active_bone_index
        if 0 <= idx < len(obj.pose.bones):
            pbone = obj.pose.bones[idx]
            bone = pbone.bone

            # Prevent infinite recursion loop
            _is_updating_selection = True
            try:
                # Set active bone in 3D view
                obj.data.bones.active = bone
                # Ensure it is selected
                bone.select = True
            finally:
                _is_updating_selection = False

@persistent
def sync_selection_to_ui(scene):
    """Called on Depsgraph update. Syncs UI list index to 3D View selection."""
    global _is_updating_selection
    if _is_updating_selection:
        return

    context = bpy.context
    obj = context.active_object

    if obj and obj.type == 'ARMATURE' and obj.mode == 'POSE':
        active_bone = obj.data.bones.active
        if active_bone:
            # Find the pose bone corresponding to the active edit bone (data bone)
            # Pose bones index usually matches data bones index, but safest is by name.
            pbone = obj.pose.bones.get(active_bone.name)
            if pbone:
                # Find index in pose.bones
                # Since pose.bones is a collection, we iterate or assume order.
                # obj.pose.bones is a collection, let's just use list.index if needed or property lookup
                # Efficient way:
                # But template_list uses integer index.
                # Assuming obj.pose.bones order matches internal index.
                # We need to find the index of pbone in obj.pose.bones

                # Blender API doesn't have a direct .index for PoseBone in the collection if not using [i].
                # We can loop.
                found_index = -1
                for i, b in enumerate(obj.pose.bones):
                    if b == pbone:
                        found_index = i
                        break

                if found_index != -1 and scene.mech_rig_active_bone_index != found_index:
                    _is_updating_selection = True
                    try:
                        scene.mech_rig_active_bone_index = found_index
                    finally:
                        _is_updating_selection = False

# --- Registration ---

def register():
    bpy.utils.register_class(MechRigBoneSettings)
    bpy.utils.register_class(MechRigBoneItem)
    bpy.utils.register_class(MECH_RIG_UL_BoneList)
    bpy.utils.register_class(VIEW3D_PT_MechanicalRigger)

    bpy.types.PoseBone.mech_rig_settings = bpy.props.PointerProperty(type=MechRigBoneSettings)

    bpy.types.Scene.mech_rig_symmetric_origin = bpy.props.PointerProperty(
        name="Symmetric Origin",
        type=bpy.types.Object,
        description="Empty object acting as the mirror center",
        poll=lambda self, obj: obj.type == 'EMPTY'
    )

    bpy.types.Scene.mech_rig_widget_scale = bpy.props.FloatProperty(
        name="Widget Scale",
        description="Global scale factor for control widgets",
        default=0.5,
        min=0.1
    )

    # Register property with update callback
    bpy.types.Scene.mech_rig_active_bone_index = bpy.props.IntProperty(
        update=update_bone_index
    )

    # Register handler
    if sync_selection_to_ui not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_selection_to_ui)

def unregister():
    # Unregister handler
    if sync_selection_to_ui in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_selection_to_ui)

    bpy.utils.unregister_class(VIEW3D_PT_MechanicalRigger)
    bpy.utils.unregister_class(MECH_RIG_UL_BoneList)
    bpy.utils.unregister_class(MechRigBoneItem)
    bpy.utils.unregister_class(MechRigBoneSettings)
    del bpy.types.PoseBone.mech_rig_settings
    del bpy.types.Scene.mech_rig_symmetric_origin
    del bpy.types.Scene.mech_rig_widget_scale
    del bpy.types.Scene.mech_rig_active_bone_index
