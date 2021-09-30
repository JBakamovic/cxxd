from builtins import str
import logging
import os
import subprocess
import tempfile
import time
import cxxd.service

class Disassembly(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.disassembly_binary = self.cxxd_config_parser.get_disassembly_binary_path()
        self.disassembly_output = None
        self.disassembly_success_code = 0
        if self.disassembly_binary:
            self.disassembly_output = tempfile.NamedTemporaryFile(suffix='_disassembly_output')
            logging.info('disassembly version: \'{0}\''.format(subprocess.check_output([self.disassembly_binary, '--version'])))
        else:
            logging.error('disassembly executable not found!')

    def startup_callback(self, args):
        return True, []

    def shutdown_callback(self, args):
        return True, []

    def _run_on_symbol(self, filename, target, line):
        #_ZN2ut15new_arr_withkeyIcJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 82e729 c7	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIdJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 8303ce d4	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIeJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 82f6ff d0	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIfJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 8310e7 d4	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIhJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 6ea0bb c7	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_N2ut15new_arr_withkeyIiJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 835dd8 d2	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIjJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 834d06 d2	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyIlJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 833a6b d3	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #_ZN2ut15new_arr_withkeyImJEEEPT_NS_16PSI_memory_key_tENS_5CountEDpOT0_ W 832a67 d3	/home/jbakamov/development/mysql/trunk/storage/innobase/include/ut0new.h:1602
        #
        # def get_mangled_symbol_name():
        #   for each line in {nm -P -l target}
        #     f_name, line_nr = extract_filename_and_line_nr(line)
        #     if f_name == filename and line_nr == line
        #       return extract_mangled_symbol_name(line)
        #   return None
        #
        # objdump --disassemble=get_mangled_symbol_name() -l -R --no-show-raw-insn --inlines --visualize-jumps=extended-color target
        pass

    def __call__(self, args):
        def find_mangled_symbol_name_from_nm_output(filename, line_nr, target):
            import io
            import subprocess
            proc = subprocess.Popen(["nm", "-P", "-l", target], stdout=subprocess.PIPE)
            for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
                nm_entry = line.split()
                nm_symbol_name = nm_entry[0]
                nm_filename_and_line_nr = nm_entry[4] if len(nm_entry) > 4 else None
                if nm_filename_and_line_nr is not None:
                    nm_filename, nm_line_nr = nm_filename_and_line_nr.split(':')
                else:
                    nm_filename = None
                    nm_line_nr = None
                logging.debug("nm line output: {0}".format(line))
                logging.debug("nm symbol {0}".format(nm_symbol_name))
                logging.debug("nm filename {0}".format(nm_filename))
                logging.debug("nm line_nr {0}".format(nm_line_nr))
                if filename == nm_filename and line_nr == nm_line_nr:
                    return nm_symbol_name
            return None

        logging.info('Running disassembly over {0}'.format(args))
        filename = args[1]
        line_nr = args[2]

        target = '/home/jbakamov/development/mysql/build/trunk/relwithdbg/bin/merge_innodb_tests-t'
        if self.disassembly_binary and os.path.isfile(filename):
            mangled_symbol = find_mangled_symbol_name_from_nm_output(filename, line_nr, target)
            if mangled_symbol is not None:
                logging.info("Mangled symbol found: {0}".format(mangled_symbol))
                cmd = self.disassembly_binary + ' --disassemble=' + mangled_symbol + ' -S -l -R --no-show-raw-insn --inlines --no-addresses ' + target + ' | c++filt' #--visualize-jumps=extended-color '
                with open(self.disassembly_output.name, 'w') as f:
                    ret = subprocess.call(cmd, shell=True, stdout=f)
                    logging.info("disassembly over '{0}' completed. Command = '{1}'".format(filename, cmd))
                return True, self.disassembly_output.name
        logging.info("Mangled symbol for given filename {0}, line {1}, target {2} was not found: {0}".format(filename, line_nr, target))
        return False, None
