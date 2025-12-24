Debugging Mechanical Rigger in JetBrains Rider

This guide explains the workflow for developing the Mechanical Rigger plugin in JetBrains Rider.

Since Rider's Python support (via the Community plugin) does not always support "Remote Debugging" configurations, we recommend a Launch-based workflow. You will launch Blender directly from Rider, running a test script that exercises your code.

1. Prerequisites

Install Rider.

Install the Python Plugin:

Go to File > Settings > Plugins.

Search for "Python Community" and install it.

Restart Rider.

2. Environment Setup (One-Time)

We need to link your source code to Blender so changes in Rider appear immediately.

Navigate to the tools/ folder in this repository.

Right-click setup_dev_env.bat and select Edit.

Update the BLENDER_ADDONS variable to match your system path (e.g., C:\Users\<User>\AppData\Roaming\Blender Foundation\Blender\4.3\scripts\addons).

Run the script as Administrator.

This creates a symbolic link. You do not need to zip/install the addon ever again.

3. Configure the Test Launcher

Instead of attaching a debugger, we will script Blender to open and run test/test_rigging.py.

Step A: Configure the Batch Script

Open tools/run_test.bat in Rider.

Edit the BLENDER_EXE variable to point to your Blender installation (e.g., C:\Program Files\Blender Foundation\Blender 4.3\blender.exe).

Step B: Create the Run Configuration

In Rider, go to Run > Edit Configurations....

Click the + button and select Shell Script.

Name it: Run Blender Test.

Execute: Select Script file.

Script path: Browse to tools/run_test.bat in your project.

Interpreter path: cmd.exe (or C:\Windows\System32\cmd.exe).

Interpreter options: /c (Crucial for batch files to run and terminate correctly).

Click OK.

Alternative (External Tool):
If the "Shell Script" configuration gives "Interpreter not found" errors:

Go to File > Settings > Tools > External Tools.

Add a new tool named "Run Blender Test".

Program: Browse to tools/run_test.bat.

Working directory: $ProjectFileDir$\tools.

Use this External Tool via the Tools menu.

4. Development Workflow

Edit Code: Make changes to your python files in src/mechanical_rigger/.

Run Test: Click the Run (Play) button next to your Run Blender Test configuration.

Blender will launch.

The test/test_rigging.py script will run automatically.

Output (Pass/Fail) will appear in the Run Dashboard / Console in Rider.

Review: Check the console for "PASS" or "FAIL" messages.

Note on Breakpoints

Because we are launching an external process via a batch script, Rider's Python debugger may not hit breakpoints automatically in this mode. Use print() statements to debug logic errors, which will show up clearly in the Rider console.
