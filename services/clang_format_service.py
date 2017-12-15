import distutils.spawn
import logging
import os
import subprocess
import cxxd.service

class ClangFormat(cxxd.service.Service):
    def __init__(self, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.clang_format_binary = distutils.spawn.find_executable('clang-format')
        self.clang_format_opts = '-i -style=file -assume-filename='
        self.clang_format_config_file = None
        self.clang_format_success_code = 0

    def startup_callback(self, args):
        # TODO add support for range-based formatting (-offset, -length)
        if self.clang_format_binary:
            config_file = args[0]
            if os.path.isfile(config_file):
                self.clang_format_config_file = config_file
                logging.info("Config_file = {0}".format(config_file))
            else:
                logging.error('Provided clang-format configuration file , \'{0}\', does not exist. Please check if correct path is given.'.format(config_file))
            logging.info('clang-format version: \'{0}\''.format(subprocess.check_output([self.clang_format_binary, '-version'])))
        else:
            logging.error('clang-format executable not found on your system path!')

    def shutdown_callback(self, args):
        pass

    def __call__(self, args):
        filename = args[0]
        if self.clang_format_binary and self.clang_format_config_file and os.path.isfile(filename):
            cmd = self.clang_format_binary + ' ' + self.clang_format_opts + self.clang_format_config_file + ' ' + filename
            ret = subprocess.call(cmd, shell=True)
            logging.info("clang-format over '{0}' completed. Command = '{1}'".format(filename, cmd))
            return ret == self.clang_format_success_code, None
        return False, None
