from pipiline_agent.directory.Directory import Directory
from pipiline_agent.jenkins_utils.JobInfo import JobInfo
from pipiline_agent.jenkins_utils.BuildData import BuildData
from langchain.tools import tool
from enum import Enum
from pipiline_agent.jenkins_utils.JobInfo import JobInfo
import os

class BuildState(Enum):
    """
    Represents the state of a build.
    """
    success = 1,
    failure = 2,
    timeout = 3
    def __str__(self) -> str:
        return super().__str__()

class Build:
    """
    Represents the result of a build execution, including its status and logs.
    """
    def __init__(self, job_info: JobInfo, build_number: int):
        """
        Initializes the BuildResult instance.

        Args:
            job_info: The job information.
            build_number: The number of the build.
        """
        self.build_number = build_number
        self.server = job_info.getServer()
        self.build_data = BuildData(job_info, build_number)
        self.state = self._determine_job_state(job_info)


    def _determine_job_state(self, job_info: JobInfo):
        build_info = self.server.get_build_info(job_info.name(), self.build_number)
        if build_info['result'] == 'SUCCESS':
            return BuildState.success
        elif build_info['result'] == 'FAILURE':
            return BuildState.failure
        elif build_info['result'] == 'ABORTED':
            return BuildState.timeout
        return BuildState.failure