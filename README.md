# Mechanical Rigger Plugin

A Blender plugin designed to automate mechanical rigging for vehicles, robotic arms, and other hard-surface machinery. It focuses on creating a clean, Unreal Engine-ready hierarchy (single mesh, rigid skinning) from an organized collection of mesh objects.

## Installation

1. Download the `mechanical_rigger` folder.
2. Zip the folder or install directly in Blender via `Edit > Preferences > Add-ons > Install...`.
3. Enable "Rigging: Mechanical Rigger".

## Workflow

1. **Organize Hierarchy**:
    - Parent your mesh objects in the Outliner to define the kinematic chain.
    - Group objects that move together into **Collections**. The Collection name determines the Bone name.
    - Assign the **Mirror Modifier** to objects that need mirroring.

2. **Naming Conventions**:
    - **Collections**: Name them after the intended bone (e.g., `Body`, `Wheel_FL`, `Arm`).
    - **Mirroring**: Suffix a collection with `_Mirrored` (e.g., `Arm_Mirrored`) to automatically generate Left (`_L`) and Right (`_R`) bones.
        - Objects in this collection with a Mirror Modifier will be split into L/R sides.
        - Objects *without* a Mirror Modifier will be assigned to the Left side (default) or Right depending on placement, but usually treated as the source side.
    - **Constraints**: Include `Hinge_` in the object name to automatically apply a Limit Rotation constraint (Locks X/Y, Free Z).
    - **Vehicle Parts**: Standard naming like `Phys_Wheel_FL`, `Axle_Damper_FL` is preserved in the final mesh data for game engine logic, but bones are named by Collection.

3. **Rigging**:
    - Open the Sidebar (N-panel) > **Mechanical Rigger**.
    - Select the root object(s) of your hierarchy.
    - Set the **Symmetric Origin** (Empty object) if you are using mirroring.
    - Click **Rig Hierarchy**.

4. **Add Controls**:
    - Select the generated Armature.
    - In the panel, you will see a list of bones.
    - Select a bone in the list to configure:
        - **Shape**: Circle, Box, Sphere.
        - **Enable IK**: Adds an IK constraint and target bone.
    - Click **Apply Controls** to update the rig.

## Features

- **Auto Armature Generation**: Converts object hierarchy to bone hierarchy.
- **Robust Mirroring**: Handles mixed mirrored/non-mirrored objects in the same collection.
- **Unreal Ready**: Combines all meshes into one object with 1.0 (rigid) skin weights.
- **Constraint Detection**: Auto-detects hinges based on naming.
- **Control System**: Easy setup for IK/FK and custom shapes.

## Requirements

- Blender 4.3.2 or later.
