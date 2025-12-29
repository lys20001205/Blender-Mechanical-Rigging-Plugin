# Mechanical Rigger Plugin

A Blender plugin (v4.3+) designed to automate mechanical rigging for vehicles, robotic arms, and other hard-surface machinery. It creates a clean, Unreal Engine-ready hierarchy (single mesh, rigid skinning) from an organized collection of mesh objects.

## Installation

1. Download the `mechanical_rigger` folder (or zip it).
2. Install in Blender via `Edit > Preferences > Add-ons > Install...`.
3. Enable "Rigging: Mechanical Rigger".

## Workflow

### 1. Preparation & Hierarchy
Organize your hard-surface meshes in the **Outliner**.
*   **Hierarchy**: Parent your objects to define the kinematic chain (e.g., *Hand* is a child of *LowerArm*, which is a child of *UpperArm*).
*   **Collections**: Group objects that move together as a single rigid body into a **Collection**.
    *   The **Collection Name** becomes the **Bone Name**.
    *   *Example:* Put all upper arm screws, plates, and the main mesh into a collection named `UpperArm`.

### 2. Mirroring
If your model is symmetric (e.g., a robot with left and right arms):
1.  Create an **Empty** object at the center of symmetry (usually 0,0,0).
2.  Suffix your collections with `_Mirrored` (e.g., `Arm_Mirrored`).
3.  The plugin will automatically generate `Arm_L` and `Arm_R` bones/objects.
    *   **Note**: For the "Right" side, the system creates **Linked Duplicates** of the "Left" objects. Edits to the Left mesh will reflect on the Right side.
4.  Objects inside these collections can use a Mirror Modifier for modeling, but the rigging process will handle the actual object duplication.

### 3. Special Naming Conventions
The plugin detects specific keywords in Object or Collection names to automate behavior:

*   **Hinges**: Prefix an object name with `Hinge_` (e.g., `Hinge_Elbow`).
    *   The generated bone head will snap to this object's pivot.
    *   A `LIMIT_ROTATION` constraint is automatically applied (locking X/Z, free Y).

*   **Hydraulic Pistons**:
    *   Use two specific Collections for every piston:
        1.  `Piston_<ID>_Cyl` (e.g., `Piston_01_Cyl`)
        2.  `Piston_<ID>_Rod` (e.g., `Piston_01_Rod`)
    *   The system automates the `DAMPED_TRACK` constraints so they point at each other.
    *   *Validation*: Ensure the Cylinder and Rod objects are parented to the correct parts of the main hierarchy (e.g., Cylinder -> UpperArm, Rod -> LowerArm) so they move with the rig.

### 4. Interactive Rigging
The workflow is iterative. You can update the rig as you refine the model.

1.  Open the Sidebar (N-panel) > **Mechanical Rigger**.
2.  Select the **Root Object(s)** of your hierarchy (and the Armature if updating).
3.  **Symmetric Origin**: Pick your Empty object if using mirroring.
4.  **Bone Size Scale**: Adjust generated bone length (Default: `0.2`).
5.  Click **Validate Hierarchy** to check for errors.
6.  Click **Build / Update Rig**.
    *   *Result:* An `Armature` is created. Objects are bound to bones via parent constraints.
    *   *Iterative:* You can move objects or change parents and run this again to update the rig.

### 5. Controls & Visualization
Select the generated **Armature** to access the Settings panel.

*   **Bone Layers**: Manage visibility using the "Rig Layers" panel (supports Blender 4.0+ Bone Collections).
*   **Global Widget Scale**: Adjust the size of all control shapes.
*   **Re-Apply Controls**: Updates shapes and constraints if you change settings.

**Per-Bone Configuration**:
Select a bone in the UI List or 3D View:
*   **Use IK**: Enable Inverse Kinematics for chains (e.g., Legs).
    *   **Chain Length**: Number of bones in the IK chain.
    *   *Note*: Creates a "Split IK" setup with a visible Control bone (`_IK`) and a hidden Solver bone (`_IK_Target`).
*   **Widget Shape**: Choose `CIRCLE`, `BOX`, `SPHERE`, or `NONE`.
*   **Customize Transform**: Check this to manually edit the widget's visual transform.
    *   Click the **Gizmo Icon** (Edit Widget Transform) to create a temporary proxy object.
    *   Move/Scale/Rotate the proxy in the viewport.
    *   Click **Apply Custom Transform** in the "Widget Edit Mode" panel to save changes.

### 6. Exporting
When the rig is finalized:

*   **Bake for Export**:
    *   Creates a new "Export" Armature and a single combined **Static Mesh** (skinned).
    *   Resets the pose to Rest Pose (T-Pose) before baking.
    *   Suitable for exporting to Unreal Engine as a Skeletal Mesh.

*   **Bake Animations**:
    *   Bakes all Actions from the Control Rig to the clean Export Rig.
    *   Ensures constraints are baked into keyframes.

## Developer Tools
*   **Reload Scripts**: Located in the "Tools" sub-panel. Useful for developers modifying the addon source code without restarting Blender.
