import logging
import os
import subprocess

import time
import shlex
import cxxd.service

class ClangTidy(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.clang_tidy_compile_flags_list = []
        self.clang_tidy_args_list = self._listify_clang_tidy_args(
           self.cxxd_config_parser.get_clang_tidy_args()
        )
        self.clang_tidy_binary = self.cxxd_config_parser.get_clang_tidy_binary_path()
        if self.clang_tidy_binary:
            configuration = self.cxxd_config_parser.get_configuration_for_target(target)
            if configuration:
                root, ext = os.path.splitext(configuration)
                if ext == '.json':
                    self.clang_tidy_compile_flags_list = ['-p', configuration]
                    logging.info('clang-tidy will extract compiler flags from existing JSON database.')
                elif ext == '.txt':
                    with open(configuration) as f:
                        # We use shlex to split the file content safely as it mimics command line args
                        content = f.read().replace('\n', ' ')
                        try:
                            self.clang_tidy_compile_flags_list = ['--'] + shlex.split(content)
                        except:
                            # Fallback if shlex fails, though splitting by space is risky
                            self.clang_tidy_compile_flags_list = ['--'] + content.split()
                    logging.info('clang-tidy will use compiler flags given inline.')
                else:
                    logging.error('clang-tidy requires compiler flags to be provided either inline or via JSON compilation database.')
            else:
                logging.error('clang-tidy requires compiler flags to be provided either inline or via JSON compilation database.')
            
            # Use list for version check too
            try:
                logging.info('clang-tidy version: \'{0}\''.format(subprocess.check_output([self.clang_tidy_binary, '-version']).decode('utf-8').strip()))
            except:
                pass
        else:
            logging.error('clang-tidy executable not found!')

    def _listify_clang_tidy_args(self, args):
        clang_tidy_args = []
        for arg, value in args:
            if isinstance(value, bool):
                if value:
                    clang_tidy_args.append(arg)
            else:
                clang_tidy_args.append(arg + '=' + value)
        return clang_tidy_args

    def startup_callback(self, args):
        logging.info('clang-tidy service started.')
        return True, []

    def shutdown_callback(self, args):
        logging.info('clang-tidy service stopped.')
        return True, []

    def __call__(self, args):
        import json
        from utils import Utils
        filename, apply_fixes = args
        
        def call_vim_rpc(status, filename, fixes_applied, tidylines):
            json_tidylines = json.dumps(tidylines)
            Utils.call_vim_remote_function(
                "cxxd#services#clang_tidy#run_callback(" + str(int(status)) + ", '" + filename + "', " + str(int(fixes_applied)) + ", " + json_tidylines + ")"
            )

        if self.clang_tidy_binary and self.clang_tidy_compile_flags_list and os.path.isfile(filename):
            cmd = [self.clang_tidy_binary, filename]
            if apply_fixes:
                cmd.append('-fix')
            
            # Append configured args and flags
            # Order: binary file [fix] [compile_flags (-p or -- flags)] [tidy_args]
            # Usually flags come after --, args come before?
            # Clang-tidy usage: clang-tidy [options] <source0> [... <sourceN>] [-- <compiler-arguments>]
            # So compiler flags (after --) should be LAST.
            # But '-p' is an option, so it can be anywhere.
            # self.clang_tidy_compile_flags_list might start with '--'.
            # self.clang_tidy_args_list has options like -checks.
            # Safe order: options first, then file (already there), then -- flags.
            # But we put file in cmd[1].
            # Let's adjust: binary [options] file [ -- flags]
            
            # Re-assemble:
            # [binary] + args_list + [file] + (['-fix']?) + compile_flags_list
            
            # Actually, standard usage:
            # clang-tidy [options] file -- [flags]
            
            full_cmd = [self.clang_tidy_binary]
            full_cmd.extend(self.clang_tidy_args_list) # checks etc.
            if apply_fixes:
                full_cmd.append('-fix')
            
            full_cmd.append(filename)
            
            full_cmd.extend(self.clang_tidy_compile_flags_list)
            
            logging.info("Triggering clang-tidy over '{0}' with cmd={1}".format(filename, full_cmd))
            
            try:
                # shell=False, pass list
                output_bytes = subprocess.check_output(full_cmd)
                output_lines = output_bytes.decode('utf-8', errors='ignore').splitlines()
                
                logging.info("clang-tidy over '{0}' completed.".format(filename))
                
                call_vim_rpc(True, filename, apply_fixes, output_lines)
                return True, None 
                
            except subprocess.CalledProcessError as e:
                output_lines = e.output.decode('utf-8', errors='ignore').splitlines()
                call_vim_rpc(True, filename, apply_fixes, output_lines)
                return True, None
            except Exception as e:
                logging.error(f"Clang-Tidy execution failed: {e}")
                return False, None

        return False, None
