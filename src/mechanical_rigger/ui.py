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

# --- Panels ---

class VIEW3D_PT_mech_rig_main(bpy.types.Panel):
    """Main Panel for Mechanical Rigger"""
    bl_label = "Mechanical Rigger"
    bl_idname = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mechanical Rigger"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # Cleaner look

class VIEW3D_PT_mech_rig_generate(bpy.types.Panel):
    """Rig Generation Panel"""
    bl_label = "Rig Generation"
    bl_idname = "VIEW3D_PT_mech_rig_generate"
    bl_parent_id = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "mech_rig_symmetric_origin", text="Symmetric Origin")
        layout.prop(scene, "mech_rig_bone_size_scale", text="Bone Size Scale")

        row = layout.row(align=True)
        row.operator("mech_rig.validate_hierarchy", text="Validate Hierarchy", icon='CHECKMARK')
        row.operator("mech_rig.auto_rig", text="Build / Update Rig", icon='ARMATURE_DATA')

        row = layout.row(align=True)
        row.operator("mech_rig.bake_rig", text="Bake & Export", icon='EXPORT')

class VIEW3D_PT_mech_rig_animation(bpy.types.Panel):
    """Animation Tools Panel"""
    bl_label = "Animation"
    bl_idname = "VIEW3D_PT_mech_rig_animation"
    bl_parent_id = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        layout.label(text="Root Motion to Object:")

        if obj and obj.type == 'ARMATURE':
             layout.prop_search(scene, "mech_rig_root_bone", obj.pose, "bones", text="Root Bone")

        layout.operator("mech_rig.convert_root_motion", text="Convert Root Motion", icon='ACTION')

class VIEW3D_PT_mech_rig_layers(bpy.types.Panel):
    """Bone Collection Management"""
    bl_label = "Rig Layers"
    bl_idname = "VIEW3D_PT_mech_rig_layers"
    bl_parent_id = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        arm = obj.data

        layout.label(text="Bone Collections:")

        # Simple Grid Layout for Collections
        # Assuming Blender 4.0+ Bone Collections
        if hasattr(arm, "collections"):
            col_flow = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
            for bcol in arm.collections:
                col_flow.prop(bcol, "is_visible", text=bcol.name, toggle=True)
        else:
            layout.label(text="Bone Collections not supported (Old Blender?)", icon='ERROR')

class VIEW3D_PT_mech_rig_settings(bpy.types.Panel):
    """Control Settings for Selected Bone"""
    bl_label = "Rig Settings"
    bl_idname = "VIEW3D_PT_mech_rig_settings"
    bl_parent_id = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        obj = context.active_object
        scene = context.scene

        # Global Settings
        layout.prop(scene, "mech_rig_widget_scale", text="Global Widget Scale")

        layout.separator()

        # Bone List
        layout.label(text="Bone Configuration:")
        row = layout.row()
        row.template_list("MECH_RIG_UL_BoneList", "", obj.pose, "bones", scene, "mech_rig_active_bone_index")

        # Active Bone Settings
        if 0 <= scene.mech_rig_active_bone_index < len(obj.pose.bones):
            active_bone = obj.pose.bones[scene.mech_rig_active_bone_index]
            settings = active_bone.mech_rig_settings

            box = layout.box()
            box.label(text=f"Settings: {active_bone.name}", icon='BONE_DATA')

            # IK Settings
            box.prop(settings, "use_ik", text="Enable IK")
            if settings.use_ik:
                box.prop(settings, "ik_chain_length", text="Chain Length")

            box.separator()

            # Shape Settings
            box.prop(settings, "control_shape", text="Widget Shape")

            if settings.control_shape != 'NONE':
                row = box.row()
                row.prop(settings, "override_transform", text="Customize Transform")
                if active_bone.custom_shape:
                    row.operator("mech_rig.edit_widget_transform", text="", icon='GIZMO')

                if settings.override_transform:
                    col = box.column(align=True)
                    col.prop(settings, "visual_scale")
                    col.prop(settings, "visual_location")
                    col.prop(settings, "visual_rotation")

        layout.separator()
        layout.operator("mech_rig.add_controls", text="Re-Apply Controls", icon='POSE_HLT')


class VIEW3D_PT_mech_rig_widget_edit(bpy.types.Panel):
    """Temporary Panel for Widget Editing Mode"""
    bl_label = "Widget Edit Mode"
    bl_idname = "VIEW3D_PT_mech_rig_widget_edit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mechanical Rigger" # Shows up when active

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get("mech_temp_type") == "WIDGET_EDIT"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        layout.label(text=f"Editing: {obj.name}", icon='EDITMODE_HLT')
        layout.operator("mech_rig.apply_widget_transform", text="Apply Custom Transform", icon='CHECKMARK')

class VIEW3D_PT_mech_rig_tools(bpy.types.Panel):
    """Developer Tools"""
    bl_label = "Tools"
    bl_idname = "VIEW3D_PT_mech_rig_tools"
    bl_parent_id = "VIEW3D_PT_mech_rig_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("mech_rig.reload_addon", text="Reload Scripts", icon='FILE_REFRESH')


# --- Data Properties ---

def update_use_ik(self, context):
    """Callback to sync Use IK to selected bones and mirrored bones."""
    # self is the PropertyGroup (MechRigBoneSettings) attached to a PoseBone
    # We need to find the PoseBone that owns this property group.
    # Unfortunately, PropertyGroup doesn't easily know its owner in the update callback without hacky traversal
    # OR we rely on context.active_pose_bone (usually the one being edited).

    # Check context
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE' or obj.mode != 'POSE':
        return

    # We assume 'self' belongs to the active bone if the user is clicking in the UI
    active_pbone = context.active_pose_bone
    if not active_pbone or active_pbone.mech_rig_settings != self:
        # Fallback: iterate all bones to find owner? Too slow.
        # Ideally we trust active_pose_bone for UI interaction.
        return

    new_val = self.use_ik

    # 1. Apply to Selected Bones
    for pbone in context.selected_pose_bones:
        if pbone != active_pbone:
            # Prevent recursion if we are setting it here
            if pbone.mech_rig_settings.use_ik != new_val:
                pbone.mech_rig_settings.use_ik = new_val

    # 2. Apply to Mirrored Bones (Symmetry)
    # Collect list of bones to process (Active + Selected)
    bones_to_mirror = [p for p in context.selected_pose_bones]

    for pbone in bones_to_mirror:
        name = pbone.name

        # Check for standard suffixes
        mirror_name = None
        if name.endswith("_L"):
            mirror_name = name[:-2] + "_R"
        elif name.endswith(".L"):
            mirror_name = name[:-2] + ".R"
        elif name.endswith("_R"):
            mirror_name = name[:-2] + "_L"
        elif name.endswith(".R"):
            mirror_name = name[:-2] + ".L"

        if mirror_name and mirror_name in obj.pose.bones:
            mirror_pbone = obj.pose.bones[mirror_name]
            if mirror_pbone.mech_rig_settings.use_ik != new_val:
                mirror_pbone.mech_rig_settings.use_ik = new_val
            # Ensure chain length is synced initially too if enabling
            if new_val:
                mirror_pbone.mech_rig_settings.ik_chain_length = active_pbone.mech_rig_settings.ik_chain_length


def update_ik_chain_length(self, context):
    """Callback to sync Chain Length to mirrored bones."""
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE' or obj.mode != 'POSE':
        return

    active_pbone = context.active_pose_bone
    if not active_pbone or active_pbone.mech_rig_settings != self:
        return

    new_val = self.ik_chain_length

    # Apply to Mirrored Bones (Symmetry)
    # Collect list of bones to process (Active + Selected)
    bones_to_mirror = [p for p in context.selected_pose_bones]

    for pbone in bones_to_mirror:
        name = pbone.name
        # Check for standard suffixes
        mirror_name = None
        if name.endswith("_L"):
            mirror_name = name[:-2] + "_R"
        elif name.endswith(".L"):
            mirror_name = name[:-2] + ".R"
        elif name.endswith("_R"):
            mirror_name = name[:-2] + "_L"
        elif name.endswith(".R"):
            mirror_name = name[:-2] + ".L"

        if mirror_name and mirror_name in obj.pose.bones:
            mirror_pbone = obj.pose.bones[mirror_name]
            if mirror_pbone.mech_rig_settings.ik_chain_length != new_val:
                mirror_pbone.mech_rig_settings.ik_chain_length = new_val

class MechRigBoneSettings(bpy.types.PropertyGroup):
    use_ik: bpy.props.BoolProperty(
        name="Use IK",
        description="Create an Inverse Kinematics setup for this bone",
        default=False,
        update=update_use_ik
    )
    ik_chain_length: bpy.props.IntProperty(
        name="Chain Length",
        description="Number of bones in the IK chain",
        default=2,
        min=1,
        update=update_ik_chain_length
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

classes = (
    MechRigBoneSettings,
    MechRigBoneItem,
    MECH_RIG_UL_BoneList,
    VIEW3D_PT_mech_rig_main,
    VIEW3D_PT_mech_rig_generate,
    VIEW3D_PT_mech_rig_animation,
    VIEW3D_PT_mech_rig_layers,
    VIEW3D_PT_mech_rig_settings,
    VIEW3D_PT_mech_rig_widget_edit,
    VIEW3D_PT_mech_rig_tools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

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
        default=5.0,
        min=0.1
    )

    bpy.types.Scene.mech_rig_bone_size_scale = bpy.props.FloatProperty(
        name="Bone Size Scale",
        description="Scale factor for generated bone length",
        default=0.2,
        min=0.01
    )

    bpy.types.Scene.mech_rig_root_bone = bpy.props.StringProperty(
        name="Root Bone",
        description="Bone to extract root motion from"
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

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.PoseBone.mech_rig_settings
    del bpy.types.Scene.mech_rig_symmetric_origin
    del bpy.types.Scene.mech_rig_widget_scale
    del bpy.types.Scene.mech_rig_bone_size_scale
    del bpy.types.Scene.mech_rig_root_bone
    del bpy.types.Scene.mech_rig_active_bone_index
