import bpy
import mathutils
import math
import re

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

# --- Step 0: Validation ---
def validate_selection(context):
    """
    Checks selected objects for common errors.
    Returns a list of error strings. If empty, validation passed.
    """
    errors = []
    selected_objects = context.selected_objects
    symmetric_origin = context.scene.mech_rig_symmetric_origin

    if not selected_objects:
        return ["No objects selected."]

    # 1. Mirroring Requirements
    uses_mirrored_collection = False
    for obj in selected_objects:
        for col in obj.users_collection:
            if "_Mirrored" in col.name:
                uses_mirrored_collection = True
                break
        if uses_mirrored_collection:
            break

    if uses_mirrored_collection and not symmetric_origin:
        errors.append("'_Mirrored' collection used but no 'Symmetric Origin' set in panel.")

    # 3. Piston Pairing Check
    # Convention: Collection Name matches Piston_<ID>_Cyl or Piston_<ID>_Rod
    pistons = {}

    # Regex to find Piston_ID_Type in Collection Name
    piston_pattern = re.compile(r"Piston_(.+?)_(Cyl|Rod)")

    # Identify involved collections first to avoid double counting objects
    scanned_collections = set()

    for obj in selected_objects:
        if not obj.users_collection: continue
        col = obj.users_collection[0]
        if col in scanned_collections: continue
        scanned_collections.add(col)

        # Check Collection Name
        col_name = col.name
        # Strip _Mirrored for check?
        clean_col_name = col_name.replace("_Mirrored", "")

        match = piston_pattern.match(clean_col_name)

        if match:
            pid = match.group(1)
            ptype = match.group(2) # Cyl or Rod

            if pid not in pistons:
                pistons[pid] = set()

            pistons[pid].add(ptype)

    # 4. Hinge in Piston Check (Not strictly an error, but good to know)
    # If using Pistons, ensure Hinge objects exist for proper alignment? 
    # Not mandatory, but prevents "bad alignment" complaints.

    for pid, types in pistons.items():
        # Check for incomplete pairs
        if "Cyl" in types and "Rod" not in types:
            errors.append(f"Piston '{pid}' has Cyl but missing Rod (Piston_{pid}_Rod).")
        if "Rod" in types and "Cyl" not in types:
            errors.append(f"Piston '{pid}' has Rod but missing Cyl (Piston_{pid}_Cyl).")

    return errors

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

            # IMPORTANT: If we are staying in the same bone (node), checks if this object 
            # is a better representative for the pivot (e.g., "Hinge_...").
            # If so, update the origin_obj.
            if node_l and obj.name.startswith("Hinge_"):
                node_l.origin_obj = obj
                if node_r:
                    node_r.origin_obj = obj

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
                else:
                    new_obj.data = mesh_from_eval
                    new_obj.modifiers.clear()

                # Automatically apply scale to the copy to ensure clean 1,1,1 scale for export
                # This avoids users needing to apply scale on linked data.

                # CRITICAL: Ensure we are operating ONLY on the new copy
                bpy.ops.object.select_all(action='DESELECT')
                new_obj.select_set(True)
                bpy.context.view_layer.objects.active = new_obj

                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

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

    # -------------------------------------------------------------
    # PRE-PASS: Identify Piston Targets for Look-At Alignment
    # -------------------------------------------------------------
    piston_map = {} # Map ID -> {Cyl: node, Rod: node}

    # Helper to traverse tree and build map
    def collect_pistons(nodes):
        for node in nodes:
            # Check if this node comes from a Piston Collection
            # Collection Name logic from validate_selection
            col = node.origin_obj.users_collection[0]
            col_name = col.name.replace("_Mirrored", "")

            match = re.match(r"Piston_(.+?)_(Cyl|Rod)", col_name)
            if match:
                pid = match.group(1)
                ptype = match.group(2)

                # We need to handle Side (L/R) if mirrored
                # Node stores is_mirrored_side
                side_suffix = ""
                if node.is_mirrored_side == 'L': side_suffix = "_L"
                elif node.is_mirrored_side == 'R': side_suffix = "_R"

                # Make a unique key for this piston instance
                instance_key = f"{pid}{side_suffix}"

                if instance_key not in piston_map:
                    piston_map[instance_key] = {}
                piston_map[instance_key][ptype] = node

            collect_pistons(node.children)

    collect_pistons(rig_roots)

    # -------------------------------------------------------------
    # RECURSIVE BONE CREATION (Updated for Pistons)
    # -------------------------------------------------------------

    def create_bones_recursive(nodes, parent_bone=None):
        for node in nodes:
            bone = amt.edit_bones.new(node.name)

            obj = node.origin_obj
            mat = obj.matrix_world

            final_head = calculate_bone_head(node)
            final_tail = None # Will calculate

            # Check if Piston
            is_piston_node = False
            # Re-check regex or lookup in map? Map is faster/cleaner if we reverse lookup?
            # Or just do regex again.
            col = node.origin_obj.users_collection[0]
            col_name = col.name.replace("_Mirrored", "")
            piston_match = re.match(r"Piston_(.+?)_(Cyl|Rod)", col_name)

            if piston_match:
                is_piston_node = True
                pid = piston_match.group(1)
                ptype = piston_match.group(2)

                side_suffix = ""
                if node.is_mirrored_side == 'L': side_suffix = "_L"
                elif node.is_mirrored_side == 'R': side_suffix = "_R"

                instance_key = f"{pid}{side_suffix}"

                # Find Target
                target_type = "Rod" if ptype == "Cyl" else "Cyl"
                target_node = piston_map.get(instance_key, {}).get(target_type)

                if target_node:
                    # Calculate Vector to Target Head
                    target_head = calculate_bone_head(target_node)
                    vec = target_head - final_head

                    # Length? Use vector length or Object dimension?
                    # Using vector length makes the bone touch the target pivot.
                    # This is visually clean for pistons.
                    # But if distance is zero (overlap), fallback.
                    dist = vec.length
                    if dist < 0.001:
                        # Fallback
                        length = max(obj.dimensions.length * 0.5, 0.2)
                        z_axis = mat.col[2].xyz.normalized()
                        vec = z_axis * length

                    final_tail = final_head + vec

                    # Align Bone Z to Hinge Z (Roll)
                    # Hinge Z is obj.matrix_world.col[2]
                    # We want rotation around this axis.
                    hinge_z = mat.col[2].xyz.normalized()

                    # Handle Mirroring for Hinge Axis
                    if node.is_mirrored_side == 'R' and symmetric_origin:
                        origin_mat = symmetric_origin.matrix_world
                        z_local = origin_mat.inverted().to_3x3() @ hinge_z
                        z_local.x *= -1 # Mirror X
                        z_mirrored = origin_mat.to_3x3() @ z_local
                        hinge_z = z_mirrored

                    bone.head = final_head
                    bone.tail = final_tail
                    bone.align_roll(hinge_z)

            if not is_piston_node:
                # STANDARD LOGIC
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

def apply_piston_constraints(armature, pbone):
    """
    Checks if this bone is part of a Piston pair and applies constraints.
    Returns True if processed as Piston (to avoid adding default controls).
    """
    name = pbone.name
    # Piston_<ID>_<Type>
    # Note: Regex needs to handle potential .L/.R suffixes from mirroring
    # Pattern: Piston_{ID}_{Type}(_{Side})?

    # Simple check first
    if "Piston_" not in name:
        return False

    # Regex to parse ID and Type
    # Match "Piston_" then (Group 1: ID) then "_" then (Group 2: Cyl|Rod)
    # Then optional suffix
    # Examples: Piston_Elbow_Cyl, Piston_Elbow_Rod, Piston_Elbow_Cyl_L
    match = re.search(r"Piston_(.+?)_(Cyl|Rod)", name)
    if not match:
        return False

    pid = match.group(1)
    ptype = match.group(2) # "Cyl" or "Rod"

    # Construct target name
    target_type = "Rod" if ptype == "Cyl" else "Cyl"

    # We need to find the target bone name.
    # If the current bone has a suffix (like _L, .L, _R), the target should too.
    # The regex extracted ID and Type from the base.
    # Let's verify suffix.
    suffix = name[match.end():] # e.g. "_L" or ""

    target_name_base = f"Piston_{pid}_{target_type}"
    target_name = target_name_base + suffix

    target_bone = armature.pose.bones.get(target_name)
    if not target_bone:
        print(f"Piston warning: Target '{target_name}' not found for '{name}'")
        return False

    # Apply Damped Track (or Track To)
    # Damped Track is usually more stable for simple pointing.
    # We want Z axis of bone (Y of bone is length?) 
    # Standard Bone: Y is length axis.
    # So we want Y to point at Target.

    # Check if constraints exist

    # 1. Look At (Damped Track)
    track_cons_name = "Piston_Track"
    if track_cons_name not in pbone.constraints:
        c = pbone.constraints.new('DAMPED_TRACK')
        c.name = track_cons_name
        c.target = armature
        c.subtarget = target_name
        c.track_axis = 'TRACK_Y' # Bone Y points to target
        c.influence = 1.0

    # 2. Limit Rotation (Keep it planar/hinged)
    # We aligned Bone Z to Hinge Z in create_armature.
    # So we want to allow rotation around Z, but lock X and Y (Twist).
    limit_cons_name = "Piston_Limit"
    if limit_cons_name not in pbone.constraints:
        c = pbone.constraints.new('LIMIT_ROTATION')
        c.name = limit_cons_name
        c.owner_space = 'LOCAL'

        # Lock X (Sideways tilt)
        c.use_limit_x = True
        c.min_x = 0
        c.max_x = 0

        # Lock Y (Twist along barrel) - Usually desireable for pistons
        c.use_limit_y = True
        c.min_y = 0
        c.max_y = 0

        # Allow Z (Hinge rotation)
        c.use_limit_z = False

    return True

def apply_controls(context, armature):
    """
    Batched processing to avoid mode switching inside loops.
    """
    # ---------------------------------------------------------
    # PASS 1: ANALYSIS (Pose Mode)
    # Collect data on what needs to be done.
    # ---------------------------------------------------------
    bpy.ops.object.mode_set(mode='POSE')

    coll_left = ensure_bone_collection(armature.data, "Left")
    coll_right = ensure_bone_collection(armature.data, "Right")
    coll_center = ensure_bone_collection(armature.data, "Center")
    coll_mech = ensure_bone_collection(armature.data, "Mechanics") # For Pistons

    ik_tasks = [] # List of (bone_name, ik_target_name, pole_target_name, chain_length, settings)

    # Lists for Cleanup (Store DATA, not Objects, as Edit Mode invalidates objects)
    cleanup_ik_bones = [] # Names of _IK and _Pole bones to remove
    cleanup_ik_constraints = [] # Tuples of (bone_name, constraint_name/type) to remove

    # Lists for Config
    update_ik_locks = [] # List of dicts with bone_name and lock settings

    global_scale = context.scene.mech_rig_widget_scale

    # First pass: Set up Visuals (Color, Shape) and Identify IK needs
    for pbone in armature.pose.bones:
        # Check if this is an IK/Pole bone to avoid overwriting shapes
        if pbone.name.endswith("_IK") or pbone.name.endswith("_Pole"):
            continue

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

        # Piston Logic
        is_piston = apply_piston_constraints(armature, pbone)
        if is_piston:
            target_coll = coll_mech
            color_theme = 'THEME10' # Orange/Brown for mechanics?
            # Assign Collection
            if pbone.bone.name not in [b.name for b in target_coll.bones]:
                target_coll.assign(pbone.bone)

            pbone.color.palette = color_theme

            # Pistons usually don't need control widgets, but maybe a simple one?
            # Or none? Let's default to None or a small Box.
            # Let's skip widget generation for pistons to keep it clean.
            pbone.custom_shape = None

            # Skip IK logic for pistons
            continue

        # Normal Bone Logic

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

            if settings.override_transform:
                pbone.custom_shape_scale_xyz = settings.visual_scale
                pbone.custom_shape_translation = settings.visual_location
                pbone.custom_shape_rotation_euler = settings.visual_rotation
            else:
                # Use Global Scale (Default)
                scale_val = pbone.length * global_scale
                scale_vec = (scale_val, scale_val, scale_val)
                # User Request: Place control at the head (0,0,0) not center
                loc_vec = (0, 0, 0)
                rot_vec = (0, 0, 0)

                pbone.custom_shape_scale_xyz = scale_vec
                pbone.custom_shape_translation = loc_vec
                pbone.custom_shape_rotation_euler = rot_vec

                # Write back calculated defaults so UI is accurate if user switches to Custom
                settings.visual_scale = scale_vec
                settings.visual_location = loc_vec
                settings.visual_rotation = rot_vec

        else:
            pbone.custom_shape = None

        # IK Logic
        ik_target_name = f"{pbone.name}_IK"
        pole_target_name = f"{pbone.name}_Pole"

        if settings.use_ik:
            # 1. Check if constraint needs adding
            has_ik_constraint = False
            # REVERT: Constraint owner is pbone (Self), not Parent
            constraint_owner = pbone

            for c in pbone.constraints:
                 if c.type == 'IK' and c.target == armature and c.subtarget == ik_target_name:
                    has_ik_constraint = True
                    c.chain_count = settings.ik_chain_length
                    break

            if not has_ik_constraint:
                # NEW STRATEGY: Split IK Control (Head) and Solver Target (Tail)
                ik_tasks.append({
                    'bone_name': pbone.name,
                    'ik_target_name': ik_target_name, # The Control Bone
                    'solver_target_name': f"{pbone.name}_IK_Target", # The Hidden Solver Bone
                    'pole_target_name': pole_target_name,
                    'chain_length': settings.ik_chain_length,
                    'color_theme': color_theme,
                    'target_coll_name': target_coll.name
                })

            # 2. Collect Locking Tasks (Traverse parents)
            # We need to lock axes on parents if they have Limit Rotation constraints
            # If constraint is on pbone (Chain 0), parent is Chain 1.
            curr_bone = pbone.parent if pbone.parent else None # Chain count starts from pbone if it has IK?
            # Actually, Blender IK Chain Count includes the owner.
            # 1 = Owner only.
            # 2 = Owner + Parent.

            # Locking applies to the CHAIN.
            # We start checking from Owner? Or Parent?
            # Usually we don't lock the Owner if it's the tip (unless it has limits).

            curr_bone = pbone # Start at owner

            for _ in range(settings.ik_chain_length):
                if not curr_bone: break

                # Check Limit Rotation
                for c in curr_bone.constraints:
                    if c.type == 'LIMIT_ROTATION':
                        # Store DATA only
                        lock_data = {
                            'bone_name': curr_bone.name,
                            'use_limit_x': c.use_limit_x,
                            'min_x': c.min_x, 'max_x': c.max_x,
                            'use_limit_y': c.use_limit_y,
                            'min_y': c.min_y, 'max_y': c.max_y,
                            'use_limit_z': c.use_limit_z,
                            'min_z': c.min_z, 'max_z': c.max_z,
                        }
                        update_ik_locks.append(lock_data)

                if curr_bone.parent:
                    curr_bone = curr_bone.parent
                else:
                    break

        else:
            # Cleanup Dead IK
            # 1. Mark Constraint for removal (Check Self)
            target_bones = [pbone]
            # No need to check parent for this specific implementation logic anymore

            for b in target_bones:
                for c in b.constraints:
                    if c.type == 'IK' and c.subtarget == ik_target_name:
                         cleanup_ik_constraints.append((b.name, c.name))

            # 2. Mark Target Bones for removal if they exist
            if ik_target_name in armature.pose.bones:
                cleanup_ik_bones.append(ik_target_name)

            solver_target_name = f"{pbone.name}_IK_Target"
            if solver_target_name in armature.pose.bones:
                cleanup_ik_bones.append(solver_target_name)

            if pole_target_name in armature.pose.bones:
                cleanup_ik_bones.append(pole_target_name)

    # ---------------------------------------------------------
    # PASS 2: STRUCTURE (Edit Mode)
    # Create/Remove Bones
    # ---------------------------------------------------------

    needs_edit_mode = bool(ik_tasks) or bool(cleanup_ik_bones)

    if needs_edit_mode:
        bpy.ops.object.mode_set(mode='EDIT')
        amt = armature.data

        # Cleanup
        for name in cleanup_ik_bones:
            if name in amt.edit_bones:
                bone = amt.edit_bones[name]
                amt.edit_bones.remove(bone)

        # Creation
        for task in ik_tasks:
            bone_name = task['bone_name']
            target_name = task['ik_target_name']
            solver_name = task['solver_target_name']
            pole_name = task['pole_target_name']

            if bone_name in amt.edit_bones:
                bone = amt.edit_bones[bone_name]

                # 1. Create Control Bone (at Head)
                if target_name not in amt.edit_bones:
                    ctrl_bone = amt.edit_bones.new(target_name)
                    ctrl_bone.head = bone.head
                    ctrl_bone.tail = bone.head + (bone.tail - bone.head).normalized() * (bone.length * 0.5)
                    ctrl_bone.parent = None
                    ctrl_bone.use_deform = False
                    ctrl_bone.roll = bone.roll
                else:
                    ctrl_bone = amt.edit_bones[target_name]

                # 2. Create Solver Target Bone (at Tail, parented to Control)
                if solver_name not in amt.edit_bones:
                    solver_bone = amt.edit_bones.new(solver_name)
                    solver_bone.head = bone.tail
                    # Align to global axes or bone? Standard IK target usually aligns to bone.
                    solver_bone.tail = bone.tail + (bone.tail - bone.head).normalized() * (bone.length * 0.2)
                    solver_bone.parent = ctrl_bone # Parenting allows orbiting behavior
                    solver_bone.use_deform = False
                    solver_bone.roll = bone.roll # Align roll

                # Pole Target
                # Calculate Pole Position (Updated for Standard IK)
                # Chain includes Bone and Parent.
                # Joint is at Bone.Head (which is Parent.Tail).

                pole_pos = None

                if task['chain_length'] >= 2 and bone.parent:
                    # Standard 2-bone chain
                    parent = bone.parent

                    # Top: parent.head
                    # Joint: bone.head (where the bend happens)
                    # End: bone.tail

                    top = parent.head
                    joint = bone.head
                    end = bone.tail

                    # Vector from top to joint
                    v_upper = joint - top
                    # Vector from joint to end
                    v_lower = end - joint

                    # Projected point of Joint onto Line(Top -> End)
                    line_vec = end - top
                    line_len_sq = line_vec.length_squared

                    if line_len_sq > 0.0001:
                        # Project Joint relative to Top onto Line
                        proj_factor = (joint - top).dot(line_vec) / line_len_sq
                        proj_point = top + line_vec * proj_factor

                        # Orthogonal Vector (Bend Direction)
                        bend_dir = joint - proj_point

                        if bend_dir.length > 0.001:
                             # Chain is bent, use this direction
                             pole_dir = bend_dir.normalized()
                             # Place pole out from joint
                             pole_pos = joint + pole_dir * (v_upper.length + v_lower.length) * 0.5
                        else:
                             # Chain is straight (collinear)
                             # Use Bone's X axis (usually forward/side depending on roll)
                             # In EditBone, we have x_axis.
                             # If X is the hinge axis (or Z?), we push along the other?
                             # Let's push along local X.
                             pole_pos = joint + bone.x_axis * (v_upper.length + v_lower.length) * 0.5
                    else:
                        # Zero length chain?
                         pole_pos = joint + mathutils.Vector((0, 1, 0))

                else:
                    # Fallback
                    pole_pos = bone.head + mathutils.Vector((0, 1, 0))

                if pole_name not in amt.edit_bones:
                    pole_bone = amt.edit_bones.new(pole_name)
                    pole_bone.head = pole_pos
                    pole_bone.tail = pole_pos + mathutils.Vector((0, 0, 0.2))
                    pole_bone.parent = None
                    pole_bone.use_deform = False

    # ---------------------------------------------------------
    # PASS 3: CONSTRAINTS & DRIVERS (Pose Mode)
    # Apply IK Constraints, setup Drivers, Remove Constraints, Apply Locks
    # ---------------------------------------------------------
    bpy.ops.object.mode_set(mode='POSE')

    # 1. Cleanup Constraints
    for bone_name, constraint_name in cleanup_ik_constraints:
        real_pbone = armature.pose.bones.get(bone_name)
        if real_pbone:
            # Remove by name if possible, or type 'IK'
            to_remove = []
            for const in real_pbone.constraints:
                if const.type == 'IK' and const.name == constraint_name:
                    to_remove.append(const)

            for const in to_remove:
                real_pbone.constraints.remove(const)

    # 2. Apply/Setup New IK
    coll_map = {c.name: c for c in armature.data.collections}

    for task in ik_tasks:
        bone_name = task['bone_name']
        target_name = task['ik_target_name']
        pole_name = task['pole_target_name']
        chain_len = task['chain_length']
        theme = task['color_theme']
        coll_name = task['target_coll_name']

        pbone = armature.pose.bones.get(bone_name)
        ik_pbone = armature.pose.bones.get(target_name)
        pole_pbone = armature.pose.bones.get(pole_name)

        # Determine Constraint Owner (Self)
        owner_pbone = pbone

        if owner_pbone and ik_pbone:
            # Get Solver Bone
            solver_name = task['solver_target_name']
            solver_pbone = armature.pose.bones.get(solver_name)

            if solver_pbone:
                # Hide Solver Bone
                solver_pbone.bone.hide = True

                # Apply Constraint (Targeting Solver Bone)
                c = owner_pbone.constraints.new('IK')
                c.target = armature
                c.subtarget = solver_name # Reach for the hidden tail bone

                # Enable Rotation tracking
                c.use_rotation = True

                # Mechanical Rigging: Do not force Pole Target by default.
                # if pole_pbone:
                #    c.pole_target = armature
                #    c.pole_subtarget = pole_name
                #    c.pole_angle = 0

                c.chain_count = chain_len

                # Setup IK-FK Switch Property on Control Target
                prop_name = "IK_FK"
                if prop_name not in ik_pbone:
                    ik_pbone[prop_name] = 1.0
                    ik_pbone.id_properties_ui(prop_name).update(min=0.0, max=1.0)

                # Driver (Influence)
                d = c.driver_add("influence")
                d.driver.type = 'AVERAGE'
                var = d.driver.variables.new()
                var.name = "var"
                var.type = 'SINGLE_PROP'
                var.targets[0].id = armature
                var.targets[0].data_path = f'pose.bones["{target_name}"]["{prop_name}"]'

                # Visuals for IK Control (No Offset Needed)
                widget_obj = get_or_create_widget("WGT_Bone_BOX", 'BOX')
                context.view_layer.objects.active = armature

                ik_pbone.custom_shape = widget_obj
                base_ik_scale = 1.5 * global_scale
                ik_pbone.custom_shape_scale_xyz = (base_ik_scale, base_ik_scale, base_ik_scale)

                # Remove visual offset (Pivot is now at Head)
                ik_pbone.custom_shape_translation = (0, 0, 0)
                ik_pbone.color.palette = theme

                if coll_name in coll_map:
                    target_coll = coll_map[coll_name]
                    if ik_pbone.bone.name not in [b.name for b in target_coll.bones]:
                        target_coll.assign(ik_pbone.bone)

            # Visuals for Pole Target
            if pole_pbone:
                widget_pole = get_or_create_widget("WGT_Bone_SPHERE", 'SPHERE')
                context.view_layer.objects.active = armature

                pole_pbone.custom_shape = widget_pole
                base_pole_scale = 0.5 * global_scale
                pole_pbone.custom_shape_scale_xyz = (base_pole_scale, base_pole_scale, base_pole_scale)
                pole_pbone.color.palette = theme

                if coll_name in coll_map:
                    if pole_pbone.bone.name not in [b.name for b in target_coll.bones]:
                        target_coll.assign(pole_pbone.bone)


    # 3. Update IK Locks
    # We must re-acquire references because we switched modes
    # Use stored data dictionary instead of object references
    for data in update_ik_locks:
        pbone = armature.pose.bones.get(data['bone_name'])
        if pbone:
            # Sync to IK Limits using stored data

            # X
            if data['use_limit_x']:
                if abs(data['max_x'] - data['min_x']) < 0.001:
                    pbone.lock_ik_x = True
                else:
                    pbone.use_ik_limit_x = True
                    pbone.ik_min_x = data['min_x']
                    pbone.ik_max_x = data['max_x']
            else:
                pbone.lock_ik_x = False
                pbone.use_ik_limit_x = False

            # Y
            if data['use_limit_y']:
                if abs(data['max_y'] - data['min_y']) < 0.001:
                    pbone.lock_ik_y = True
                else:
                    pbone.use_ik_limit_y = True
                    pbone.ik_min_y = data['min_y']
                    pbone.ik_max_y = data['max_y']
            else:
                pbone.lock_ik_y = False
                pbone.use_ik_limit_y = False

            # Z
            if data['use_limit_z']:
                if abs(data['max_z'] - data['min_z']) < 0.001:
                    pbone.lock_ik_z = True
                else:
                    pbone.use_ik_limit_z = True
                    pbone.ik_min_z = data['min_z']
                    pbone.ik_max_z = data['max_z']
            else:
                pbone.lock_ik_z = False
                pbone.use_ik_limit_z = False