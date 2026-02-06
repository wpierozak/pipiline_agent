from pipiline_agent.jenkins_utils.JobInfo import JobInfo
import os

class BuildData:
    """
    Manages the retrieval of build data and artifacts from Jenkins.
    """
    def __init__(self, job_info: JobInfo, build_number: int = -1):
        """
        Initializes the BuildData instance.

        Args:
            build_number (int, optional): The build number to retrieve. Defaults to None.
        """
        self.server = job_info.getServer()
        if build_number == -1:
            build_number = self.server.get_job_info(job_info.name())['lastBuild']['number']
        self.build = self.server.get_build_info(job_info.name(), build_number)
        self.artifacts = self.build.get('artifacts')
    
    def _writeLogFile(self, dest:str, build, artifactPath):
        """
        Writes a single log artifact to a file.

        Args:
            dest (str): The destination file path.
            build (dict): The build information.
            artifactPath (str): The relative path of the artifact on Jenkins.

        Returns:
            int: The number of bytes written.
        """
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            writtenBytes = f.write(self.server.get_build_artifact_as_bytes(JobInfo.name(), 
                                                        self.build['number'], 
                                                        artifactPath))   
        return writtenBytes
    
    def fetchLogs(self, dest: str = "./logs") -> str:
        """
        Fetches log artifacts from the build and saves them to the destination directory.

        Args:
            dest (str, optional): Destination directory. Defaults to "./logs".

        Returns:
            str: The path to the directory where logs were saved.
        """
        os.makedirs(dest, exist_ok=True)
        if self.artifacts:
            for artifact in self.artifacts:
                relativePath = artifact['relativePath']
                if ".log" in relativePath:
                    print(f"Downloading {relativePath}...")
                    destPath = dest + "/" + artifact['relativePath']
                    writtenBytes = self._writeLogFile(destPath, self.build['number'],  relativePath) 
                    print(f"Saved {writtenBytes} bytes to {destPath}")
        return dest