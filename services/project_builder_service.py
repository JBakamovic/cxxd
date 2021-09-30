import logging
import os
import subprocess
import tempfile
import time
import cxxd.service

class ProjectBuilderRequestId(object):
    TARGET_BUILD_CONFIG_CMD = 0x0
    CUSTOM_CMD = 0x1

class ProjectBuilder(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.build_args = self._stringify_project_builder_args(
            self.cxxd_config_parser.get_project_builder_args()
        )
        self.build_dir = self.cxxd_config_parser.get_project_builder_build_dir(target)
        self.build_cmd = self.cxxd_config_parser.get_project_builder_build_cmd(target)
        self.build_cmd_output_file = tempfile.NamedTemporaryFile(suffix='_project_build_output')
        self.service = {
            ProjectBuilderRequestId.TARGET_BUILD_CONFIG_CMD  : self._build_by_reading_target_config_cmd,
            ProjectBuilderRequestId.CUSTOM_CMD               : self._build_by_using_on_air_provided_cmd,
        }
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

    def __unknown_service(self, args):
        logging.error("Unknown service triggered! Valid services are: {0}".format(self.service))
        return False, None

    def _run_the_build(self, cmd):
        start = time.process_time()
        self.build_cmd_output_file.truncate(0)
        build_exit_code = subprocess.call(cmd, shell=True, stdout=self.build_cmd_output_file, stderr=self.build_cmd_output_file)
        end = time.process_time()
        logging.info("Cmd '{0}' took {1}. Status = {2}".format(cmd, end-start, build_exit_code))
        return True, [self.build_cmd_output_file.name, build_exit_code, end-start]

    def _build_by_reading_target_config_cmd(self, args):
        build_cmd = 'cd ' + os.path.join(self.project_root_directory, self.build_dir) + ' && ' + self.build_cmd
        return self._run_the_build(build_cmd)

    def _build_by_using_on_air_provided_cmd(self, args):
        build_cmd = 'cd ' + os.path.join(self.project_root_directory, self.build_dir) + ' && ' + args[0] + ' ' + self.build_args
        return self._run_the_build(build_cmd)

    def startup_callback(self, args):
        return True, [self.build_cmd_output_file.name]

    def shutdown_callback(self, args):
        return True, []

    def __call__(self, args):
        return self.service.get(int(args[0]), self.__unknown_service)(args[1:len(args)])
