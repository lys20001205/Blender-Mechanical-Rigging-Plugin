# Debugging Mechanical Rigger in JetBrains Rider

To debug this Blender addon using JetBrains Rider, you need to use **Remote Debugging**. This involves running a debug server in Rider and connecting to it from Blender.

## Prerequisites

1.  **JetBrains Rider** (or PyCharm Professional).
2.  **Blender** installed.
3.  **pydevd-pycharm** package installed in Blender's Python environment.

## Step 1: Install `pydevd-pycharm` in Blender

Blender uses its own bundled Python. You must install the debugger package into *that* specific environment.

1.  Locate your Blender installation's Python executable.
    *   **Windows**: `C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe`
    *   **macOS**: `/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.10` (Adjust version as needed)
    *   **Linux**: `/path/to/blender/4.3/python/bin/python3.10`

2.  Open a terminal/command prompt and run:
    ```bash
    # Replace <BLENDER_PYTHON_PATH> with the path found above
    "<BLENDER_PYTHON_PATH>" -m pip install pydevd-pycharm~=241.14494.240
    ```
    *Note: The version of `pydevd-pycharm` must match the version supported by your Rider installation. You can find the required version in the Rider Run Configuration setup (see Step 2).*

## Step 2: Configure Rider

1.  Open this project in Rider.
2.  Go to **Run > Edit Configurations...**.
3.  Click **+** and select **Python Debug Server**.
4.  Name it "Blender Debug".
5.  Set **Port** to `5678` (or any free port).
6.  **Important**: Note the instructions displayed in the configuration window regarding the `pydevd-pycharm` version. If it asks for a specific version, install that one in Step 1.
7.  Uncheck "Redirect output to console" if you want to see Blender's logs in Blender's console, or keep it checked to see them in Rider.
8.  Click **OK**.

## Step 3: Enable Debugging in the Addon

1.  Open `src/mechanical_rigger/__init__.py`.
2.  Uncomment the Debugging Block at the top of the file (instructions provided in the file).
    ```python
    # REMOTE DEBUGGING SETUP
    # import sys
    # if "pydevd_pycharm" not in sys.modules:
    #     import pydevd_pycharm
    #     pydevd_pycharm.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
    ```
3.  Ensure the `port` matches what you set in Rider (default `5678`).

## Step 4: Start Debugging

1.  In Rider, select the "Blender Debug" configuration and click **Debug** (the bug icon).
    *   The Console should say: `Starting debug server at port 5678... Waiting for process connection...`
2.  Start **Blender**.
3.  If the plugin is already enabled, the connection might happen immediately on startup.
4.  If not, enable (or disable and re-enable) the "Mechanical Rigger" addon in **Edit > Preferences > Add-ons**.
5.  Check Rider. It should say "Connected to pydevd".
6.  Set breakpoints in Rider (e.g., in `operators.py` inside `execute`).
7.  Run the operator in Blender. Rider should pause execution at your breakpoint.

## Troubleshooting

*   **Connection Refused**: Ensure Rider's debug server is running *before* you start/enable the addon in Blender.
*   **Version Mismatch**: If you get errors about protocol versions, double-check that the `pip install pydevd-pycharm` version matches what Rider expects.
*   **Path Mappings**: If breakpoints aren't hitting, you might need to configure path mappings in the Run Configuration in Rider to map the local source folder to the installed addon folder (though usually not necessary if you are loading the addon from source).
