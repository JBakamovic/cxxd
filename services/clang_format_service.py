import distutils.spawn
import logging
import os
import subprocess
import cxxd.service

class ClangFormat(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.clang_format_binary = distutils.spawn.find_executable('clang-format')
        self.clang_format_args = self._stringify_clang_format_args(
            self.cxxd_config_parser.get_clang_format_args()
        )
        self.clang_format_success_code = 0

    def _stringify_clang_format_args(self, args):
        clang_format_args = ''
        for arg, value in args:
            if isinstance(value, bool):
                if value:
                    clang_format_args += arg + ' '
            else:
                clang_format_args += arg + '=' + value
        return clang_format_args

    def startup_callback(self, args):
        if self.clang_format_binary:
            logging.info('clang-format version: \'{0}\''.format(subprocess.check_output([self.clang_format_binary, '-version'])))
        else:
            logging.error('clang-format executable not found on your system path!')

    def shutdown_callback(self, args):
        pass

    def __call__(self, args):
        # TODO add support for range-based formatting (-offset, -length)
        filename = args[0]
        if self.clang_format_binary and os.path.isfile(filename):
            cmd = self.clang_format_binary + ' ' + self.clang_format_args + ' ' + filename
            ret = subprocess.call(cmd, shell=True)
            logging.info("clang-format over '{0}' completed. Command = '{1}'".format(filename, cmd))
            return ret == self.clang_format_success_code, None
        return False, None
