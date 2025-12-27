# Mechanical Rigger Plugin

A Blender plugin designed to automate mechanical rigging for vehicles, robotic arms, and other hard-surface machinery. It focuses on creating a clean, Unreal Engine-ready hierarchy (single mesh, rigid skinning) from an organized collection of mesh objects.

## Installation

1. Download the `mechanical_rigger` folder (or zip it).
2. Install in Blender via `Edit > Preferences > Add-ons > Install...`.
3. Enable "Rigging: Mechanical Rigger".

## Workflow

### 1. Preparation
Organize your hard-surface meshes in the **Outliner**.
*   **Hierarchy**: Parent your objects to define the kinematic chain (e.g., *Hand* is a child of *LowerArm*, which is a child of *UpperArm*).
*   **Collections**: Group objects that move together as a single rigid body into a **Collection**.
    *   The **Collection Name** becomes the **Bone Name**.
    *   *Example:* Put all upper arm screws, plates, and the main mesh into a collection named `UpperArm`.

### 2. Mirroring (Optional)
If your model is symmetric (e.g., a robot with left and right arms):
1.  Create an **Empty** object at the center of symmetry (usually 0,0,0).
2.  Suffix your collections with `_Mirrored` (e.g., `Arm_Mirrored`).
3.  The plugin will automatically generate `Arm_L` and `Arm_R` bones.
4.  Objects inside these collections should use a **Mirror Modifier** targeting the Empty.

### 3. Special Naming Conventions
The plugin detects specific keywords in Object or Collection names to automate behavior:

*   **Hinges**: Prefix an object name with `Hinge_` (e.g., `Hinge_Elbow`).
    *   The generated bone head will snap to this object's pivot.
    *   A `LIMIT_ROTATION` constraint is automatically applied, locking X/Z and allowing rotation only on the local Z-axis (Bone Y).

*   **Hydraulic Pistons**:
    *   Use two specific Collections for every piston:
        1.  `Piston_<ID>_Cyl` (e.g., `Piston_01_Cyl`)
        2.  `Piston_<ID>_Rod` (e.g., `Piston_01_Rod`)
    *   The system automates the `DAMPED_TRACK` constraints so they point at each other.
    *   **Tip**: Ensure they are parented correctly in the hierarchy (e.g., *Cyl* parented to *UpperArm*, *Rod* parented to *LowerArm*).

### 4. Generation
1.  Open the Sidebar (N-panel) > **Mechanical Rigger**.
2.  Select the **Root Object(s)** of your hierarchy in the 3D View.
3.  **Symmetric Origin**: Pick your Empty object if using mirroring.
4.  **Bone Size Scale**: Adjust the size of the generated bones relative to object dimensions (Default: `0.2`).
5.  Click **Validate Hierarchy** to check for errors (like missing piston parts).
6.  Click **Generate Rig**.
    *   *Result:* A new `Armature` and a combined `Rigged_Mesh` are created. Original objects are hidden.

### 5. Controls & Widgets
Select the generated **Armature** to see the Settings panel.

*   **Global Widget Scale**: Adjust the size of all control shapes (Default: `5.0`).
*   **Apply Controls**: Click this button to generate shapes and constraints.
    *   *Note:* The source meshes for widgets are stored in a hidden "Widgets" collection.

**Per-Bone Configuration**:
Select a bone in the "Bone Configuration" list to tweak it:
*   **Use IK**: Enable Inverse Kinematics for chains (e.g., Legs/Arms).
    *   **Chain Length**: Number of bones in the IK chain.
    *   *IK Controls* automatically get a **BOX** shape.
*   **Widget Shape**: Choose `CIRCLE`, `BOX`, `SPHERE`, or `NONE`.
*   **Customize Transform**: Check this to manually move/scale the widget without affecting the bone.
    *   Use the **Edit Widget Transform** tool (Gizmo icon) to adjust the shape visually in the viewport.

## Developer Tools
*   **Reload Scripts**: Located in the "Tools" sub-panel (bottom). Useful for developers modifying the addon source code.
