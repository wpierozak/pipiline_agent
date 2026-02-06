import os
import pathlib
import pipiline_agent.directory.file_access as file_access

class WorkDir:
    def __init__(self, path: str) -> None:
        if os.path.exists(path) == True and os.path.isdir(path) == False:
            raise RuntimeError(f"{path} is not a directory!")
        os.makedirs(path, exist_ok=True)
        self.dir = file_access.Directory(path)
    
    def clear(self):
        dir_obj = pathlib.Path(self.dir.get_source_dir())
        for item in dir_obj.iterdir():
            os.remove(str(item.absolute()))

    def get_dir(self):
        return self.dir