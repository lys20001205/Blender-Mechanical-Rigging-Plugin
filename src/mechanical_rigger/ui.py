import bpy

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
        if obj and obj.type == 'ARMATURE':
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
                col.prop(settings, "use_ik", text="Enable IK")
                if settings.use_ik:
                    col.prop(settings, "ik_chain_length", text="Chain Length")

            box.separator()
            box.operator("mech_rig.add_controls", text="Apply Controls", icon='POSE_HLT')
        else:
            box.label(text="Select the Rig to configure.", icon='INFO')

class MechRigBoneSettings(bpy.types.PropertyGroup):
    use_ik: bpy.props.BoolProperty(
        name="Use IK", description="Create an Inverse Kinematics setup for this bone", default=False
    )
    ik_chain_length: bpy.props.IntProperty(
        name="Chain Length", description="Number of bones in the IK chain", default=2, min=1
    )
    control_shape: bpy.props.EnumProperty(
        items=[
            ('CIRCLE', "Circle", ""),
            ('BOX', "Box", ""),
            ('SPHERE', "Sphere", ""),
        ],
        name="Shape",
        default='CIRCLE'
    )

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
    bpy.types.Scene.mech_rig_active_bone_index = bpy.props.IntProperty()

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_MechanicalRigger)
    bpy.utils.unregister_class(MECH_RIG_UL_BoneList)
    bpy.utils.unregister_class(MechRigBoneItem)
    bpy.utils.unregister_class(MechRigBoneSettings)
    del bpy.types.PoseBone.mech_rig_settings
    del bpy.types.Scene.mech_rig_symmetric_origin
    del bpy.types.Scene.mech_rig_active_bone_index
