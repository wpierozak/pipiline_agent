import jenkins
from jenkins import _JSON
import re
import os

class JobInfo:
    """
    Stores and manages job information and configuration.
    """
    def __init__(self, server: str, job: str, username: str, password: str):
        """
        Sets up the JobInfo with server details and credentials.

        Args:
            server (str): The Jenkins server URL.
            job (str): The name of the job.
            username (str): The username for authentication.
            password (str): The password or API token for authentication.
        """
        self.s_server = server
        self.s_job = job
        self.s_username = username
        self.s_password = password
        self.jenkins_server = jenkins.Jenkins(self.s_server, username=self.s_username, password=self.s_password)
        print(f"Logged into {self.jenkins_server.get_whoami()['fullName']}")

    def name(self) -> str:
        """
        Returns the job name.
        """
        return self.s_job
    
    def username(self) -> str:
        """
        Returns the username.
        """
        return self.s_username
    
    def passwd(self) -> str:
        """
        Returns the password.
        """
        return self.s_password
    
    def getServer(self):
        """
        Connects to the Jenkins server and returns the Jenkins instance.

        Returns:
            jenkins.Jenkins: The connected Jenkins instance.
        """
        return self.jenkins_server
    
    def getLastBuild(self, fetch_data: bool = False, file_filter: str = ""):
        build_number = self.jenkins_server.get_job_info(self.s_job)['nextBuildNumber'] - 1
        try:
            build_info = self.jenkins_server.get_build_info(self.s_job, build_number)
            if not build_info['building']:
                return {"result": build_info['result']}
        except Exception as e:
            print(f"Failed to process last build ({e})")
        return {"result" : "timeout"}

    def getBuild(self, build_number: int, fetch_data: bool = False, file_filter: str = ""):
        build_info = self.jenkins_server.get_build_info(self.s_job, build_number)
        
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
    
    def fetch(self, build_info: _JSON, dest: str = "./build", filter: str = "") -> str:
        """
        Fetches log artifacts from the build and saves them to the destination directory.

        Args:
            dest (str, optional): Destination directory. Defaults to "./logs".

        Returns:
            str: The path to the directory where logs were saved.
        """
        artifacts = build_info.get("artifacts")
        if artifacts is None:
            return ""
        os.makedirs(dest, exist_ok=True)
        for artifact in artifacts:
                relativePath = artifact['relativePath']
                if ".log" in relativePath:
                    print(f"Downloading {relativePath}...")
                    destPath = dest + "/" + artifact['relativePath']
                    writtenBytes = self._writeLogFile(destPath, self.build['number'],  relativePath) 
                    print(f"Saved {writtenBytes} bytes to {destPath}")
        return dest
    
    @staticmethod
    def jobSuccess():
        """
        Returns the string representation of a successful job status.
        """
        return "SUCCESS"
    
    @staticmethod
    def jobTimeout():
        """
        Returns the string representation of a timeout job status.
        """
        return "timeout"
    
    @staticmethod
    def jobFailed():
        """
        Returns the string representation of a failed job status.
        """
        return "FAILED"