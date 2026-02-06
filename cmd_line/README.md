# Command Line Module

## Overview

The `cmd_line` module provides tools for executing and monitoring command-line processes. It supports both synchronous command execution and background process monitoring with real-time stdout/stderr streaming.

## Classes

### CmdLineOutput

Data class representing the output of a command execution.

**Fields:**
- `stdout` (str): Standard output from the command
- `stderr` (str): Standard error from the command

---

### CmdLineMonitor

Monitor class for tracking the output and status of a running process. Decorated with `@Monitor` for thread-safe access.

**Constructor Parameters:**
- `process` (subprocess.Popen): The process to monitor

**Key Methods:**

#### State Checking
- `is_running() -> bool`: Check if process is still running
- `is_new_stdout() -> bool`: Check if new stdout is available
- `is_new_stderr() -> bool`: Check if new stderr is available
- `get_process_code() -> int`: Get the exit code of the process

#### Reading Output
- `get_stdout() -> str`: Get and consume new stdout (advances read pointer)
- `get_stderr() -> str`: Get and consume new stderr (advances read pointer)

#### Process Interaction
- `write_stdin(stdin: str)`: Write to the process's stdin
- `set_finished(code: int)`: Mark process as finished (internal use)

**Features:**
- Incremental output reading (only returns new data since last read)
- Thread-safe operation
- Non-blocking stdout/stderr monitoring
- stdin interaction for interactive processes

**Example Usage:**
```python
from pipiline_agent.cmd_line.cmd_tools import CmdLineRunner

runner = CmdLineRunner()
monitor = runner.monitor_cmd("python", ["script.py"])

# Check for new output
while monitor.is_running():
    if monitor.is_new_stdout():
        print("STDOUT:", monitor.get_stdout())
    
    if monitor.is_new_stderr():
        print("STDERR:", monitor.get_stderr())
    
    time.sleep(0.1)

print("Exit code:", monitor.get_process_code())
```

---

### CmdLineRunner

Executor class for running command-line commands with monitoring capabilities.

**Constructor Parameters:**
- None

**Key Methods:**

#### `execute_cmd(cmd: str, args: list[str] = []) -> CmdLineOutput`

Run a command synchronously and return its complete output.

**Parameters:**
- `cmd` (str): Command to execute
- `args` (list[str]): Command arguments

**Returns:**
- `CmdLineOutput`: Object containing stdout and stderr

**Example:**
```python
runner = CmdLineRunner()
output = runner.execute_cmd("ls", ["-la", "/tmp"])
print(output.stdout)
print(output.stderr)
```

#### `monitor_cmd(cmd: str, args: list[str] = [], bufsize: int = 1) -> CmdLineMonitor`

Start a command in the background and return a monitor for tracking its progress.

**Parameters:**
- `cmd` (str): Command to execute
- `args` (list[str]): Command arguments
- `bufsize` (int): Buffer size for output streams (default: 1 for line buffering)

**Returns:**
- `CmdLineMonitor`: Monitor object for tracking execution

**Features:**
- Command runs in background
- Real-time output monitoring via separate threads
- Non-blocking operation
- stdin interaction support

**Example:**
```python
runner = CmdLineRunner()
monitor = runner.monitor_cmd("python", ["-u", "long_running_script.py"])

# Monitor until completion
while monitor.is_running():
    if monitor.is_new_stdout():
        new_output = monitor.get_stdout()
        print(f"New output: {new_output}")
    time.sleep(0.5)

print(f"Process finished with code: {monitor.get_process_code()}")
```

**Interactive Process Example:**
```python
# Start an interactive Python REPL
monitor = runner.monitor_cmd("python", ["-i"])

# Send commands
monitor.write_stdin("print('Hello')\n")
time.sleep(0.1)

if monitor.is_new_stdout():
    print(monitor.get_stdout())  # Will show "Hello"

monitor.write_stdin("exit()\n")
```

## Usage Patterns

### Synchronous Execution

Use `execute_cmd()` for commands that complete quickly:

```python
runner = CmdLineRunner()
result = runner.execute_cmd("git", ["status"])
print(result.stdout)
```

### Background Monitoring

Use `monitor_cmd()` for long-running processes or when you need real-time output:

```python
runner = CmdLineRunner()
monitor = runner.monitor_cmd("npm", ["run", "build"])

while monitor.is_running():
    if monitor.is_new_stdout():
        # Process output in real-time
        log_to_file(monitor.get_stdout())
```

### Interactive Processes

For processes requiring stdin interaction:

```python
monitor = runner.monitor_cmd("python", ["-i"])

# Send input
monitor.write_stdin("import math\n")
monitor.write_stdin("print(math.pi)\n")

# Read output
time.sleep(0.1)
print(monitor.get_stdout())
```

## Threading Model

- Main thread: Manages process lifecycle
- stdout thread: Continuously reads stdout
- stderr thread: Continuously reads stderr  
- wait thread: Monitors process completion

All threads are daemon threads and will terminate when the main program exits.

## Dependencies

- [core.tools](../core/tools.py) - ToolProvider base class
- [core.monitor](../core/monitor.py) - Monitor decorator
- `subprocess` - Python subprocess management
- `threading` - Thread management for background monitoring
