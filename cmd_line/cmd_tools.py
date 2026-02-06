from pipiline_agent.core.tools import ToolProvider
from dataclasses import dataclass
from pipiline_agent.core.monitor import Monitor
import subprocess
import threading

@dataclass
class CmdLineOutput:
    stdout: str
    stderr: str

@Monitor
class CmdLineMonitor:
    """
    Monitors the output of a command.
    """
    def __init__(self, process: subprocess.Popen):
        self._stdout : list[str] = []
        self._stderr : list[str] = []
        self._stdout_ptr : int = 0
        self._stderr_ptr : int = 0
        self._process_finished : bool = False
        self._process_code : int = -1
        self.__process : subprocess.Popen = process

    def write_stdin(self, stdin: str):
        """
        Writes to the stdin of the process.

        Args:
            stdin (str): The stdin to write.
        """
        self.__process.stdin.write(stdin)
        self.__process.stdin.flush()

    def update_stdout(self, stdout: str):
        """
        Updates the stdout.

        Args:
            stdout (str): The stdout to update.
        """
        self._stdout.append(stdout)

    def update_stderr(self, stderr: str):
        """
        Updates the stderr.

        Args:
            stderr (str): The stderr to update.
        """
        self._stderr.append(stderr)

    def is_new_stdout(self) -> bool:
        """
        Checks if there is new stdout.

        Returns:
            bool: True if there is new stdout, False otherwise.
        """
        result: bool = False
        result = (self._stdout_ptr != len(self._stdout))
        return result
    
    def is_new_stderr(self) -> bool:
        """
        Checks if there is new stderr.

        Returns:
            bool: True if there is new stderr, False otherwise.
        """
        result = (self._stderr_ptr != len(self._stderr))
        return result

    def get_stdout(self) -> str:
        """
        Gets the stdout.

        Returns:
            str: The stdout.
        """
        result: str = ""
        for idx in range(self._stdout_ptr, len(self._stdout)):
            result += str(self._stdout[idx])
        self._stdout_ptr = len(self._stdout)
        return result
    
    def get_stderr(self) -> str:
        """
        Gets the stderr.

        Returns:
            str: The stderr.
        """
        result: str = ""
        for idx in range(self._stderr_ptr, len(self._stderr)):
            result += str(self._stderr[idx])
        self._stderr_ptr = len(self._stderr)
        return result
    
    def is_running(self) -> bool:
        """
        Checks if the process is running.

        Returns:
            bool: True if the process is running, False otherwise.
        """
        return self._process_finished

    def set_finished(self, code: int):
        """
        Sets the process as finished.

        Args:
            code (int): The exit code of the process.
        """
        self._process_finished = True
        self._process_code = code

    def get_process_code(self) -> int:
        """
        Gets the exit code of the process.

        Returns:
            int: The exit code of the process.
        """
        return self._process_code
    

class CmdLineRunner:
    def __init__(self):
        pass

    def execute_cmd(self, cmd: str, args: list[str] = []) -> CmdLineOutput:
        """
        Runs a command and returns its output.

        Args:
            cmd (str): The command to run.
            args (list[str], optional): The arguments to pass to the command. Defaults to [].

        Returns:
            CmdLineOutput: The output of the command.
        """
        output = subprocess.run([cmd] + args, capture_output=True, text=True)
        return CmdLineOutput(output.stdout, output.stderr)
    
    def _read_str(self, stream, output_call):
        while True:
            line = stream.readline()
            if not line:
                break
            output_call(line)
    
    def monitor_cmd(self, cmd: str, args: list[str] = [], bufsize : int = 1) -> CmdLineMonitor:
        """
        Runs a command and monitors its output.

        Args:
            cmd (str): The command to run.
            args (list[str], optional): The arguments to pass to the command. Defaults to [].
            bufsize (int, optional): The buffer size for reading the output. Defaults to 1.

        Returns:
            CmdLineMonitor: The monitor object.
        """
        self._process = subprocess.Popen(
            args = [cmd] + args,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            stdin = subprocess.PIPE,
            text = True,
            bufsize = bufsize
        )
        self._monitor = CmdLineMonitor(self._process)

        self._t_out = threading.Thread(target = self._read_str, args = (self._process.stdout, self._monitor.update_stdout))
        self._t_err = threading.Thread(target = self._read_str, args = (self._process.stderr, self._monitor.update_stderr))
        
        def wait_for_process():
            self._process.wait()
            self._monitor.set_finished(self._process.returncode)

        self._t_wait = threading.Thread(target = wait_for_process)

        self._t_out.daemon = True
        self._t_err.daemon = True
        self._t_wait.daemon = True
        
        self._t_out.start()
        self._t_err.start()
        self._t_wait.start()

        return self._monitor

