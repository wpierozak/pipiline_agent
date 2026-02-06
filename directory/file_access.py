import os
from enum import Enum

class FileType(Enum):
    Text = 0

class BaseFile:
    def type(self) -> FileType:
        raise RuntimeError("type() method has to  be overwrite!")

class TextFile(BaseFile):
    """
    Represents a file that is read lazily only when its content is requested.
    """
    def __init__(self, path: str):
        """
        Initializes the LazyFile instance.

        Args:
            path (str): The absolute path to the file.
        """
        self.path = path
        self.content = None

    def type(self) -> FileType:
        return FileType.Text

    def get(self) -> str:
        """
        Returns the content of the file, reading it if not already in memory.

        Returns:
            str: The file content.
        """
        if self.content is None:
            self.content = self.read()
        return self.content

    def clean_buffer(self):
        """
        Clears the cached content from memory.
        """
        self.content = None

    def read(self) -> str:
        """
        Reads the file content from disk.

        Returns:
            str: The file content.
        """
        with open(self.path, "r") as file:
            return file.read()      
        
    def __len__(self):
        return self.get_len()
    
    def get_len(self) -> int:
        """
        Returns the length of the file content or size on disk.

        Returns:
            int: The size of the file.
        """
        if self.content is None:
            return os.path.getsize(self.path)
        return len(self.content)
    
    def append(self, content: str):
        with open(self.path, "a") as file:
            file.write(content)

    def overwrite(self, content: str):
        with open(self.path, "w") as file:
            file.write(content)


class Directory:
    """
    Represents a file system repository, providing access to files and directories.
    """
    def __init__(self, source: str, file_extension: str = ""):
        """
        Initializes the Repository.

        Args:
            source (str): The path to the source directory.
            file_extension (str, optional): Filter files by extension. Defaults to "".
        
        Raises:
            ValueError: If source is not a directory.
        """
        if (os.path.isdir(source) == False):
            raise ValueError(f"{source} is not a directory") 
        self.source_dir = os.path.abspath(source)
        self.file_extension = file_extension
        self.items = self.unpack(source)

    def get_source_dir(self):
        return self.source_dir
    
    def unpack(self, path: str):
        """
        Recursively unpacks the directory structure into a dictionary of LazyFiles and sub-dictionaries.

        Args:
            path (str): The path to unpack.

        Returns:
            dict: The unpacked structure.
        """
        result = {}
        childs = os.listdir(path)
        for item in childs:
            itemPath = os.path.join(path, item)
            if os.path.isdir(itemPath):
                result[item] = self.unpack(itemPath)
            elif os.path.isfile(itemPath) and (len(self.file_extension) == 0 or item.endswith(self.file_extension)):
                result[item] = TextFile(itemPath)
            else:
                print(f"Ignoring {item}")
        return result

    def read_text_file(self, filePath: str):
        """
        Reads a log file.

        Args:
            filePath (str): The path to the log file.

        Returns:
            str: The content of the file.
        """
        with open(filePath, "r") as file:
            return file.read()
        
    def print_structure(self, current_dict=None, indent_level=0):
        """Prints a visual tree of the repository."""
        if current_dict is None:
            current_dict = self.items
            print(f"ROOT")
        for name, value in current_dict.items():
            indent = "\t" * indent_level
            connector = "├── "
            if isinstance(value, dict):
                print(f"{indent}{connector} {name}/")
                self.print_structure(value, indent_level + 1)
            else:
                print(f"{indent}{connector} {name}")

    def get_all_paths(self) -> list[str]:
        """
        Returns a list of all file paths in the repository relative to the root.

        Returns:
            list[str]: List of relative paths.
        """
        paths = []
        def recurse(current_dict, current_path_prefix):
            for name, item in current_dict.items():
                new_path = f"{current_path_prefix}/{name}" if current_path_prefix else name
                if isinstance(item, dict):
                    recurse(item, new_path)
                else:
                    paths.append(new_path)
        recurse(self.items, "")
        return paths

    def get_file_by_path(self, path_str: str) -> BaseFile:
        """
        Retrieves a LazyFile object by its relative path.

        Args:
            path_str (str): The relative path to the file.

        Returns:
            LazyFile: The requested LazyFile, or None if not found.
        """
        parts = path_str.split('/')
        current = self.items
        try:
            for part in parts:
                current = current[part]
        except KeyError:
            raise RuntimeError(f"Error: Path {path_str} not found.")
        if isinstance(current, TextFile) == False:
                raise RuntimeError(f"Error: Path {path_str} not found.")
        return current
    
    def create_file(self, relative_path: str, content: str = "", exists_ok : bool = False):
        """
        Creates a file.

        Args:
            relative_path (str): The relative path to the file.
            content (str, optional): The content of the file. Defaults to "".
            exists_ok (bool, optional): Whether to raise an error if the file already exists. Defaults to False.

        Raises:
            RuntimeError: If the file already exists and exists_ok is False.
        """
        if os.path.exists(os.path.join(self.source_dir, relative_path)) and exists_ok == False:
            raise RuntimeError(f"File {relative_path} already exists.")
        directory = os.path.dirname(os.path.join(self.source_dir, relative_path))
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(os.path.join(self.source_dir, relative_path), "w") as file:
            file.write(content)