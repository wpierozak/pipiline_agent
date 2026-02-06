from pipiline_agent.core.tools import ToolProvider, toolmethod, ToolFactory
import pipiline_agent.directory.file_access as file_access
import pipiline_agent.directory.workdir as workdir
from pipiline_agent.cmd_line.cmd_tools import CmdLineMonitor, CmdLineRunner
import os
import time
from enum import Enum

class PythonWorkSpace(ToolProvider):
    def __init__(self, path: str, python_path: str = "python", create_venv: bool = False, allow_read_only: bool = False):
        super().__init__()
        self.workdir = workdir.WorkDir(path)
        self.python_path = python_path
        self._cmd_line_runner : CmdLineRunner = CmdLineRunner()
        self.use_venv = create_venv
        self.monitor : CmdLineMonitor = None
        if create_venv:
            self.create_venv()
        self.allow_read_only = allow_read_only
    
    def create_venv(self):
        path = self.workdir.dir.get_source_dir() + "/venv"
        self._cmd_line_runner.execute_cmd(cmd = self.python_path, args = ["-m", "venv", path])
        self.python_path = path + "/bin/python"
    
    @toolmethod(name = "create_script")
    def create_script(self, relative_path: str, content: str = "") -> str:
        """
        Creates a Python script.

        Args:
            relative_path (str): The path to the script.
            content (str, optional): The content of the script. Defaults to "".

        Returns:
            str: returns error message or confirmation message.
        """
        if self.allow_read_only:
            return "Error: Read only mode is enabled."
        try:
            self.workdir.dir.create_file(relative_path, content)
        except RuntimeError as err:
            return str(err)
        return f"{relative_path} created"

    @toolmethod(name = "overwrite_script")
    def overwrite_script(self, relative_path: str, content: str = "") -> str:
        """
        Overwrites a Python script.

        Args:
            relative_path (str): The path to the script.
            content (str, optional): The content of the script. Defaults to "".

        Returns:
            str: returns error message or confirmation message.
        """
        if self.allow_read_only:
            return "Error: Read only mode is enabled."
        try:
            self.workdir.dir.create_file(relative_path, content, True)
        except RuntimeError as err:
            return str(err)
        return f"{relative_path} overwritten"

    @toolmethod(name = "run_script")
    def run_script(self, script_path: str, args: list[str], run_background: bool = False) -> str:
        """
        Runs a Python scripts.

        Args:
            script_path (str): The path to the script.
            args (list[str]): The arguments to pass to the script.
            run_background (bool, optional): If True, runs the script in background. Defaults to False.

        Returns:
            str: The output of the script or confirmation message that process was started in background mode.
            To monitor process use monitor_process tool.
        """
        path = self.workdir.dir.get_source_dir() + "/" + script_path
        
        if run_background:
            if self.monitor is not None and self.monitor.is_running():
                 return "Error: A process is already running in background. Please stop it or wait for it to finish."
            self.monitor = self._cmd_line_runner.monitor_cmd(cmd = self.python_path, args = [path] + args)
            return "Process started in background mode."
            
        output = self._cmd_line_runner.execute_cmd(cmd = self.python_path, args = [path] + args)
        return f"Stdout: {output.stdout}\nStderr: {output.stderr}"

    @toolmethod(name = "monitor_process")
    def monitor_background_process(self, timeout: float = None, min_time: float = 0.0) -> str:
        """
        Monitors script started in background for output / execution end.

        Args:
            timeout (float, optional): The timeout in seconds. Defaults to None (indefinite).
            min_time (float, optional): Minimum time in seconds to wait before returning. Defaults to 0.0.

        Returns:
            str: string in json format: {"stdout": "stdout", "stderr": "stderr", "process_code": "process_code"}
        """
        if self.monitor is None:
            return "Error: No attached process found."

        start_time = time.time()
        stdout = ""
        stderr = ""
        
        while True:
            if self.monitor.is_new_stdout():
                stdout += self.monitor.get_stdout()
            
            if self.monitor.is_new_stderr():
                stderr += self.monitor.get_stderr()

            if not self.monitor.is_running():
                 return f"Process finished with code {self.monitor.get_process_code()}\nOutput:\n{output_buffer}"

            elapsed_time = time.time() - start_time
            
            if elapsed_time >= min_time:
                if (stdout or stderr):
                    break
            
                if timeout is not None and elapsed_time > timeout:
                    break

            time.sleep(0.1)
        return f"stdout: {stdout}\nstderr: {stderr}"

    @toolmethod(name = "write_to_stdin")
    def write_to_stdin(self, contnet: str) -> str:
        """
        Writes to the stdin of the background process.

        Args:
            contnet (str): The content to write.
        """
        if self.monitor is None:
            return "Error: No attached process found."
        self.monitor.write_stdin(contnet)
        return "OK"

class PythonWorkSpaceFactory(ToolFactory):
    def __init__(self):
        super().__init__(PythonWorkSpace)