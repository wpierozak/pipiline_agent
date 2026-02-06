from pipiline_agent.jenkins_utils.JobInfo import JobInfo
from pipiline_agent.jenkins_utils.Build import Build
from pipiline_agent.jenkins_utils.BuildData import BuildData
import time

class Job:
    """
    Represents a Jenkins job and handles triggering builds and waiting for results.
    """
    def __init__(self, job_info: JobInfo):
        """
        Initializes the JenkinsJob instance by connecting to the server and getting job info.
        """
        self.job_info = job_info
        self.server = job_info.getServer()
        self.job_name = job_info.name()

    def build_and_wait(self, timeout):
        """
        Triggers a build and waits for it to complete or timeout.

        Args:
            timeout (int): The maximum time to wait in seconds.

        Returns:
            dict: A dictionary containing the result of the build ("result": status).
        """
        self.build_number = self.server.get_job_info(self.job_name)['nextBuildNumber']
        self.server.build_job(self.job_name)
        start_time = time.time()
        
        while (time.time() - start_time < timeout):
            try:
                build_info = self.server.get_build_info(self.job_name, self.build_number)
                if not build_info['building']:
                    return {"result": build_info['result']}
                
            except Exception as e:
                print(f"Waiting for build to initialize... ({e})")

            time.sleep(5) 

        return {"result" : "timeout"}

    def get_last_build_result(self):
        self.build_number = self.server.get_job_info(self.job_name)['nextBuildNumber'] - 1
        try:
            build_info = self.server.get_build_info(self.job_name, self.build_number)
            if not build_info['building']:
                return {"result": build_info['result']}
        except Exception as e:
            print(f"Failed to process last build ({e})")
        return {"result" : "timeout"}

    def jenkins_run_build(self, timeout: int, fetch_only_on_failed: bool = True):
        """
        Runs a Jenkins build and handles the result, optionally fetching logs.

        Args:
            job_info (JobInfo): The Jenkins job configuration.
            timeout (int): The maximum time to wait for the build.
            fetch_only_on_failed (bool, optional): Whether to fetch logs only if the build fails. Defaults to True.

        Returns:
            BuildResult: The result of the build and logs.
        """
        result = self.build_and_wait(timeout)
        fetch_data = False
        logs = None
        state: BuildState
        if result["result"] == JobInfo.jobSuccess():
            fetch_data = not fetch_only_on_failed
            state = BuildState.success
        if result["result"] == JobInfo.jobTimeout():
            fetch_data = False
            state = BuildState.timeout
        if result["result"] == JobInfo.jobFailed():
            fetch_data = True
            state = BuildState.failure
        if fetch_data:
            build = BuildData(job_info)
            logDir = build.fetchLogs()
            logs = Repository(logDir, ".log")
        return Build(state, logs)