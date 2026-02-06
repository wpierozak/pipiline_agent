# Coding Module

## Overview

The `coding` module provides tools for managing Python workspaces, creating and executing Python scripts, and monitoring script execution. It's designed to support agent-driven code generation and testing workflows.

## Classes

### PythonWorkSpace

Core class for Python script management and execution. Extends `ToolProvider` to expose methods as LLM-callable tools.

**Constructor Parameters:**
- `path` (str): Path to the workspace directory
- `python_path` (str, default="python"): Python interpreter path
- `create_venv` (bool, default=False): Create and use virtual environment
- `allow_read_only` (bool, default=False): Enable read-only mode (prevents file creation)

**Tools (LLM-callable methods):**

#### `@toolmethod` create_script
```python
create_script(relative_path: str, content: str = "") -> str
```

Creates a new Python script in the workspace.

**Parameters:**
- `relative_path` (str): Path relative to workspace root
- `content` (str): Script content

**Returns:**
- Confirmation message or error if read-only mode is enabled or file exists

**Example:**
```python
workspace = PythonWorkSpace("./my_workspace")
result = workspace.create_script(
    "data_processor.py",
    "import pandas as pd\n\ndf = pd.read_csv('data.csv')\n"
)
```

#### `@toolmethod` overwrite_script
```python
overwrite_script(relative_path: str, content: str = "") -> str
```

Overwrites an existing Python script or creates a new one.

**Parameters:**
- `relative_path` (str): Path relative to workspace root
- `content` (str): New script content

**Returns:**
- Confirmation message or error

**Example:**
```python
workspace.overwrite_script(
    "data_processor.py",
    "import pandas as pd\n\nprint('Updated version')\n"
)
```

#### `@toolmethod` run_script
```python
run_script(script_path: str, args: list[str], run_background: bool = False) -> str
```

Executes a Python script in foreground or background.

**Parameters:**
- `script_path` (str): Path to script relative to workspace
- `args` (list[str]): Command-line arguments for the script
- `run_background` (bool): If True, run in background; if False, run synchronously

**Returns:**
- If foreground: stdout and stderr output
- If background: confirmation message

**Foreground Example:**
```python
output = workspace.run_script("data_processor.py", ["--input", "data.csv"])
print(output)  # "Stdout: ...\nStderr: ..."
```

**Background Example:**
```python
result = workspace.run_script(
    "long_running_task.py",
    ["--iterations", "1000"],
    run_background=True
)
# Returns: "Process started in background mode."
```

#### `@toolmethod` monitor_process
```python
monitor_background_process(timeout: float = None, min_time: float = 0.0) -> str
```

Monitors a script running in the background for output and completion.

**Parameters:**
- `timeout` (float, optional): Maximum seconds to wait before returning (None = indefinite)
- `min_time` (float): Minimum seconds to wait before checking for output

**Returns:**
- JSON-formatted string with stdout, stderr, and process code (if finished)

**Monitoring Strategy:**
- Waits at least `min_time` seconds
- Returns when new output is available OR timeout reached
- Returns immediately if process finishes

**Example:**
```python
# Start background process
workspace.run_script("server.py", [], run_background=True)

# Monitor for output
while True:
    result = workspace.monitor_background_process(timeout=5.0, min_time=1.0)
    print(result)
    
    if "Process finished" in result:
        break
```

#### `@toolmethod` write_to_stdin
```python
write_to_stdin(content: str) -> str
```

Writes input to the stdin of a background process.

**Parameters:**
- `content` (str): Input to send to the process

**Returns:**
- "OK" on success or error message

**Example:**
```python
# For interactive scripts
workspace.run_script("interactive.py", [], run_background=True)
workspace.write_to_stdin("user input\n")
output = workspace.monitor_background_process(timeout=2.0)
```

**Non-Tool Methods:**

#### `create_venv()`

Creates a Python virtual environment in the workspace and updates `python_path` to use it.

**Example:**
```python
workspace = PythonWorkSpace("./workspace", create_venv=True)
# Virtual environment created at ./workspace/venv
```

## Usage Patterns

### Agent-Driven Code Generation

When used by an LLM agent, the workspace provides tools for the complete code lifecycle:

```python
from pipiline_agent.coding.python_tools import PythonWorkSpace

# Agent uses these tools:
# 1. Create script
workspace.create_script("analyzer.py", code_content)

# 2. Run script
output = workspace.run_script("analyzer.py", ["--data", "input.csv"])

# 3. Fix and overwrite if needed
workspace.overwrite_script("analyzer.py", fixed_code)
```

### Background Process Management

For long-running scripts:

```python
workspace = PythonWorkSpace("./workspace")

# Start background task
workspace.run_script("training.py", ["--epochs", "100"], run_background=True)

# Periodically check progress
while True:
    status = workspace.monitor_background_process(timeout=10.0, min_time=5.0)
    print(status)
    
    if "finished" in status.lower():
        break
```

### Virtual Environment Isolation

For dependency isolation:

```python
workspace = PythonWorkSpace(
    path="./isolated_workspace",
    create_venv=True
)

# All scripts run in the virtual environment
workspace.create_script("requirements.txt", "numpy\npandas\n")
# Install dependencies in venv manually or via script
```

---

### PythonWorkSpaceFactory

Factory class for creating `PythonWorkSpace` instances. Extends `ToolFactory`.

**Constructor Parameters:**
- None

**Methods:**
- `create(args: dict) -> PythonWorkSpace`: Creates workspace instance from arguments dictionary

**Example Usage:**
```python
from pipiline_agent.coding.python_tools import PythonWorkSpaceFactory

factory = PythonWorkSpaceFactory()
workspace = factory.create({
    "path": "./my_workspace",
    "create_venv": True
})
```

## File System Structure

Typical workspace structure:

```
workspace/
├── venv/                    # Virtual environment (if create_venv=True)
│   ├── bin/
│   ├── lib/
│   └── ...
├── script1.py              # User scripts
├── script2.py
└── data/
    └── input.csv
```

## Read-Only Mode

When `allow_read_only=True`, the workspace prevents file creation/modification:

```python
workspace = PythonWorkSpace("./workspace", allow_read_only=True)
result = workspace.create_script("test.py", "print('hello')")
# Returns: "Error: Read only mode is enabled."
```

Useful for sandboxing or testing scenarios where file system changes should be prevented.

## Dependencies

- [core.tools](../core/tools.py) - ToolProvider, toolmethod decorator, ToolFactory
- [directory.file_access](../directory/file_access.py) - File system utilities
- [directory.workdir](../directory/workdir.py) - Workspace directory management
- [cmd_line.cmd_tools](../cmd_line/cmd_tools.py) - Command execution and monitoring
