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

            # Inherit names from object if collection is generic?
            # Existing logic uses Collection Name.
            # If Piston, we might want to use Object name logic?
            # But the requirement is Piston_<ID>_Cyl is the object name.
            # If the user put Piston_Arm_Cyl in a collection named "ArmPiston", base_name is "ArmPiston".
            # This is fine. The bone will be named "ArmPiston" (or _L/_R).
            # Wait, if we rely on bone names matching object names for pistons, this might be tricky if we rename bones based on collections.

            # IMPORTANT: The current logic names bones based on COLLECTION names.
            # If the user has many objects in one collection, they get merged to one bone.
            # For Pistons, usually Cyl and Rod are separate moving parts, so they MUST be in separate collections or
            # the logic needs to change to support object-based bones.

            # User workflow: "Parent Cyl to UpperArm, Rod to LowerArm".
            # If they are in the same collection as parent, they merge?
            # No, `is_new_bone` checks `obj_to_col[parent_node] != col`.
            # So if Cyl is in a new collection, it gets a bone.
            # If Cyl is in same collection as UpperArm, it merges.
            # Mechanical rigging implies moving parts = separate bones.
            # So user must put them in separate collections?
            # Or we should update logic to always create bone if object name starts with Piston_?

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

def prepare_meshes_for_bake(context, bound_objects, symmetric_origin):
    """
    Prepares a list of meshes for baking by applying modifiers and handling mirroring.
    Input: list of original objects (bound to the rig).
    Output: list of new, processed mesh objects ready to be joined.
    """
    processed_objects = []

    # We need to distinguish between L-Side source objects (Mirrored) and R-Side generated objects (Linked)
    # Strategy:
    # 1. Iterate all bound objects.
    # 2. Check if object has Mirror Modifier -> It's a Source (L/Center).
    #    -> Action: Remove Mirror Modifier (because we have R object separate), Apply other modifiers.
    # 3. Check if object is R-Side (Linked, Negative Scale).
    #    -> Action: Apply Modifiers (to mesh), Apply Transform (Fix Scale), Flip Normals.

    # Avoid duplicate processing? 
    # Interactive bind creates: Object_L (w/ Mirror Mod), Object_R (Linked Dup).
    # Both are children of the rig (Bone Parent).
    # So `bound_objects` contains both.

    bpy.ops.object.select_all(action='DESELECT')

    for obj in bound_objects:
        if obj.hide_render:
            continue

        # Create temp copy to work on
        new_obj = obj.copy()
        new_obj.data = obj.data.copy() # Make data unique to apply modifiers safely
        context.collection.objects.link(new_obj)

        new_obj.hide_viewport = False
        new_obj.hide_render = False

        # Handle Mirror Modifiers:
        # If this is a source object with Mirror Modifier, we remove the mirror modifier
        # because the R-side geometry is represented by the separate R-side object in the list.
        # Exception: If for some reason R-side object is missing, we might want to apply it?
        # But for reliability with the rig structure, we assume 1-to-1 object-bone mapping.

        to_remove = []
        has_mirror_mod = False

        # Check if object is part of a Mirrored collection
        is_mirrored_collection = False
        if obj.users_collection:
            if "_Mirrored" in obj.users_collection[0].name:
                is_mirrored_collection = True

        for m in new_obj.modifiers:
            if m.type == 'MIRROR':
                # Check if it's the structural mirror (using Symmetric Origin)
                if symmetric_origin and m.mirror_object == symmetric_origin:
                    # ONLY remove the mirror modifier if the object is in a Mirrored collection.
                    # This implies there is a separate R-side object handling the other half.
                    # If it is a Center object (not in _Mirrored), we want to KEEP (Apply) the mirror
                    # so the final mesh is complete.
                    if is_mirrored_collection:
                        to_remove.append(m)
                    has_mirror_mod = True

        for m in to_remove:
            new_obj.modifiers.remove(m)

        # Mute Armature Modifiers to prevent double-skinning or baking deformation
        # We want the 'Rest Pose' static mesh.
        for m in new_obj.modifiers:
            if m.type == 'ARMATURE':
                m.show_viewport = False
                m.show_render = False

        # Apply Modifiers (bake to mesh)
        # Use depsgraph to evaluate modifiers (Subsurf, Bevel, etc.)
        context.view_layer.objects.active = new_obj
        new_obj.select_set(True)

        depsgraph = context.evaluated_depsgraph_get()
        obj_eval = new_obj.evaluated_get(depsgraph)
        mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)

        # Replace data
        # Note: If new_obj was a Curve, we cannot assign Mesh data to it directly.
        if new_obj.type != 'MESH':
            # Create a new Mesh Object to replace the Curve Object
            mesh_obj = bpy.data.objects.new(new_obj.name, mesh_from_eval)
            context.collection.objects.link(mesh_obj)

            # Copy properties
            mesh_obj.matrix_world = new_obj.matrix_world
            mesh_obj.hide_viewport = False
            mesh_obj.hide_render = False

            # Replace reference
            to_delete = new_obj
            new_obj = mesh_obj

            # Remove the old curve object
            bpy.data.objects.remove(to_delete)

            # Ensure the new object is Active and Selected for subsequent ops
            context.view_layer.objects.active = new_obj
            new_obj.select_set(True)
        else:
            old_mesh = new_obj.data
            new_obj.data = mesh_from_eval
            new_obj.modifiers.clear() # Modifiers are baked now

        # Handle Transforms and Constraints
        # We must clear constraints because 'transform_apply' resets the transform to identity,
        # but if a constraint remains, it might re-apply rotation/location on the next update,
        # causing the mesh to be double-transformed or offset.

        # 1. Store the visual world matrix (what we see)
        visual_matrix = new_obj.matrix_world.copy()

        # 2. Clear constraints
        new_obj.constraints.clear()

        # 3. Unparent to ensure we are baking World Transform, not Local-to-Parent
        new_obj.parent = None

        # 4. Force the object to exist at that visual transform without constraints
        new_obj.matrix_world = visual_matrix

        # 5. Apply Visual Transform (Bake Matrix into Mesh Vertices)
        # This makes the Object Transform (0,0,0) and Scale (1,1,1)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Check determinant for R-side flip
        # Original object world matrix determinant tells us if it was mirrored
        det = obj.matrix_world.determinant()
        if det < 0:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.mode_set(mode='OBJECT')

        # Recover Bone Name
        # If object is not directly parented to bone (child of another mesh), search up hierarchy
        bone_name = None
        if obj.parent_type == 'BONE' and obj.parent_bone:
            bone_name = obj.parent_bone
        elif obj.parent:
            curr = obj.parent
            while curr:
                if curr.parent_type == 'BONE' and curr.parent_bone:
                    bone_name = curr.parent_bone
                    break
                curr = curr.parent

        if bone_name:
            new_obj['mech_bone_name'] = bone_name

        processed_objects.append(new_obj)
        new_obj.select_set(False)

    return processed_objects

def bind_objects_interactive(context, rig_roots, armature_obj, symmetric_origin, mesh_selection=None):
    """
    Parents objects to bones using operators to ensure reliability.
    Creates linked duplicates for mirrored sides.
    """
    print(f"DEBUG: Starting bind_objects_interactive. Armature: {armature_obj.name}")

    def get_all_nodes(nodes):
        res = []
        for n in nodes:
            res.append(n)
            res.extend(get_all_nodes(n.children))
        return res

    all_nodes = get_all_nodes(rig_roots)

    # Dictionary to batch parenting tasks: { bone_name: [list_of_objects] }
    parenting_tasks = {}

    # Ensure Object Mode for preparation
    bpy.ops.object.mode_set(mode='OBJECT')

    # We iterate ALL nodes. The node.origin_obj is the definitive object for that bone.
    # In the old logic, we assumed "Collection = Bone", but if users split objects (Thigh, Shin)
    # into one collection or separate, the `analyze_hierarchy` logic determined the BoneNode structure.
    # We should trust `node.origin_obj` as the target mesh for `node.name`.

    # Wait, `analyze_hierarchy` groups by Collection?
    # Yes, `is_new_bone` checks if collection changed.
    # So actually, MULTIPLE objects can belong to ONE bone (if they are in the same collection).
    # We need to find ALL objects that belong to this node's scope.

    # Re-map: Collection -> Objects
    col_objects = {}
    target_objects = mesh_selection if mesh_selection else context.selected_objects

    for obj in target_objects:
        if not obj.users_collection: continue
        c = obj.users_collection[0]
        if c not in col_objects:
            col_objects[c] = []
        col_objects[c].append(obj)

    # Track processed collections to avoid double-processing if multiple nodes map to same collection (shouldn't happen with current analyze logic?)
    # Actually, analyze logic: "If collection changes, make new bone".
    # So one node = one collection context.
    # BUT, if we have nested structures, we iterate nodes.

    processed_cols = set()

    for node in all_nodes:
        # Identify the collection associated with this node
        col = node.origin_obj.users_collection[0]

        # Unique key for processing this "bone's payload"
        # We need to process both L and R sides for this node
        # But we must be careful:
        # If multiple nodes share the same collection (e.g. slight hierarchy diff?), 
        # `analyze_hierarchy` logic: "is_new_bone" if collection differs.
        # So it implies 1 Bone <-> 1 Collection (mostly).
        # Let's trust that.

        # However, the previous bug was skipping nodes because `processed_keys` matched `(col.name, side)`.
        # If Node A (Thigh) uses Col_Leg, and Node B (Shin) uses Col_Leg...
        # Wait, `analyze_hierarchy`:
        # `if obj_to_col[parent_node.origin_obj] != col: is_new_bone = True`
        # If Thigh and Shin are in SAME collection, they are merged into ONE bone (Thigh).
        # So `processed_keys` preventing duplicates was actually CORRECT for the *Bone Generation* logic (one bone per col).
        # BUT, `bind_objects` iterates NODES (bones).
        # If we have 1 Bone for 2 Objects, we visit that Node once. We grab all objects in collection. Correct.

        # If we have 2 Bones (Thigh, Shin) they MUST be in different collections (Col_Thigh, Col_Shin).
        # So `col` would be different.

        # So why did the Reviewer verify a bug?
        # "If a user has a hierarchy of parts (Thigh, Shin) organizing them in a single collection (Leg_Collection)...
        # ... the loop will process the first node (Thigh), parent ALL three meshes to Thigh bone..."

        # Ah! `analyze_hierarchy` logic:
        # If Thigh and Shin are in SAME collection:
        # 1. Thigh (Root) -> Bone "Leg_Collection" created.
        # 2. Shin (Child of Thigh) -> Same collection -> `is_new_bone` = False. `traverse` continues passing `node_l` (Thigh Bone).
        # So Shin is effectively part of Thigh Bone.
        # So `all_nodes` only contains "Leg_Collection" bone.
        # So collecting all objects in "Leg_Collection" and parenting to "Leg_Collection" bone is CORRECT behavior for that logic.

        # BUT, if the user *wants* separate bones, they *must* separate collections currently.
        # The reviewer implies my logic is broken for "hierarchy of parts".
        # If the existing logic enforces 1-Bone-Per-Collection, then the previous code was technically consistent with that limitation.
        # However, to be safer and support future "Object-Per-Bone" logic (if ever changed), 
        # let's bind `node.origin_obj` specifically?
        # No, because `origin_obj` is just the *representative*. There might be other objects in that collection (e.g. bolts) that should move with it.

        # Okay, let's stick to the Collection-based grouping but ensure we don't accidentally skip valid different bones.
        # The key was `(col.name, node.is_mirrored_side)`.
        # If multiple bones map to same collection... wait, that shouldn't happen in `analyze_hierarchy`.
        # UNLESS `analyze_hierarchy` produces multiple nodes for same collection?
        # Only if hierarchy splits and comes back? No.

        # Let's refine the loop to be explicit.
        # We want to bind ALL objects in the collection associated with this bone.

        key = (col.name, node.is_mirrored_side)
        if key in processed_cols:
            continue
        processed_cols.add(key)

        objs = col_objects.get(col, [])
        bone_name = node.name

        if bone_name not in parenting_tasks:
            parenting_tasks[bone_name] = []

        # L-Side or Center
        if node.is_mirrored_side != 'R':
            for obj in objs:
                # Disable Mirror Modifier on Source (L)
                if symmetric_origin and node.is_mirrored_side == 'L':
                    for m in obj.modifiers:
                        if m.type == 'MIRROR' and m.mirror_object == symmetric_origin:
                            m.show_viewport = False
                            m.show_render = False

                # Check if this object is a "Root" in this collection context.
                # If its parent is ALSO in this list of objects to bind, we skip parenting it to the bone.
                # This preserves the local hierarchy (e.g. Hinge -> Piston) while binding the Hinge to the bone.
                if obj.parent and obj.parent in objs:
                    continue

                # Check if already correctly parented to avoid redundant ops
                if obj.parent == armature_obj and obj.parent_type == 'BONE' and obj.parent_bone == bone_name:
                    continue

                # Clear existing parent to prevent 'loop in parents' or transform issues
                # Note: We only clear parent if we are about to reparent it to the bone.
                if obj.parent:
                    mat = obj.matrix_world.copy()
                    obj.parent = None
                    obj.matrix_world = mat

                parenting_tasks[bone_name].append(obj)

        # R-Side (Mirror)
        if node.is_mirrored_side == 'R':
            # Manage Target Collection for Linked Objects
            target_col_name = f"{col.name}_Linked"
            if target_col_name in bpy.data.collections:
                target_col = bpy.data.collections[target_col_name]
            else:
                target_col = bpy.data.collections.new(target_col_name)
                context.scene.collection.children.link(target_col)

            # Pass 1: Ensure all Linked Duplicates exist first
            # We need to guarantee presence of r_parents if they exist within the same batch
            r_objects_map = {} # Map source_obj -> r_obj

            for obj in objs:
                # Find or Create Linked Duplicate
                r_name = f"{obj.name}_Linked_R"
                r_obj = bpy.data.objects.get(r_name)

                if not r_obj:
                    r_obj = obj.copy() # Linked Duplicate
                    r_obj.name = r_name
                    r_obj.data = obj.data # Ensure linked
                    target_col.objects.link(r_obj)
                else:
                    # Move to correct collection if needed
                    if target_col not in r_obj.users_collection:
                         target_col.objects.link(r_obj)
                    for c in list(r_obj.users_collection):
                        if c != target_col:
                            c.objects.unlink(r_obj)

                # Calculate Mirrored Matrix (Negative Scale)
                mat = obj.matrix_world
                if symmetric_origin:
                    origin_mat = symmetric_origin.matrix_world
                    local = origin_mat.inverted() @ mat
                    mirror_scale = mathutils.Matrix.Scale(-1, 4, (1,0,0))
                    local_mirrored = mirror_scale @ local
                    target_mat = origin_mat @ local_mirrored
                else:
                    mirror_scale = mathutils.Matrix.Scale(-1, 4, (1,0,0))
                    target_mat = mirror_scale @ mat

                r_obj.matrix_world = target_mat

                # Remove mirror modifiers on the copy
                if symmetric_origin:
                    to_remove = []
                    for m in r_obj.modifiers:
                        if m.type == 'MIRROR' and m.mirror_object == symmetric_origin:
                            to_remove.append(m)
                    for m in to_remove:
                        r_obj.modifiers.remove(m)

                # Clear parent initially to prevent bad transforms
                if r_obj.parent:
                    r_obj.parent = None
                    r_obj.matrix_world = target_mat

                r_obj.hide_viewport = False
                r_obj.hide_render = False

                r_objects_map[obj] = r_obj

            # Pass 2: Parenting Logic
            for obj in objs:
                r_obj = r_objects_map[obj]

                # Check if this object should preserve local hierarchy (parented to another object in this group)
                if obj.parent and obj.parent in objs:
                    # Parent to R-counterpart instead of Bone
                    r_parent = r_objects_map.get(obj.parent)
                    if r_parent:
                        # Restore Matrix (Parenting modifies local transform)
                        current_matrix = r_obj.matrix_world.copy()
                        r_obj.parent = r_parent
                        r_obj.matrix_world = current_matrix

                        # We specifically SKIP adding to parenting_tasks (Bone Binding)
                        continue

                # Else: Bind to Bone
                parenting_tasks[bone_name].append(r_obj)

    print(f"DEBUG: Collected {len(parenting_tasks)} parenting tasks.")

    # Execute Parenting in Pose Mode
    if parenting_tasks:
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = armature_obj
        # Ensure armature is selected
        armature_obj.select_set(True)

        bpy.ops.object.mode_set(mode='POSE')

        for bone_name, objects_to_bind in parenting_tasks.items():
            if not objects_to_bind:
                continue

            print(f"DEBUG: Processing Bone: {bone_name}, Objects: {[o.name for o in objects_to_bind]}")

            # Set Active Bone
            if bone_name not in armature_obj.data.bones:
                print(f"DEBUG: Bone {bone_name} not found in armature!")
                continue

            bone = armature_obj.data.bones[bone_name]
            armature_obj.data.bones.active = bone

            # Verify active bone
            print(f"DEBUG: Active Bone set to: {armature_obj.data.bones.active.name}")

            # Select Objects
            for obj in objects_to_bind:
                obj.select_set(True)

            # Ensure Armature is Active
            context.view_layer.objects.active = armature_obj

            # Check Selection
            sel_names = [o.name for o in context.selected_objects]
            print(f"DEBUG: Selection before parent_set: {sel_names}")
            print(f"DEBUG: Active Object: {context.view_layer.objects.active.name}, Mode: {context.mode}")

            # Apply
            try:
                res = bpy.ops.object.parent_set(type='BONE', keep_transform=True)
                print(f"DEBUG: parent_set result: {res}")
            except Exception as e:
                print(f"DEBUG: parent_set FAILED: {e}")

            # Deselect objects for next batch
            for obj in objects_to_bind:
                obj.select_set(False)

    # Restore Object Mode
    bpy.ops.object.mode_set(mode='OBJECT')
    print("DEBUG: Finished bind_objects_interactive")

    # Restore Object Mode
    bpy.ops.object.mode_set(mode='OBJECT')

# --- Step 3: Armature Creation ---

def create_armature(context, rig_roots, symmetric_origin, armature_obj=None):
    if armature_obj:
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')
        amt_obj = armature_obj
        amt = amt_obj.data
    else:
        bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
        amt_obj = context.object
        amt = amt_obj.data
        amt.name = "MechRig"

        # Move to dedicated collection
        rig_col_name = "MechRig_Collection"
        if rig_col_name not in bpy.data.collections:
            rig_col = bpy.data.collections.new(rig_col_name)
            context.scene.collection.children.link(rig_col)
        else:
            rig_col = bpy.data.collections[rig_col_name]

        # Link to new col, unlink from others
        if rig_col.name not in [c.name for c in amt_obj.users_collection]:
            rig_col.objects.link(amt_obj)

        for c in list(amt_obj.users_collection):
            if c != rig_col:
                c.objects.unlink(amt_obj)

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
            if node.name in amt.edit_bones:
                bone = amt.edit_bones[node.name]
            else:
                bone = amt.edit_bones.new(node.name)

            obj = node.origin_obj
            mat = obj.matrix_world

            final_head = calculate_bone_head(node)

            # Align Bone to Object's Local Z axis (Y of bone = Z of object)
            z_axis = mat.col[2].xyz.normalized()

            # Readability: Use max dimension or scale, with minimum
            length = max(obj.dimensions.length * 0.5, 0.2) * context.scene.mech_rig_bone_size_scale

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
                        length = max(obj.dimensions.length * 0.5, 0.2) * context.scene.mech_rig_bone_size_scale
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
                length = max(obj.dimensions.length * 0.5, 0.2) * context.scene.mech_rig_bone_size_scale

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

    # Set parent with inverse matrix to prevent offset if armature is not at origin
    combined_mesh.parent = armature
    combined_mesh.matrix_parent_inverse = armature.matrix_world.inverted()

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

    widgets_col.hide_viewport = True

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

    ik_tasks = [] # List of (bone_name, ik_target_name, chain_length, settings)

    # Lists for Cleanup (Store DATA, not Objects, as Edit Mode invalidates objects)
    cleanup_ik_bones = [] # Names of _IK bones to remove
    cleanup_ik_constraints = [] # Tuples of (bone_name, constraint_name/type) to remove

    # Lists for Config
    update_ik_locks = [] # List of dicts with bone_name and lock settings

    global_scale = context.scene.mech_rig_widget_scale

    # First pass: Set up Visuals (Color, Shape) and Identify IK needs
    for pbone in armature.pose.bones:
        settings = pbone.mech_rig_settings

        # Skip IK Bones for generic shapes (They are handled in Pass 3)
        if pbone.name.endswith("_IK"):
            continue

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

        if settings.use_ik:
            # 1. Check if constraint needs adding
            has_ik_constraint = False
            for c in pbone.constraints:
                if c.type == 'IK':
                    has_ik_constraint = True
                    c.chain_count = settings.ik_chain_length # Update length
                    break

            if not has_ik_constraint:
                ik_tasks.append({
                    'bone_name': pbone.name,
                    'ik_target_name': ik_target_name,
                    'chain_length': settings.ik_chain_length,
                    'color_theme': color_theme,
                    'target_coll_name': target_coll.name
                })

            # 2. Collect Locking Tasks (Traverse parents)
            # We need to lock axes on parents if they have Limit Rotation constraints
            curr_bone = pbone
            for _ in range(settings.ik_chain_length):
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
            # 1. Mark Constraint for removal
            for c in pbone.constraints:
                if c.type == 'IK':
                    cleanup_ik_constraints.append((pbone.name, c.name))

            # 2. Mark Target Bone for removal if it exists
            # We can only check existence here, actual removal in Edit Mode
            # We assume naming convention implies ownership
            if ik_target_name in armature.pose.bones:
                cleanup_ik_bones.append(ik_target_name)

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

            if bone_name in amt.edit_bones:
                bone = amt.edit_bones[bone_name]
                if target_name not in amt.edit_bones:
                    ik_bone = amt.edit_bones.new(target_name)
                    ik_bone.head = bone.tail
                    # Align IK bone similar to bone
                    ik_bone.tail = bone.tail + (bone.tail - bone.head).normalized() * (bone.length * 0.5)

                    # Parent to the bone's parent (Direct Parent) to enable FK-like behavior for IK control
                    if bone.parent:
                        ik_bone.parent = bone.parent
                    else:
                        ik_bone.parent = None

                    ik_bone.use_deform = False

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
        chain_len = task['chain_length']
        theme = task['color_theme']
        coll_name = task['target_coll_name']

        pbone = armature.pose.bones.get(bone_name)
        ik_pbone = armature.pose.bones.get(target_name)

        if pbone and ik_pbone:
            # Apply Constraint
            c = pbone.constraints.new('IK')
            c.target = armature
            c.subtarget = target_name
            c.chain_count = chain_len

            # Setup IK-FK Switch Property on Target
            prop_name = "IK_FK"
            if prop_name not in ik_pbone:
                ik_pbone[prop_name] = 1.0
                ik_pbone.id_properties_ui(prop_name).update(min=0.0, max=1.0)

            # Driver
            d = c.driver_add("influence")
            d.driver.type = 'AVERAGE'
            var = d.driver.variables.new()
            var.name = "var"
            var.type = 'SINGLE_PROP'
            var.targets[0].id = armature
            var.targets[0].data_path = f'pose.bones["{target_name}"]["{prop_name}"]'

            # Visuals for IK Target
            widget_obj = get_or_create_widget("WGT_Bone_BOX", 'BOX')
            context.view_layer.objects.active = armature

            ik_pbone.custom_shape = widget_obj
            # Fixed scale for IK Handle or proportional? 1.5 is standard logic.
            # Let's scale it by global scale too.
            base_ik_scale = 1.5 * global_scale
            ik_pbone.custom_shape_scale_xyz = (base_ik_scale, base_ik_scale, base_ik_scale)
            ik_pbone.custom_shape_translation = (0, 0, 0)

            ik_pbone.color.palette = theme

            if coll_name in coll_map:
                target_coll = coll_map[coll_name]
                if ik_pbone.bone.name not in [b.name for b in target_coll.bones]:
                    target_coll.assign(ik_pbone.bone)

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