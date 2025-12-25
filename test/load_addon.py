import bpy
import sys
import os

# Adds 'src' to sys.path so we can import the addon modules directly
# This allows testing the current source code without installing it as an addon.

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(repo_root, "src")

if src_path not in sys.path:
    sys.path.append(src_path)

print(f" Mechanical Rigger: Loading addon from source: {src_path}")

try:
    from mechanical_rigger import operators, ui, utils

    # Unregister first to be safe (if re-running)
    try:
        ui.unregister()
        operators.unregister()
    except:
        pass

    ui.register()
    operators.register()

    print(" Mechanical Rigger: Addon Registered Successfully!")

except Exception as e:
    print(f" Mechanical Rigger: Failed to load addon. Error: {e}")
    import traceback
    traceback.print_exc()
