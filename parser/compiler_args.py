import clang.cindex
import logging
import os
import sys

class CompilerArgs():
    class JSONCompilationDatabase():
        def __init__(self, default_compiler_args, filename):
            self.default_compiler_args = default_compiler_args
            self.cached_compiler_args = []
            try:
                self.database = clang.cindex.CompilationDatabase.fromDirectory(os.path.dirname(filename))
            except:
                logging.error(sys.exc_info())

        def get(self, filename):
            def eat_minus_c_compiler_option(json_comp_db_command):
                return json_comp_db_command[0:len(json_comp_db_command)-2] # -c <source_code_filename>

            def eat_minus_o_compiler_option(json_comp_db_command):
                return json_comp_db_command[0:len(json_comp_db_command)-2] # -o <object_file>

            def eat_compiler_invocation(json_comp_db_command):
                return json_comp_db_command[1:len(json_comp_db_command)]   # i.e. /usr/bin/c++

            def cache_compiler_args(args_list):
                # JSON compilation database ('compile_commands.json'):
                #   1. Will include information about translation units only (.cxx)
                #   2. Will NOT include information about header files
                #
                # That is the reason why we have to cache existing compiler
                # arguments (i.e. the ones from translation units existing
                # in JSON database) and apply them equally to any other file
                # which does not exist in JSON database (i.e. header file).
                #
                # This approach will obviously not going to work if there
                # are no translation units in the database at all. I.e. think
                # of header-only libraries.
                self.cached_compiler_args = list(args_list) # most simplest is to create a copy of current ones

            def extract_compiler_args(compile_cmd):
                args = []
                if compile_cmd:
                    for arg in compile_cmd[0].arguments:
                        args.append(arg)
                    args = self.default_compiler_args + eat_compiler_invocation(eat_minus_o_compiler_option(eat_minus_c_compiler_option(args)))
                return list(args)

            compiler_args = extract_compiler_args(self.database.getCompileCommands(filename))
            if compiler_args:
                cache_compiler_args(compiler_args)
            else:                                                   # 'filename' entry doesn't exist in JSON database (i.e. header file)
                if self.cached_compiler_args:                       # use cached compiler args if available
                    compiler_args = list(self.cached_compiler_args)
                else:                                               # otherwise use the compiler arguments from the very first entry in the JSON database (assuming that similar flags if not the same will be valid)
                    compiler_args = extract_compiler_args(self.database.getAllCompileCommands())
                    if compiler_args:
                        cache_compiler_args(compiler_args)
                    else:                                           # if that also failed (i.e. no entries in the JSON db; header-only libs), use default compiler args
                        compiler_args = list(self.default_compiler_args)
            return compiler_args

    class CompileFlagsCompilationDatabase():
        def __init__(self, default_compiler_args, filename):
            self.root_project_directory = ['-working-directory=' + os.path.dirname(filename)] # TODO this assumes that compile_flags.txt is in the root project directory
            self.compiler_args = self.root_project_directory + default_compiler_args + [line.rstrip('\n') for line in open(filename)]

        def get(self, filename):
            return self.compiler_args

    class FallbackCompilationDatabase():
        def __init__(self, default_compiler_args):
            self.default_compiler_args = default_compiler_args

        def get(self, filename):
            return self.default_compiler_args

    def __init__(self, compiler_args_filename):
        self.database = None
        self.database_filename = None
        self.default_compiler_args = ['-x', 'c++'] + get_system_includes()
        self.set(compiler_args_filename)
        logging.info('Compiler args filename = {0}. Default compiler args = {1}'.format(compiler_args_filename, self.default_compiler_args))

    def filename(self):
        return self.database_filename

    def set(self, compiler_args_filename):
        self.database_filename = compiler_args_filename
        if self.is_json_database(compiler_args_filename):
            self.database = self.JSONCompilationDatabase(self.default_compiler_args, compiler_args_filename)
        elif self.is_compile_flags_database(compiler_args_filename):
            self.database = self.CompileFlagsCompilationDatabase(self.default_compiler_args, compiler_args_filename)
        else:
            self.database = self.FallbackCompilationDatabase(self.default_compiler_args)
            logging.error("Unsupported way of providing compiler args: '{0}'. Parsing capabilities will be very limited or NOT functional at all!".format(compiler_args_filename))

    def get(self, source_code_filename):
        return list(self.database.get(source_code_filename)) # make a copy; we don't want to keep modifying the original compiler args

    def prepare_for_modified_files(self, source_code_filename, in_compiler_args):
        def find_first_occurence_of_minus_i_compiler_option(compiler_args):
            for index, arg in enumerate(compiler_args):
                if str(arg).startswith('-I'):
                    return index
            return None

        def find_last_occurence_of_minus_i_compiler_option(compiler_args):
            for index, arg in enumerate(reversed(compiler_args)):
                if str(arg).startswith('-I'):
                    return len(compiler_args) - index
            return None

        out_compiler_args = list(in_compiler_args) # make a copy; we don't want to keep modifying the original compiler args
        # Append additional include path to the compiler args which points to the parent directory of current buffer.
        #   * This needs to be done because we will be doing analysis on temporary file which is located outside the project
        #     directory. By doing this, we might invalidate header includes for that particular file and therefore trigger
        #     unnecessary Clang parsing errors.
        #   * An alternative would be to generate tmp files in original location but that would pollute project directory and
        #     potentially would not play well with other tools (indexer, version control, etc.).
        index = 0
        last_include_index = find_last_occurence_of_minus_i_compiler_option(in_compiler_args)
        if last_include_index is not None:
            index = last_include_index
        out_compiler_args.insert(index, '-I' + os.path.dirname(source_code_filename))
        return out_compiler_args

    def is_json_database(self, compiler_args_filename):
        return os.path.basename(compiler_args_filename) == 'compile_commands.json'

    def is_compile_flags_database(self, compiler_args_filename):
        return os.path.basename(compiler_args_filename) == 'compile_flags.txt'

def get_system_includes():
    import os.path
    gcc_includes = extract_system_includes_from('g++')
    clang_includes = extract_system_includes_from('clang++')
    gcc_normalized_includes = [os.path.normpath(include) for include in gcc_includes]
    clang_normalized_includes = [os.path.normpath(include) for include in clang_includes]
    merged_includes = set(gcc_normalized_includes + clang_normalized_includes)
    return list(merged_includes)

def extract_system_includes_from(compiler_name, pattern = ["\\n#include <...> search starts here:\\n", "\\nEnd of search list.\\n"]):
    import subprocess
    import distutils.spawn
    if not distutils.spawn.find_executable(compiler_name):
        logging.warning('\'{0}\' not available on this system. System include paths may not be set fully which will probably result in parsing issues.'.format(compiler_name))
        return []
    output = subprocess.Popen([compiler_name, "-v", "-E", "-x", "c++", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    output = str(output)
    return output[output.find(pattern[0]) + len(pattern[0]) : output.find(pattern[1])].replace(' ', '-I').split('\\n')
