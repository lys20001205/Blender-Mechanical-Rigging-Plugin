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

## 3. Configure Rider Debug Server

Once the Python plugin is installed:

1.  In Rider, go to **Run > Edit Configurations...**.
2.  Click the **+** (Add New) button.
3.  Search for and select **Python Debug Server**.
4.  Configure it as follows:
    *   **Name**: `Blender Debug`
    *   **IDE Host Name**: `localhost`
    *   **Port**: `5678` (Must match the port in `__init__.py`)
5.  **Path Mappings**:
    *   Click the folder icon or `...`.
    *   **Local Path**: The absolute path to your `src/mechanical_rigger` folder (e.g., `E:\Projects\mechanical-rigger\src\mechanical_rigger`).
    *   **Remote Path**: The path where Blender sees the addon (e.g., `C:\Users\mice\AppData\Roaming\Blender Foundation\Blender\4.3\scripts\addons\mechanical_rigger`).
6.  Click **Apply** / **OK**.

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
