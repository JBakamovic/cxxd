import logging
import os
import subprocess
import tempfile
import cxxd.service

class IwyuRequestId(object):
    RUN                 = 0x0
    RUN_AND_APPLY_FIXES = 0x1

class Iwyu(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.target = target
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.iwyu_compilation_db = None
        self.iwyu_binary = cxxd_config_parser.get_iwyu_binary_path()
        self.iwyu_args = self._stringify_iwyu_args(
            self.cxxd_config_parser.get_iwyu_args()
        )
        self.iwyu_success_code = 0
        self.service = {
            IwyuRequestId.RUN                   : self._run_iwyu,
            IwyuRequestId.RUN_AND_APPLY_FIXES   : self._run_and_apply_fixes,
        }
        self.iwyu_output = tempfile.NamedTemporaryFile(suffix='_iwyu_output')
        self.fix_includes = tempfile.NamedTemporaryFile(suffix='_iwyu_fix_includes_output')

    def _stringify_iwyu_args(self, args):
        iwyu_args = ''
        for arg, value in args:
            if isinstance(value, bool):
                if value:
                    iwyu_args += arg
            else:
                iwyu_args += arg + '=' + value
            iwyu_args += ' '
        return iwyu_args

    def __unknown_service(self, args):
        logging.error("Unknown service triggered! Valid services are: {0}".format(self.service))
        return False, None

    def _run_iwyu(self, args):
        filename = args[0]
        if self.iwyu_binary and self.iwyu_compilation_db and os.path.isfile(filename):
            cmd = self.iwyu_binary +  ' ' + self.iwyu_compilation_db + ' ' + filename + ' -- ' + self.iwyu_args
            with open(self.iwyu_output.name, 'w') as f:
                ret = subprocess.call(cmd, shell=True, stdout=f)
                logging.info("iwyu over '{0}' completed. Command = '{1}'".format(filename, cmd))
            return ret == self.iwyu_success_code, self.iwyu_output.name
        return False, None

    def _run_and_apply_fixes(self, args):
        filename = str(args[0])
        self._run_iwyu(args)
        cmd = 'fix_includes ' + filename
        with open(self.iwyu_output.name, 'r') as f_in:
            with open(self.fix_includes.name, 'w') as f_out:
                ret = subprocess.call(cmd, shell=True, stdin=f_in, stdout=f_out)
                logging.info("fix_includes over '{0}' completed. Command = '{1}'".format(filename, cmd))
        return ret == self.iwyu_success_code, self.fix_includes.name

    def startup_callback(self, args):
        if self.iwyu_binary:
            logging.info('iwyu is found')
            configuration = self.cxxd_config_parser.get_configuration_for_target(self.target)
            if configuration:
                root, ext = os.path.splitext(configuration)
                if ext == '.json':
                    self.iwyu_compilation_db = '-p ' + configuration
                    return True, []
                else:
                    logging.error('iwyu: missing compilation-database.')
        else:
            logging.error('iwyu executable not found on your system path!')
        return False, []

    def shutdown_callback(self, args):
        return True, []

    def __call__(self, args):
        return self.service.get(int(args[0]), self.__unknown_service)(args[1:len(args)])
