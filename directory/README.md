# Directory Module

## Overview

The `directory` module provides file system access utilities with lazy-loading capabilities, directory traversal, and file management. It's designed for efficient handling of large directory structures and file operations.

## Classes

### FileType

Enumeration for file types.

**Values:**
- `Text = 0`: Text file type

---

### BaseFile

Abstract base class for file representations.

**Methods:**
- `type() -> FileType`: Returns the file type (must be overridden)

---

### TextFile

Lazy-loading text file implementation. File content is only read from disk when explicitly requested, reducing memory usage for large file sets.

**Constructor Parameters:**
- `path` (str): Absolute path to the file

**Key Methods:**

#### `get() -> str`
Returns file content, reading from disk if not already cached in memory.

#### `read() -> str`
Reads file content from disk.

#### `clean_buffer()`
Clears cached content from memory to free up resources.

#### `get_len() -> int`
Returns the length of file content (uses cached content or file size on disk).

#### `append(content: str)`
Appends content to the file.

#### `overwrite(content: str)`
Overwrites the file with new content.

#### `type() -> FileType`
Returns `FileType.Text`.

**Lazy Loading Benefits:**
- Memory efficient: Content only loaded when needed
- Large directories: Can represent thousands of files without loading all content
- Manual control: Call `clean_buffer()` to free memory after processing

**Example Usage:**
```python
from pipiline_agent.directory.file_access import TextFile

file = TextFile("/path/to/document.txt")

# Content not loaded yet
print(file.path)  # /path/to/document.txt

# First access loads content
content = file.get()
print(len(content))

# Subsequent access uses cached content
content_again = file.get()  # No disk read

# Clear cache
file.clean_buffer()

# Next access will read from disk again
content_fresh = file.get()
```

---

### Directory

File system repository providing access to files and directories with optional filtering.

**Constructor Parameters:**
- `source` (str): Path to the source directory
- `file_extension` (str, default=""): Filter files by extension (e.g., ".py", ".log")

**Raises:**
- `ValueError`: If source is not a valid directory

**Key Methods:**

#### `get_source_dir() -> str`
Returns the absolute path to the source directory.

#### `unpack(path: str) -> dict`
Recursively unpacks directory structure into a nested dictionary:
- Directories → nested dictionaries
- Files → `TextFile` objects
- Filtered by `file_extension` if specified

**Returns:**
- Dictionary representing directory tree structure

#### `read_text_file(filePath: str) -> str`
Reads and returns the content of a text file.

**Parameters:**
- `filePath` (str): Path to the file

#### `print_structure(current_dict=None, indent_level=0)`
Prints a visual tree representation of the repository structure.

#### `get_all_paths() -> list[str]`
Returns a list of all file paths relative to the repository root.

**Example:**
```python
["script.py", "src/main.py", "src/utils/helper.py"]
```

#### `get_file_by_path(path_str: str) -> BaseFile`
Retrieves a file object by its relative path.

**Parameters:**
- `path_str` (str): Relative path to the file (e.g., "src/main.py")

**Returns:**
- `BaseFile`: The requested file object

**Raises:**
- `RuntimeError`: If path not found or path points to a directory

#### `create_file(relative_path: str, content: str = "", exists_ok: bool = False)`
Creates a new file with optional content. Automatically creates parent directories if needed.

**Parameters:**
- `relative_path` (str): Path relative to source directory
- `content` (str): Initial file content
- `exists_ok` (bool): If False, raises error if file exists; if True, overwrites

**Raises:**
- `RuntimeError`: If file exists and `exists_ok=False`

**Example Usage:**

**Basic Directory Traversal:**
```python
from pipiline_agent.directory.file_access import Directory

# Load all Python files
repo = Directory("/path/to/project", file_extension=".py")

# Print structure
repo.print_structure()

# Get all file paths
all_files = repo.get_all_paths()
print(all_files)
```

**Lazy File Reading:**
```python
repo = Directory("/path/to/logs", file_extension=".log")

# Get file handle (content not loaded yet)
log_file = repo.get_file_by_path("application.log")

# Load content only when needed
if some_condition:
    content = log_file.get()
    analyze(content)
```

**File Creation:**
```python
repo = Directory("/workspace")

# Create file with directories
repo.create_file("src/utils/config.py", content="DEBUG = True\n")

# File created at: /workspace/src/utils/config.py
```

**Processing Large Repositories:**
```python
repo = Directory("/large/codebase", file_extension=".py")

# Iterate through files without loading all content
for path in repo.get_all_paths():
    file = repo.get_file_by_path(path)
    
    # Only load files matching criteria
    if "test" in path:
        content = file.get()
        run_tests(content)
        file.clean_buffer()  # Free memory
```

---

### WorkDir

Workspace directory manager that ensures directory existence and provides cleanup utilities.

**Constructor Parameters:**
- `path` (str): Path to workspace directory

**Raises:**
- `RuntimeError`: If path exists but is not a directory

**Fields:**
- `dir` (Directory): Directory instance for the workspace

**Key Methods:**

#### `clear()`
Removes all items in the workspace directory.

#### `get_dir() -> Directory`
Returns the Directory instance.

**Example Usage:**

**Initialize Workspace:**
```python
from pipiline_agent.directory.workdir import WorkDir

# Creates directory if it doesn't exist
workspace = WorkDir("./my_workspace")

# Access directory operations
workspace.dir.create_file("script.py", "print('hello')")
```

**Clean Workspace:**
```python
workspace = WorkDir("./temp_workspace")

# Do work...
workspace.dir.create_file("output.txt", "results")

# Clean up all files
workspace.clear()
```

**Ensure Directory:**
```python
# Safe initialization - creates if missing
workspace = WorkDir("/path/to/workspace")

# Can now use directory operations
all_files = workspace.dir.get_all_paths()
```

## Usage Patterns

### Efficient Large Directory Handling

```python
# Only load files as needed
repo = Directory("/large/dataset", file_extension=".csv")

for path in repo.get_all_paths():
    file = repo.get_file_by_path(path)
    
    # Check file size before loading
    if file.get_len() < 1_000_000:  # Only process small files
        data = file.get()
        process(data)
        file.clean_buffer()  # Free memory
```

### File Filtering by Extension

```python
# Process only Python files
python_repo = Directory("/project", file_extension=".py")

# Process only log files
log_repo = Directory("/var/log", file_extension=".log")
```

### Workspace Management

```python
# Create temporary workspace
workspace = WorkDir("./temp")

try:
    # Create and manipulate files
    workspace.dir.create_file("data.json", json_content)
    workspace.dir.create_file("results/output.txt", results)
finally:
    # Clean up
    workspace.clear()
```

## Directory Structure Representation

Directory is represented as nested dictionaries:

```python
{
    "script.py": TextFile("/path/script.py"),
    "src": {
        "main.py": TextFile("/path/src/main.py"),
        "utils": {
            "helper.py": TextFile("/path/src/utils/helper.py")
        }
    }
}
```

## Dependencies

- `os` - File system operations
- `pathlib` - Path manipulation (WorkDir)
