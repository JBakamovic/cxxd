import logging
import os
import subprocess
import tempfile
import time
import cxxd.service

class ProjectBuilder(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.build_args = self._stringify_project_builder_args(
            self.cxxd_config_parser.get_project_builder_args()
        )
        self.build_cmd_output_file = tempfile.NamedTemporaryFile(suffix='_project_build_output')
        logging.info("Build command will be executed from \'{0}\' directory. Output will be recorded into \'{1}\'.".format(self.project_root_directory, self.build_cmd_output_file.name))

    def _stringify_project_builder_args(self, args):
        project_builder_args = ''
        for arg, value in args:
            if isinstance(value, bool):
                if value:
                    project_builder_args += arg + ' '
            else:
                project_builder_args += arg + '=' + value
        return project_builder_args

    def startup_callback(self, args):
        pass

    def shutdown_callback(self, args):
        pass

    def __call__(self, args):
        build_cmd = args[0] + ' ' + self.build_args
        start = time.clock()
        self.build_cmd_output_file.truncate()
        cmd = "cd " + self.project_root_directory + " && " + build_cmd
        build_exit_code = subprocess.call(cmd, shell=True, stdout=self.build_cmd_output_file, stderr=self.build_cmd_output_file)
        end = time.clock()
        logging.info("Cmd '{0}' took {1}. Status = {2}".format(cmd, end-start, build_exit_code))
        return True, [self.build_cmd_output_file.name, build_exit_code, end-start]
