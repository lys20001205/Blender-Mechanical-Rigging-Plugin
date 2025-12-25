import bpy
import mathutils
import math

# --- Data Structures for Analysis ---
class BoneNode:
    def __init__(self, name, origin_obj, parent=None, is_mirrored_side=None):
        self.name = name
        self.origin_obj = origin_obj  # The representative object
        self.parent = parent
        self.children = []
        self.is_mirrored_side = is_mirrored_side # None, 'L', or 'R'
        self.sibling_r = None

    def add_child(self, node):
        self.children.append(node)
        node.parent = self

# --- Step 1: Hierarchy Analysis ---

def analyze_hierarchy(selected_objects):
    """
    Builds a tree of BoneNodes based on Object Parent-Child relationships.
    Handles '_Mirrored' collections.
    """
    obj_to_col = {}
    for obj in selected_objects:
        if not obj.users_collection:
            raise ValueError(f"Object '{obj.name}' is not assigned to any Collection.")
        obj_to_col[obj] = obj.users_collection[0]

    roots = []
    selected_set = set(selected_objects)

    for obj in selected_objects:
        parent = obj.parent
        if parent is None or parent not in selected_set:
            roots.append(obj)

    if not roots:
        raise ValueError("Circular dependency or no root object found.")

    bone_tree_roots = []

    def traverse(obj, parent_node_l, parent_node_r):
        col = obj_to_col[obj]

        node_l = None
        node_r = None

        # Check if new bone needed
        is_new_bone = False
        if parent_node_l is None:
            is_new_bone = True
        else:
            if obj_to_col[parent_node_l.origin_obj] != col:
                is_new_bone = True

        if is_new_bone:
            is_mirrored_col = "_Mirrored" in col.name
            base_name = col.name.replace("_Mirrored", "")

            if is_mirrored_col:
                name_l = f"{base_name}_L"
                node_l = BoneNode(name_l, obj, is_mirrored_side='L')

                name_r = f"{base_name}_R"
                node_r = BoneNode(name_r, obj, is_mirrored_side='R')
                node_l.sibling_r = node_r

                if parent_node_l:
                    parent_node_l.add_child(node_l)
                else:
                    bone_tree_roots.append(node_l)

                if parent_node_r:
                    parent_node_r.add_child(node_r)
                elif parent_node_l:
                    parent_node_l.add_child(node_r)
                else:
                    bone_tree_roots.append(node_r)

            else:
                name = base_name
                node_l = BoneNode(name, obj, is_mirrored_side=None)

                if parent_node_l:
                    parent_node_l.add_child(node_l)
                else:
                    bone_tree_roots.append(node_l)

                node_r = None

        else:
            node_l = parent_node_l
            node_r = parent_node_r

        for child in obj.children:
            if child in selected_set:
                traverse(child, node_l, node_r)

    for root in roots:
        traverse(root, None, None)

    return bone_tree_roots

# --- Step 2: Mesh Processing ---

def process_meshes(context, rig_roots, symmetric_origin):
    """
    duplicates and prepares meshes.
    Handles 'Symmetric Origin' logic for Mirrored collections.
    """
    processed_objects = []

    col_objects = {}
    for obj in context.selected_objects:
        if obj.users_collection:
            c = obj.users_collection[0]
            if c not in col_objects:
                col_objects[c] = []
            col_objects[c].append(obj)

    def get_all_nodes(nodes):
        res = []
        for n in nodes:
            res.append(n)
            res.extend(get_all_nodes(n.children))
        return res
    all_nodes = get_all_nodes(rig_roots)

    processed_keys = set()

    # Deselect everything before destructive operations
    bpy.ops.object.select_all(action='DESELECT')

    for node in all_nodes:
        col = node.origin_obj.users_collection[0]
        key = (col.name, node.is_mirrored_side)

        if key in processed_keys:
            continue
        processed_keys.add(key)

        objs = col_objects.get(col, [])

        for obj in objs:
            has_mirror_mod = False
            mirror_mod = None
            for m in obj.modifiers:
                if m.type == 'MIRROR':
                    if symmetric_origin and m.mirror_object == symmetric_origin:
                        has_mirror_mod = True
                        mirror_mod = m
                        break

            # L-Side (and Center)
            if node.is_mirrored_side == 'L' or node.is_mirrored_side is None:
                new_obj = obj.copy()
                new_obj.data = obj.data.copy()
                context.collection.objects.link(new_obj)
                new_obj.name = f"{obj.name}_rigged"

                if node.is_mirrored_side == 'L' and has_mirror_mod:
                    new_obj.modifiers.remove(new_obj.modifiers[mirror_mod.name])

                bpy.ops.object.select_all(action='DESELECT')
                new_obj.select_set(True)
                bpy.context.view_layer.objects.active = new_obj

                depsgraph = context.evaluated_depsgraph_get()
                obj_eval = new_obj.evaluated_get(depsgraph)
                mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)

                if new_obj.type != 'MESH':
                    new_mesh_obj = bpy.data.objects.new(new_obj.name, mesh_from_eval)
                    new_mesh_obj.matrix_world = new_obj.matrix_world
                    context.collection.objects.link(new_mesh_obj)
                    bpy.data.objects.remove(new_obj, do_unlink=True)
                    new_obj = new_mesh_obj
                    bpy.ops.object.select_all(action='DESELECT')
                    new_obj.select_set(True)
                    bpy.context.view_layer.objects.active = new_obj
                else:
                    new_obj.data = mesh_from_eval
                    new_obj.modifiers.clear()

                new_obj['mech_bone_name'] = node.name
                processed_objects.append(new_obj)

            # R-Side
            if node.is_mirrored_side == 'R':
                if has_mirror_mod:
                    new_obj = obj.copy()
                    new_obj.data = obj.data.copy()
                    context.collection.objects.link(new_obj)
                    new_obj.name = f"{obj.name}_R_rigged"

                    new_obj.modifiers.remove(new_obj.modifiers[mirror_mod.name])

                    bpy.ops.object.select_all(action='DESELECT')
                    new_obj.select_set(True)
                    bpy.context.view_layer.objects.active = new_obj

                    depsgraph = context.evaluated_depsgraph_get()
                    obj_eval = new_obj.evaluated_get(depsgraph)
                    mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)

                    if new_obj.type != 'MESH':
                        new_mesh_obj = bpy.data.objects.new(new_obj.name, mesh_from_eval)
                        new_mesh_obj.matrix_world = new_obj.matrix_world
                        context.collection.objects.link(new_mesh_obj)
                        bpy.data.objects.remove(new_obj, do_unlink=True)
                        new_obj = new_mesh_obj
                        bpy.ops.object.select_all(action='DESELECT')
                        new_obj.select_set(True)
                        bpy.context.view_layer.objects.active = new_obj
                    else:
                        new_obj.data = mesh_from_eval
                        new_obj.modifiers.clear()

                    origin_matrix = symmetric_origin.matrix_world
                    mat_world = new_obj.matrix_world
                    mat_local = origin_matrix.inverted() @ mat_world

                    mirror_mat = mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
                    mat_local_mirrored = mirror_mat @ mat_local

                    new_obj.matrix_world = origin_matrix @ mat_local_mirrored
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.flip_normals()
                    bpy.ops.object.mode_set(mode='OBJECT')

                    new_obj['mech_bone_name'] = node.name
                    processed_objects.append(new_obj)

    return processed_objects

# --- Step 3: Armature Creation ---

def create_armature(context, rig_roots, symmetric_origin):
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
    amt_obj = context.object
    amt = amt_obj.data
    amt.name = "MechRig"

    node_to_bone = {}

    def get_mirrored_matrix(obj_matrix, origin_matrix):
        mat_local = origin_matrix.inverted() @ obj_matrix
        mirror_mat = mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
        mat_local_mirrored = mirror_mat @ mat_local
        return origin_matrix @ mat_local_mirrored

    def calculate_bone_head(node):
        """Helper to calculate the head position for a node."""
        obj = node.origin_obj
        mat = obj.matrix_world

        final_head = mat.translation

        if node.is_mirrored_side == 'R' and symmetric_origin:
            mirrored_mat = get_mirrored_matrix(mat, symmetric_origin.matrix_world)
            final_head = mirrored_mat.translation

        return final_head

    def create_bones_recursive(nodes, parent_bone=None):
        for node in nodes:
            bone = amt.edit_bones.new(node.name)

            obj = node.origin_obj
            mat = obj.matrix_world

            final_head = calculate_bone_head(node)

            # Align Bone to Object's Local Z axis (Y of bone = Z of object)
            z_axis = mat.col[2].xyz.normalized()

            # Readability: Use max dimension or scale, with minimum
            length = max(obj.dimensions.length * 0.5, 0.2)

            final_tail = final_head + (z_axis * length)

            # Handle Mirroring for Vector/Tail
            if node.is_mirrored_side == 'R' and symmetric_origin:
                origin_mat = symmetric_origin.matrix_world
                z_local = origin_mat.inverted().to_3x3() @ z_axis
                z_local.x *= -1 # Mirror X
                z_mirrored = origin_mat.to_3x3() @ z_local

                final_tail = final_head + (z_mirrored * length)

            bone.head = final_head
            bone.tail = final_tail

            # Align Bone Z to Object X (mat.col[0]) for consistency
            x_axis = mat.col[0].xyz.normalized()
            if node.is_mirrored_side == 'R' and symmetric_origin:
                origin_mat = symmetric_origin.matrix_world
                x_local = origin_mat.inverted().to_3x3() @ x_axis
                x_local.x *= -1
                x_mirrored = origin_mat.to_3x3() @ x_local
                bone.align_roll(x_mirrored)
            else:
                bone.align_roll(x_axis)

            if parent_bone:
                bone.parent = parent_bone
                bone.use_connect = False # Disable connection

            node_to_bone[node] = bone.name
            create_bones_recursive(node.children, bone)

    create_bones_recursive(rig_roots)

    bpy.ops.object.mode_set(mode='POSE')
    for node, bone_name in node_to_bone.items():
        pbone = amt_obj.pose.bones.get(bone_name)
        if not pbone: continue

        # Apply Hinge Constraints (Rotation limited to Y axis of Bone = Z axis of Object)
        if node.name.startswith("Hinge_") or node.origin_obj.name.startswith("Hinge_"):
            c = pbone.constraints.new('LIMIT_ROTATION')
            # Limit Rotation is Local to Bone.
            # Bone Y is Object Z.
            # We want to Allow Rotation around Object Z (Bone Y).
            # So Allow Y. Lock X and Z.
            c.use_limit_x = True
            c.use_limit_y = False
            c.use_limit_z = True
            c.owner_space = 'LOCAL'

    bpy.ops.object.mode_set(mode='OBJECT')
    amt_obj.show_in_front = True
    return amt_obj

def finalize_mesh_and_skin(context, processed_objects, armature, original_selection):
    """
    Combines meshes, creates 'Armature' collection, hides original objects.
    """
    if not processed_objects:
        return

    # Assign Vertex Groups BEFORE join
    for obj in processed_objects:
        bone_name = obj.get('mech_bone_name')
        if bone_name:
            vg = obj.vertex_groups.new(name=bone_name)
            verts = [v.index for v in obj.data.vertices]
            vg.add(verts, 1.0, 'REPLACE')

    # Join
    bpy.ops.object.select_all(action='DESELECT')
    for o in processed_objects:
        o.select_set(True)

    context.view_layer.objects.active = processed_objects[0]
    bpy.ops.object.join()

    combined_mesh = processed_objects[0]
    combined_mesh.name = "Rigged_Mesh"
    combined_mesh.display_type = 'SOLID'

    combined_mesh.parent = armature
    mod = combined_mesh.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = armature

    # --- Collection Management ---

    # Create or Get "Armature" Collection
    armature_col_name = "Armature"
    if armature_col_name in bpy.data.collections:
        armature_col = bpy.data.collections[armature_col_name]
        # Ensure it is linked to the scene
        if armature_col.name not in context.scene.collection.children:
            context.scene.collection.children.link(armature_col)
    else:
        armature_col = bpy.data.collections.new(armature_col_name)
        context.scene.collection.children.link(armature_col)

    def ensure_in_collection(obj, target_col):
        for col in list(obj.users_collection):
            if col != target_col:
                col.objects.unlink(obj)
        if target_col not in obj.users_collection:
            target_col.objects.link(obj)

    ensure_in_collection(armature, armature_col)
    ensure_in_collection(combined_mesh, armature_col)

    # --- Hide Original Objects ---
    if original_selection:
        for obj in original_selection:
            obj.hide_viewport = True
            obj.hide_render = True

# --- Step 4: Controls ---

def get_or_create_widget(name, type='CIRCLE'):
    if name in bpy.data.objects:
        return bpy.data.objects[name]

    if type == 'CIRCLE':
        bpy.ops.curve.primitive_nurbs_circle_add(radius=1.0)
        # Circles are aligned to Global XY. Bone Y is the axis.
        # We want the circle to be in the XZ plane (Normal Y).
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        # Rotate 90 degrees around X axis
        bpy.ops.transform.rotate(value=math.radians(90), orient_axis='X')
        bpy.ops.object.mode_set(mode='OBJECT')

    elif type == 'BOX':
        bpy.ops.mesh.primitive_cube_add(size=1.0) # 1.0 size = 0.5 radius
        bpy.context.object.display_type = 'WIRE'
    elif type == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5)
        bpy.context.object.display_type = 'WIRE'

    obj = bpy.context.active_object
    obj.name = name

    if "Widgets" not in bpy.data.collections:
        widgets_col = bpy.data.collections.new("Widgets")
        bpy.context.scene.collection.children.link(widgets_col)
    else:
        widgets_col = bpy.data.collections["Widgets"]

    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    widgets_col.objects.link(obj)
    obj.hide_render = True

    return obj

def ensure_bone_collection(armature_data, name):
    """
    Get or create a BoneCollection (Blender 4.0+)
    """
    col = armature_data.collections.get(name)
    if not col:
        col = armature_data.collections.new(name)
    return col

def apply_controls(context, armature):
    """
    Batched processing to avoid mode switching inside loops.
    """
    # ---------------------------------------------------------
    # PASS 1: ANALYSIS (Pose Mode)
    # Collect data on what needs to be done.
    # ---------------------------------------------------------
    bpy.ops.object.mode_set(mode='POSE')

    # Bone Groups were removed in 4.0. Replaced by Bone Collections.
    coll_left = ensure_bone_collection(armature.data, "Left")
    coll_right = ensure_bone_collection(armature.data, "Right")
    coll_center = ensure_bone_collection(armature.data, "Center")

    ik_tasks = [] # List of (bone_name, ik_target_name, chain_length, settings)

    # First pass: Set up Visuals (Color, Shape) and Identify IK needs
    for pbone in armature.pose.bones:
        settings = pbone.mech_rig_settings

        # Determine Color & Collection
        target_coll = coll_center
        color_theme = 'THEME09' # Yellow

        if pbone.name.endswith("_L") or ".L" in pbone.name:
            target_coll = coll_left
            color_theme = 'THEME01' # Red
        elif pbone.name.endswith("_R") or ".R" in pbone.name:
            target_coll = coll_right
            color_theme = 'THEME04' # Blue/Purple

        # Assign Collection
        if pbone.bone.name not in [b.name for b in target_coll.bones]:
             target_coll.assign(pbone.bone)

        # Assign Color
        pbone.color.palette = color_theme

        # Custom Shape Assignment
        shape_type = settings.control_shape
        if shape_type != 'NONE':
            widget_name = f"WGT_Bone_{shape_type}"
            # Creating widget changes active object, restore armature immediately
            widget_obj = get_or_create_widget(widget_name, shape_type)
            context.view_layer.objects.active = armature

            pbone.custom_shape = widget_obj
            pbone.custom_shape_scale_xyz = (pbone.length, pbone.length, pbone.length)
            pbone.custom_shape_translation = (0, pbone.length * 0.5, 0)
        else:
            pbone.custom_shape = None

        # Check for IK requirement
        if settings.use_ik:
            has_ik_constraint = False
            for c in pbone.constraints:
                if c.type == 'IK':
                    has_ik_constraint = True
                    # If exists, just update chain length later?
                    # For simplicity, we assume we configure everything if requested.
                    break

            if not has_ik_constraint:
                ik_tasks.append({
                    'bone_name': pbone.name,
                    'ik_target_name': f"{pbone.name}_IK",
                    'chain_length': settings.ik_chain_length,
                    'color_theme': color_theme,
                    'target_coll_name': target_coll.name
                })
            else:
                # Update existing chain length
                for c in pbone.constraints:
                    if c.type == 'IK':
                        c.chain_count = settings.ik_chain_length

    # ---------------------------------------------------------
    # PASS 2: STRUCTURE (Edit Mode)
    # Create IK Target Bones
    # ---------------------------------------------------------
    if ik_tasks:
        bpy.ops.object.mode_set(mode='EDIT')
        amt = armature.data

        for task in ik_tasks:
            bone_name = task['bone_name']
            target_name = task['ik_target_name']

            if bone_name in amt.edit_bones:
                bone = amt.edit_bones[bone_name]
                if target_name not in amt.edit_bones:
                    ik_bone = amt.edit_bones.new(target_name)
                    ik_bone.head = bone.tail
                    # Align IK bone similar to bone
                    ik_bone.tail = bone.tail + (bone.tail - bone.head).normalized() * (bone.length * 0.5)
                    ik_bone.parent = None
                    ik_bone.use_deform = False

    # ---------------------------------------------------------
    # PASS 3: CONSTRAINTS & DRIVERS (Pose Mode)
    # Apply IK Constraints and setup Drivers
    # ---------------------------------------------------------
    bpy.ops.object.mode_set(mode='POSE')

    # Must re-fetch collections as objects might have been reallocated
    coll_map = {c.name: c for c in armature.data.collections}

    for task in ik_tasks:
        bone_name = task['bone_name']
        target_name = task['ik_target_name']
        chain_len = task['chain_length']
        theme = task['color_theme']
        coll_name = task['target_coll_name']

        pbone = armature.pose.bones.get(bone_name)
        ik_pbone = armature.pose.bones.get(target_name)

        if pbone and ik_pbone:
            # 1. Apply Constraint
            c = pbone.constraints.new('IK')
            c.target = armature
            c.subtarget = target_name
            c.chain_count = chain_len

            # 2. Setup IK-FK Switch Property on Target
            prop_name = "IK_FK"
            if prop_name not in ik_pbone:
                ik_pbone[prop_name] = 1.0
                ik_pbone.id_properties_ui(prop_name).update(min=0.0, max=1.0)

            # 3. Driver
            d = c.driver_add("influence")
            d.driver.type = 'AVERAGE'
            var = d.driver.variables.new()
            var.name = "var"
            var.type = 'SINGLE_PROP'
            var.targets[0].id = armature
            var.targets[0].data_path = f'pose.bones["{target_name}"]["{prop_name}"]'

            # 4. Visuals for IK Target
            # Shape
            widget_obj = get_or_create_widget("WGT_Bone_BOX", 'BOX')
            context.view_layer.objects.active = armature # Restore after widget creation

            ik_pbone.custom_shape = widget_obj
            ik_pbone.custom_shape_scale_xyz = (1.5, 1.5, 1.5)
            ik_pbone.custom_shape_translation = (0, 0, 0)

            # Color
            ik_pbone.color.palette = theme

            # Collection
            if coll_name in coll_map:
                target_coll = coll_map[coll_name]
                if ik_pbone.bone.name not in [b.name for b in target_coll.bones]:
                    target_coll.assign(ik_pbone.bone)
