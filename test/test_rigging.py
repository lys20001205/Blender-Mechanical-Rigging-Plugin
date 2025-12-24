import bpy
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

# Import plugin
from mechanical_rigger import operators, ui, utils

# Register
ui.register()
operators.register()

def test_rigging():
    # 1. Clear Scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    for c in bpy.data.collections:
        bpy.data.collections.remove(c)

    # 2. Setup Hierarchy
    # Collection: Body
    col_body = bpy.data.collections.new("Body")
    bpy.context.scene.collection.children.link(col_body)

    bpy.ops.mesh.primitive_cube_add(size=2)
    body = bpy.context.object
    body.name = "BodyMesh"
    col_body.objects.link(body)
    bpy.context.collection.objects.unlink(body)

    # Collection: Arm_Mirrored
    col_arm = bpy.data.collections.new("Arm_Mirrored")
    bpy.context.scene.collection.children.link(col_arm)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(2, 0, 0))
    arm = bpy.context.object
    arm.name = "ArmMesh"
    col_arm.objects.link(arm)
    bpy.context.collection.objects.unlink(arm)

    # Parent Arm to Body
    arm.parent = body

    # Create Symmetric Origin
    bpy.ops.object.empty_add()
    origin = bpy.context.object
    origin.name = "Origin"

    # Add Mirror Mod to Arm targeting Origin
    mod = arm.modifiers.new("Mirror", 'MIRROR')
    mod.mirror_object = origin

    # 3. Select Objects
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    arm.select_set(True)

    # Set Scene Prop
    bpy.context.scene.mech_rig_symmetric_origin = origin

    # 4. Run Auto Rig
    bpy.ops.mech_rig.auto_rig()

    # 5. Verify Results
    armature = bpy.context.scene.objects.get("MechRig")
    if not armature:
        print("FAIL: Armature not created")
        return

    print("PASS: Armature created")

    # Check Bones
    bone_names = armature.data.bones.keys()
    print(f"Bones: {bone_names}")

    if "Body" not in bone_names:
        print("FAIL: Body bone missing")
    if "Arm_L" not in bone_names:
        print("FAIL: Arm_L bone missing")
    if "Arm_R" not in bone_names:
        print("FAIL: Arm_R bone missing")

    # Check Mesh
    mesh = bpy.context.scene.objects.get("Rigged_Mesh")
    if not mesh:
        print("FAIL: Rigged Mesh not created")

    if "Arm_R_rigged" not in [v.name for v in mesh.data.vertices] and len(mesh.data.vertices) > 0:
        # Hard to check vertex origin, but we can check if vertex groups exist
        vgs = mesh.vertex_groups.keys()
        print(f"Vertex Groups: {vgs}")
        if "Arm_R" not in vgs:
            print("FAIL: Arm_R Vertex Group missing")

    # 6. Test Controls
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)

    # Set IK for Arm_L
    pbone = armature.pose.bones["Arm_L"]
    pbone.mech_rig_settings.use_ik = True
    pbone.mech_rig_settings.ik_chain_length = 1
    pbone.mech_rig_settings.control_shape = 'BOX'

    bpy.ops.mech_rig.add_controls()

    # Verify IK
    c = pbone.constraints.get("IK")
    if not c:
        print("FAIL: IK Constraint not added")
    else:
        print("PASS: IK Constraint added")

    if "Arm_L_IK" not in armature.data.bones:
        print("FAIL: IK Target Bone not created")

    print("Test Complete")

if __name__ == "__main__":
    test_rigging()
