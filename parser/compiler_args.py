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

            def eat_minus_minus_path_to_file(json_comp_db_command):
                # From version XYZ (?) clang_getCompileCommands started to output "faked" compilation database commands
                # for header files. This is different than what has been before when it would simply return null
                # for all files which are not translation units (headers are not) and hence not part of the
                # compile_commands.json
                #
                # "Faked" output contains '-- /path/to/header/file' part and this interferes with
                # clang_parseTranslationUnit which will fail with 'invalid arguments' error.
                #
                # Also, the same "faked" output clang_getCompileCommands will be returned for non-header files, so
                # translation units, that are not part of the compilation database. This is a very valid use-case
                # possible to run into if a new .cxx file is created but is not yet part of the compilation
                # database. This happens either when a CMakeLists.txt entry has not been added yet and/or CMake
                # build config has not been yet regenerated with a new file.
                #
                # This function fixes this interferance with improperly parsing these units by removing
                # the '-- <path>' part.
                try:
                    o_idx = json_comp_db_command.index('--')
                    json_comp_db_command.pop(o_idx)
                    json_comp_db_command.pop(o_idx)
                except ValueError:
                    pass
                return json_comp_db_command

            def eat_conflicting_language_args(json_comp_db_command):
                # We force '-x c++' at the beginning, so we must remove conflicting language specifications
                # that might appear later in the command line (e.g. 'c++-header' or 'c++' dangling from a stripped -x)
                new_args = []
                skip_next = False
                for i, arg in enumerate(json_comp_db_command):
                    if skip_next:
                        skip_next = False
                        continue
                    if arg == '-x':
                        if i + 1 < len(json_comp_db_command) and json_comp_db_command[i+1] in ('c++', 'c++-header', 'c', 'c-header'):
                            skip_next = True
                            continue
                    if arg in ('-xc++', '-xc++-header', '-xc', '-xc-header'):
                        continue
                    if arg in ('c++', 'c++-header', 'c', 'c-header'):
                        continue
                    new_args.append(arg)
                return new_args

            def eat_conflicting_input_file(json_comp_db_command, filename):
                # If the source filename itself is present in the arguments (e.g. gcc file.c ...),
                # libclang will be confused because we pass the filename separately to parse().
                # We need to remove it from the args list. We check for exact match or basename match or abspath match.
                abs_filename = os.path.abspath(filename)
                basename = os.path.basename(filename)

                def is_match(arg):
                    arg_str = str(arg)
                    if arg_str == filename or arg_str == basename:
                        return True
                    # If arg looks like a path and resolves to same file
                    if '/' in arg_str or '\\' in arg_str:
                         try:
                             if os.path.abspath(arg_str) == abs_filename:
                                 return True
                         except:
                             pass
                    return False

                return [arg for arg in json_comp_db_command if not is_match(arg)]

            def eat_unsupported_flags_and_transform_relative_into_absolute_paths(json_comp_db_command, working_directory):
                # Even though compile_commands.json documentation says that paths used in (compiler) arguments
                # can be relative, it seems like it doesn't work in practice so we have to transform all of such
                # paths.
                logging.debug('compile cmd before: {}'.format(json_comp_db_command))
                for idx in range(len(json_comp_db_command)):
                    if json_comp_db_command[idx] in ['-I', '-iquote', '-isystem']:
                        json_comp_db_command[idx+1] = os.path.join(working_directory, json_comp_db_command[idx+1])
                    elif json_comp_db_command[idx].startswith('-Ibazel'):
                        json_comp_db_command[idx] = '-I' + os.path.join(working_directory, json_comp_db_command[idx][2:])
                    elif json_comp_db_command[idx].startswith('bazel-out'):
                        json_comp_db_command[idx] = os.path.join(working_directory, json_comp_db_command[idx])
                    elif json_comp_db_command[idx].startswith('--sysroot=external'):
                        json_comp_db_command[idx] = '--sysroot=' + os.path.join(working_directory, json_comp_db_command[idx][10:])
                    elif json_comp_db_command[idx] in ['-fno-canonical-system-headers', '-Wformat-truncation', '-Wformat-truncation=1', '-Wformat-truncation=2']:
                        json_comp_db_command[idx] = ''
                logging.debug('compile cmd after: {}'.format(json_comp_db_command))
                return json_comp_db_command

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
                if s[1].startswith('h') or s[1] == 'i':
                    # extension is some variation of .h, .hpp, .hxx, etc. OR .i (preprocessed/inline include)
                    return True 
                return False

            def extract_compiler_args(compile_cmd, is_header):
                args = []
                if compile_cmd:
                    try:
                        cmd = compile_cmd[0]
                    except Exception as e:
                         logging.debug(f"CompilerArgs: Failed to inspect cmd: {e}")

                    for arg in compile_cmd[0].arguments:
                        args.append(arg)

                    try:
                         # Propagate working directory if available.
                         # This is critical for build systems like Bazel where includes are relative to execution root.
                         if compile_cmd[0].directory:
                             args.append('-working-directory')
                             args.append(compile_cmd[0].directory)
                    except Exception:
                         pass
                    # Since some version of libclang, handling for files not part of the compilation database
                    # (e.g. headers and TUs not yet part of the build system) has been changed and now we have
                    # to special-case it here with eat_minus_minus_path_to_file. Furthermore, headers need more
                    # special care because compiler flag options are not the same as for the TUs.
                    if is_header:
                        args = self.default_compiler_args + eat_unsupported_flags_and_transform_relative_into_absolute_paths(eat_conflicting_language_args(eat_compiler_invocation(eat_minus_minus_path_to_file(eat_minus_o_compiler_option(eat_minus_c_compiler_option(args))))), compile_cmd[0].directory)
                    else:
                        args = self.default_compiler_args + eat_unsupported_flags_and_transform_relative_into_absolute_paths(eat_conflicting_language_args(eat_compiler_invocation(eat_minus_minus_path_to_file(eat_minus_o_compiler_option(eat_minus_c_compiler_option(args))))), compile_cmd[0].directory)
                    # Finally, remove the input filename itself if it appears in args
                    # For headers, the filename in args might be the TU that included it (if we borrowed args), or the header itself.
                    # For TUs, it's the TU itself.
                    # We pass 'filename' assuming it matches what's in the args (which comes from compile_commands.json entry)
                    args = eat_conflicting_input_file(args, compile_cmd[0].filename if compile_cmd else filename)
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
            logging.debug(compiler_args)
            return compiler_args

        def get_working_dir(self, filename):
            compile_cmd = self.database.getCompileCommands(filename)
            if compile_cmd and compile_cmd[0].directory:
                return compile_cmd[0].directory
            return ""

    class CompileFlagsCompilationDatabase():
        def __init__(self, default_compiler_args, filename):
            self.working_directory = os.path.dirname(filename)
            self.root_project_directory = ['-working-directory=' + self.working_directory] # TODO this assumes that compile_flags.txt is in the root project directory
            self.compiler_args = self.root_project_directory + default_compiler_args + [line.rstrip('\n') for line in open(filename)]

        def get(self, filename):
            return self.compiler_args

        def get_working_dir(self, filename):
            return self.working_directory

    class FallbackCompilationDatabase():
        def __init__(self, default_compiler_args):
            self.default_compiler_args = default_compiler_args

        def get(self, filename):
            return self.default_compiler_args

        def get_working_dir(self, filename):
            return None # Not supported

    def __init__(self, compiler_args_filename):
        self.database = None
        self.database_filename = None
        self.default_compiler_args = ['-x', 'c++'] + get_system_includes()
        self.set(compiler_args_filename)
        logging.info('Compiler args filename = {0}. Default compiler args = {1}'.format(compiler_args_filename, self.default_compiler_args))

    def filename(self):
        return self.database_filename

    def working_directory(self, source_code_filename):
        return self.database.get_working_dir(source_code_filename)

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

    def transform_to_edited_file_form(self, source_code_filename, in_compiler_args):

        # For edited files, we need to append additional include path to the compiler args which points to the parent directory of current buffer.
        #   * This needs to be done because we will be doing analysis on temporary file which is located outside the project
        #     directory. By doing this, we might invalidate header includes for that particular file and therefore trigger
        #     unnecessary Clang parsing errors.
        #   * An alternative would be to generate tmp files in original location but that would pollute project directory and
        #     potentially would not play well with other tools (indexer, version control, etc.).

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

        index = 0
        out_compiler_args = list(in_compiler_args) # make a copy; we don't want to keep modifying the original compiler args
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
