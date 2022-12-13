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
                # Get rid of the '-c <source_code_filename>' part
                try:
                    c_idx = json_comp_db_command.index('-c')
                    json_comp_db_command.pop(c_idx)
                    json_comp_db_command.pop(c_idx)
                except ValueError:
                    pass
                return json_comp_db_command

            def eat_minus_o_compiler_option(json_comp_db_command):
                # Get rid of the '-o <object_file>' part
                try:
                    o_idx = json_comp_db_command.index('-o')
                    json_comp_db_command.pop(o_idx)
                    json_comp_db_command.pop(o_idx)
                except ValueError:
                    pass
                return json_comp_db_command

            def eat_compiler_invocation(json_comp_db_command):
                # Get rid of the '<compiler_invocation>' part. It's always the first one.
                return json_comp_db_command[1:len(json_comp_db_command)]

            def eat_getCompileCommands_header_file_part(json_comp_db_command):
                # From version XYZ (?) clang_getCompileCommands started to output "faked" compilation database commands
                # for header files. This is different than what has been before when it would simply return null
                # for all files which are not translation units (headers are not) and hence not part of the
                # compile_commands.json
                #
                # "Faked" output contains '-- /path/to/header/file' part and this interferes with
                # clang_parseTranslationUnit which will fail with 'invalid arguments' error.
                #
                # Getting rid of that part seems to fix the issue and headers again can be successfully parsed.
                # It's always the last two args in the sequence.
                return json_comp_db_command[0:len(json_comp_db_command)-2]

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

            def is_header_file(filename):
                s = filename.split('.')
                if len(s) == 1:
                    return True # some headers don't have an extension, e.g. vector
                if s[1].startswith('h'):
                    return True # extension is some variation of .h, .hpp, .hxx, etc.
                return False

            def extract_compiler_args(compile_cmd, is_header):
                args = []
                if compile_cmd:
                    for arg in compile_cmd[0].arguments:
                        args.append(arg)
                    # Since some version of libclang, handling for header files has been changed and now we have to special-case it here
                    if is_header:
                        args = self.default_compiler_args + eat_compiler_invocation(eat_getCompileCommands_header_file_part(args))
                    else:
                        args = self.default_compiler_args + eat_compiler_invocation(eat_minus_o_compiler_option(eat_minus_c_compiler_option(args)))
                return list(args)

            compiler_args = extract_compiler_args(self.database.getCompileCommands(filename), is_header_file(filename))
            if compiler_args:
                cache_compiler_args(compiler_args)
            else:                                                   # 'filename' entry doesn't exist in JSON database (i.e. header file)
                if self.cached_compiler_args:                       # use cached compiler args if available
                    compiler_args = list(self.cached_compiler_args)
                else:                                               # otherwise use the compiler arguments from the very first entry in the JSON database (assuming that similar flags if not the same will be valid)
                    compiler_args = extract_compiler_args(self.database.getAllCompileCommands(), is_header_file(filename))
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

    def get(self, source_code_filename, source_code_is_modified):
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

        compiler_args = list(self.database.get(source_code_filename)) # make a copy; we don't want to keep modifying the original compiler args
        if source_code_is_modified:
            # Append additional include path to the compiler args which points to the parent directory of current buffer.
            #   * This needs to be done because we will be doing analysis on temporary file which is located outside the project
            #     directory. By doing this, we might invalidate header includes for that particular file and therefore trigger
            #     unnecessary Clang parsing errors.
            #   * An alternative would be to generate tmp files in original location but that would pollute project directory and
            #     potentially would not play well with other tools (indexer, version control, etc.).
            index = 0
            last_include_index = find_last_occurence_of_minus_i_compiler_option(compiler_args)
            if last_include_index is not None:
                index = last_include_index
            compiler_args.insert(index, '-I' + os.path.dirname(source_code_filename))
        logging.info('Compiler args = ' + str(compiler_args))
        return compiler_args

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
