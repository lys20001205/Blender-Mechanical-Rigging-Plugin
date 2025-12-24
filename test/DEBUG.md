# Debugging Mechanical Rigger in JetBrains Rider

This guide explains how to set up a professional debugging environment for the Mechanical Rigger plugin using JetBrains Rider. This setup allows you to:
1.  **Edit code in Rider and see changes immediately** (no more zipping/installing).
2.  **Set breakpoints and step through code** running inside Blender.
3.  **Reload the plugin** without restarting Blender.

---

## 1. Install the Python Plugin for Rider

The "Python Debug Server" configuration is missing by default because Rider requires the Python plugin.

1.  Open Rider.
2.  Go to **File > Settings** (or `Ctrl+Alt+S`).
3.  Navigate to **Plugins**.
4.  Click the **Marketplace** tab.
5.  Search for **"Python"**.
6.  Install the **Python Community** plugin (published by JetBrains).
7.  **Restart Rider**.

---

## 2. Setup (Windows)

We have provided a script to automatically link the source code to Blender and install the required debugger tools.

1.  Close Blender.
2.  Navigate to the `tools/` folder in this repository.
3.  **Right-click `setup_dev_env.bat` and select Edit.**
4.  Update the `BLENDER_PYTHON` and `BLENDER_ADDONS` variables at the top of the file to match your system paths.
5.  Save and double-click `setup_dev_env.bat` to run it.
    *   This script will:
        *   Enable `pip` in your Blender installation.
        *   Install `pydevd-pycharm` (the debugger) into Blender's Python environment.
        *   Create a "Junction" (Symlink) so Blender loads the code directly from your repo.

---

## 3. Run Configuration (Auto-Setup)

We have automatically included a Run Configuration for you.

1.  **Restart Rider** (if it was open).
2.  Look at the Run/Debug toolbar at the top right.
3.  Select **Blender Debug** from the dropdown list.
    *   If you don't see it, ensure the **Python Community** plugin is installed and you have restarted Rider.

> **Manual Setup (Only if auto-setup fails):**
> If the "Blender Debug" configuration doesn't appear:
> 1. Go to **Run > Edit Configurations**.
> 2. Add a new **Python Remote Debug** (or "Python Debug Server") configuration.
> 3. Set Port to `5678`.
> 4. Map your local `src/mechanical_rigger` folder to the Blender addons folder.

---

## 4. Debugging Workflow

1.  **Start the Debug Server** in Rider:
    *   Select the `Blender Debug` configuration.
    *   Click the **Debug** icon (bug).
    *   The console should say: `Waiting for process connection...`

2.  **Launch Blender**:
    *   Open Blender.
    *   If the plugin is enabled, it will attempt to connect immediately.
    *   Look at the Rider console. If successful, it will say `Connected to pydev debugger`.

3.  **Edit and Reload**:
    *   Make changes to the code in Rider.
    *   In Blender, press **F3** and search for **"Reload Scripts"**.
    *   Alternatively, use the **"Reload Addon"** button in the Mechanical Rigger panel (if available).

## Troubleshooting

*   **Port already in use**: Ensure no other debug session is running. Change the port in both Rider and `__init__.py` if needed.
*   **Module not found**: If Blender says `No module named 'pydevd_pycharm'`, re-run the `setup_dev_env.bat` script and check for errors.
