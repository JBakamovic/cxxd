import logging
import os
import subprocess
import tempfile
import time
import cxxd.service

class ProjectBuilder(cxxd.service.Service):
    def __init__(self, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.build_cmd_dir = None
        self.build_cmd_output_file = None

    def startup_callback(self, args):
        build_cmd_dir = args[0]
        if os.path.isdir(build_cmd_dir):
            self.build_cmd_dir = build_cmd_dir
            self.build_cmd_output_file = tempfile.NamedTemporaryFile(suffix='_project_build_output')
            logging.info("Build command will be executed from \'{0}\' directory. Output will be recorded into \'{1}\'.".format(build_cmd_dir, self.build_cmd_output_file.name))
        else:
            logging.error('Provided directory, \'{0}\', is not valid!'.format(build_cmd_dir))

    def shutdown_callback(self, args):
        pass

    def __call__(self, args):
        build_cmd = args[0]
        if self.build_cmd_dir and self.build_cmd_output_file:
            start = time.clock()
            self.build_cmd_output_file.truncate()
            cmd = "cd " + self.build_cmd_dir + " && " + build_cmd
            build_exit_code = subprocess.call(cmd, shell=True, stdout=self.build_cmd_output_file, stderr=self.build_cmd_output_file)
            end = time.clock()
            logging.info("Cmd '{0}' took {1}. Status = {2}".format(cmd, end-start, build_exit_code))
            return True, [self.build_cmd_output_file.name, build_exit_code, end-start]
        return False, None
