from __future__ import division
from __future__ import absolute_import
from builtins import zip
from builtins import str
from past.utils import old_div
from builtins import object
import linecache
import logging
import multiprocessing
import os
import shlex
import subprocess
import time
import tempfile
from cxxd.parser.cxxd_config_parser import CxxdConfigParser
from cxxd.parser.clang_parser import ClangParser
from cxxd.parser.tunit_cache import TranslationUnitCache, NoCache
from cxxd.parser.ast_node_identifier import ASTNodeId
from cxxd.parser.clang_parser import ChildVisitResult
from . symbol_database import SymbolDatabase

# TODO move this to utils
import itertools
def slice_it(iterable, n, padvalue=None):
    return itertools.zip_longest(*[iter(iterable)]*n, fillvalue=padvalue)

class SourceCodeModelIndexerRequestId(object):
    RUN_ON_SINGLE_FILE        = 0x0
    RUN_ON_DIRECTORY          = 0x1
    DROP_SINGLE_FILE          = 0x2
    DROP_ALL                  = 0x3
    FIND_ALL_REFERENCES       = 0x10
    FETCH_ALL_DIAGNOSTICS     = 0x11

class ClangIndexer(object):
    supported_ast_node_ids = [
        ASTNodeId.getClassId(),           ASTNodeId.getStructId(),            ASTNodeId.getEnumId(),             ASTNodeId.getEnumValueId(), # handle user-defined types
        ASTNodeId.getUnionId(),           ASTNodeId.getTypedefId(),           ASTNodeId.getUsingDeclarationId(),
        ASTNodeId.getFunctionId(),        ASTNodeId.getMethodId(),                                                                           # handle functions and methods
        ASTNodeId.getLocalVariableId(),   ASTNodeId.getFunctionParameterId(), ASTNodeId.getFieldId(),                                        # handle local/function variables and member variables
        ASTNodeId.getMacroDefinitionId(), ASTNodeId.getMacroInstantiationId()                                                                # handle macros
    ]

    def __init__(self, parser, root_directory, cxxd_config_parser):
        self.cxxd_config_parser     = cxxd_config_parser
        self.root_directory         = root_directory
        self.symbol_db_name         = '.cxxd_index.db'
        self.symbol_db_path         = os.path.join(self.root_directory, self.symbol_db_name)
        self.symbol_db              = SymbolDatabase(self.symbol_db_path) if self.symbol_db_exists() else SymbolDatabase()
        self.parser                 = parser
        self.op = {
            SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE    : self.__run_on_single_file,
            SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY      : self.__run_on_directory,
            SourceCodeModelIndexerRequestId.DROP_SINGLE_FILE      : self.__drop_single_file,
            SourceCodeModelIndexerRequestId.DROP_ALL              : self.__drop_all,
            SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES   : self.__find_all_references,
            SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS : self.__fetch_all_diagnostics,
        }
        self.recognized_file_extensions = ['.cpp', '.cc', '.cxx', '.c', '.h', '.hh', '.hpp', 'hxx']
        self.extra_file_extensions = self.cxxd_config_parser.get_extra_file_extensions()
        self.blacklisted_directories = self.cxxd_config_parser.get_blacklisted_directories()

    def symbol_db_exists(self):
        return os.path.exists(self.symbol_db_path)

    def get_symbol_db(self):
        return self.symbol_db

    def symbol_db_schema_changed(self):
        if self.symbol_db_exists():
            self.symbol_db.open(self.symbol_db_path)
            current_major_number, current_minor_number = self.symbol_db.fetch_schema_version()
            if current_major_number != self.symbol_db.VERSION_MAJOR or current_minor_number != self.symbol_db.VERSION_MINOR:
                return True
        return False

    def __call__(self, args):
        return self.op.get(int(args[0]), self.__unknown_op)(int(args[0]), args[1:len(args)])

    def __unknown_op(self, id, args):
        logging.error("Unknown operation with ID={0} triggered! Valid operations are: {1}".format(id, self.op))
        return False, None

    def __run_on_single_file(self, id, args):
        success = False
        if self.symbol_db_exists():
            filename = str(args[0])
            if not CxxdConfigParser.is_file_blacklisted(self.blacklisted_directories, filename):
                self.symbol_db.open(self.symbol_db_path)
                self.symbol_db.delete_entry(remove_root_dir_from_filename(self.root_directory, filename))
                success = index_single_file(
                    self.parser,
                    self.root_directory,
                    filename,
                    self.symbol_db
                )
                    # TODO what if index_single_file() fails? we should revert the symbol_db.delete_entry() back
            else:
                logging.warning('Indexing will not take place on existing files whose contents were modified but not saved.')
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return success, None

    def __run_on_directory(self, id, args):
        if self.symbol_db_schema_changed():
            logging.warning('Detected symbol database schema change! About to drop the current one and re-create a new one ...')
            self.__drop_all(0, (True,))

        if not self.symbol_db_exists():
            logging.info("Starting to index whole directory '{0}' ... ".format(self.root_directory))

            # Establish the connection first and create an empty symbol database
            self.symbol_db.open(self.symbol_db_path)

            # When creating the symbol db for the first time we need to create a data model for it
            self.symbol_db.create_data_model()

            # Build-up a list of source code files from given project directory
            cpp_file_list = get_cpp_file_list(self.root_directory, self.blacklisted_directories, self.recognized_file_extensions + self.extra_file_extensions)

            indexing_subprocess_list = []
            symbol_db_list = []
            indexer_input_list = []

            # We will slice the input file list into a number of chunks which corresponds to the amount of available CPU cores
            how_many_chunks = old_div(len(cpp_file_list), multiprocessing.cpu_count())

            # Now we are able to parallelize the indexing operation across different CPU cores
            for cpp_file_list_chunk in slice_it(cpp_file_list, how_many_chunks):

                # Each subprocess will get a file containing source files to be indexed
                indexer_input_handle, indexer_input = create_indexer_input_list_file(self.root_directory, '.cxxd_idx_input', cpp_file_list_chunk)

                # Each subprocess will get an empty DB file to record indexing results into it
                symbol_db_handle, symbol_db = create_empty_symbol_db(self.root_directory, self.symbol_db_name)

                # Start indexing a given chunk in a new subprocess
                #   Note: Running and handling subprocesses as following, and not via multiprocessing.Process module,
                #         is done intentionally and more or less it served as a (very ugly) workaround because of several reasons:
                #           (1) 'libclang' is not made thread safe which is why we want to utilize it from different
                #               processes (e.g. each process will get its own instance of 'libclang')
                #           (2) Python bindings for 'libclang' implement some sort of module caching mechanism which basically
                #               contradicts with the intent from (1)
                #           (3) Point (2) seems to be a Pythonic way of implementing modules which basically obscures
                #               the way how different instances of libraries (modules?) across different processes
                #               should behave
                #           (4) Python does have a way to handle such situations (module reloading) but seems that it
                #               works only for the simplest cases which is unfortunally not the case here
                #           (5) Creating a new process via subprocess.Popen interface and running the indexing operation
                #               from another Python script ('clang_index.py') is the only way how I managed to get it
                #               working correctly (each process will get their own instance of library)
                indexing_subprocess = start_indexing_subprocess(
                    self.root_directory,
                    self.parser.get_compiler_args_db().filename(),
                    indexer_input,
                    symbol_db,
                    logging.getLoggerClass().root.handlers[0].baseFilename + '_' + str(len(indexing_subprocess_list)+1)
                )

                # Store handles to subprocesses and corresponding tmp files so we can handle them later on
                indexing_subprocess_list.append(indexing_subprocess)
                symbol_db_list.append(symbol_db)
                indexer_input_list.append(indexer_input)

            # Wait indexing subprocesses to finish with their work
            for indexing_subprocess in indexing_subprocess_list:
                indexing_subprocess.wait()

            # Merge the results of indexing operations into the single symbol database
            self.symbol_db.copy_all_entries_from(symbol_db_list)

            # Get rid of temporary symbol db's & indexer input list filenames
            for symbol_db, indexer_input in zip(symbol_db_list, indexer_input_list):
                os.remove(symbol_db)
                os.remove(indexer_input)

            # TODO how to count total CPU time, for all sub-processes?
            logging.info("Indexing {0} is completed.".format(self.root_directory))
        else:
            logging.info("Directory '{0}' already indexed ... ".format(self.root_directory))
        return True, None

    def __drop_single_file(self, id, args):
        symbol_db_exists = self.symbol_db_exists()
        if symbol_db_exists:
            filename = str(args[0])
            if not CxxdConfigParser.is_file_blacklisted(self.blacklisted_directories, filename):
                self.symbol_db.open(self.symbol_db_path)
                self.symbol_db.delete_entry(remove_root_dir_from_filename(self.root_directory, filename))
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return symbol_db_exists, None

    def __drop_all(self, id, args):
        symbol_db_exists = self.symbol_db_exists()
        if symbol_db_exists:
            delete_file_from_disk = bool(args[0])
            if delete_file_from_disk:
                self.symbol_db.close()
                os.remove(self.symbol_db.filename)
            else:
                self.symbol_db.open(self.symbol_db_path)
                self.symbol_db.delete_all_entries()
            logging.info('Indexer DB dropped.')
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return symbol_db_exists, None

    def __find_all_references(self, id, args):
        tunit, cursor, references = None, None, []
        if self.symbol_db_exists():
            tunit = self.parser.parse(str(args[0]), str(args[0]))
            cursor = self.parser.get_cursor(tunit, int(args[1]), int(args[2]))
            if cursor:
                # TODO In order to make find-all-references work on edited (and not yet saved) files,
                #      we would need to manipulate directly with USR.
                #      In case of edited files, USR contains a name of a temporary file we serialized
                #      the contents in and therefore will not match the USR in the database (which in
                #      contrast contains an original filename).
                usr = cursor.referenced.get_usr() if cursor.referenced else cursor.get_usr()
                self.symbol_db.open(self.symbol_db_path)
                for ref in self.symbol_db.fetch_symbols_by_usr(usr):
                    references.append([
                        os.path.join(self.root_directory, self.symbol_db.get_symbol_filename(ref)),
                        self.symbol_db.get_symbol_line(ref),
                        self.symbol_db.get_symbol_column(ref),
                        self.symbol_db.get_symbol_context(ref)
                    ])
                logging.info("Find-all-references operation completed for '{0}', [{1}, {2}], '{3}'".format(
                    cursor.displayname, cursor.location.line, cursor.location.column, tunit.spelling)
                )
            logging.debug("\n{0}".format('\n'.join(str(ref) for ref in references)))
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return tunit is not None and cursor is not None, references

    def __fetch_all_diagnostics(self, id, args):
        diagnostics = []
        db_exists = self.symbol_db_exists()
        if db_exists:
            self.symbol_db.open(self.symbol_db_path)
            for diag in self.symbol_db.fetch_all_diagnostics(int(args[0])):
                diagnostics.append([
                    os.path.join(self.root_directory, self.symbol_db.get_diagnostics_filename(diag)),
                    self.symbol_db.get_diagnostics_line(diag),
                    self.symbol_db.get_diagnostics_column(diag),
                    self.symbol_db.get_diagnostics_description(diag),
                    self.symbol_db.get_diagnostics_severity(diag)
                ])
                for detail in self.symbol_db.fetch_diagnostics_details(self.symbol_db.get_diagnostics_id(diag)):
                    diagnostics.append([
                        os.path.join(self.root_directory, self.symbol_db.get_diagnostics_details_filename(detail)),
                        self.symbol_db.get_diagnostics_details_line(detail),
                        self.symbol_db.get_diagnostics_details_column(detail),
                        self.symbol_db.get_diagnostics_details_description(detail),
                        self.symbol_db.get_diagnostics_details_severity(detail)
                    ])
            logging.debug("\n{0}".format('\n'.join(str(diag) for diag in diagnostics)))
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return db_exists, diagnostics


def index_file_list(root_directory, input_filename_list, compiler_args_filename, output_db_filename):
    symbol_db = SymbolDatabase(output_db_filename)
    symbol_db.create_data_model()
    clang_library_file = '/usr/lib64/llvm7.0/lib/libclang.so.7'
    import clang.cindex
    clang.cindex.Config.set_library_file(clang_library_file)
    parser = ClangParser(compiler_args_filename, TranslationUnitCache(NoCache()))
    with open(input_filename_list, 'r') as input_list:
        for filename in input_list.readlines():
            index_single_file(parser, root_directory, filename.strip(), symbol_db)
    symbol_db.close()

def indexer_visitor(ast_node, ast_parent_node, args):
    def extract_cursor_context(filename, line):
        return linecache.getline(filename, line)

    parser, symbol_db, root_directory = args
    ast_node_location = ast_node.location
    ast_node_tunit_spelling = ast_node.translation_unit.spelling
    ast_node_referenced = ast_node.referenced
    if ast_node_location and ast_node_location.file and ast_node_location.file.name == ast_node_tunit_spelling:  # we are not interested in symbols which got into this TU via includes
        id = parser.get_ast_node_id(ast_node)
        usr = ast_node_referenced.get_usr() if ast_node_referenced else ast_node.get_usr()
        line = int(parser.get_ast_node_line(ast_node))
        column = int(parser.get_ast_node_column(ast_node))
        if id in ClangIndexer.supported_ast_node_ids:
            symbol_db.insert_symbol_entry(
                remove_root_dir_from_filename(root_directory, ast_node_tunit_spelling),
                line,
                column,
                usr,
                extract_cursor_context(ast_node_tunit_spelling, line),
                ast_node_referenced._kind_id if ast_node_referenced else ast_node._kind_id,
                ast_node.is_definition()
            )
        return ChildVisitResult.RECURSE.value  # If we are positioned in TU of interest, then we'll traverse through all descendants
    return ChildVisitResult.CONTINUE.value  # Otherwise, we'll skip to the next sibling

def index_single_file(parser, root_directory, filename, symbol_db):
    logging.info("Indexing a file '{0}' ... ".format(filename))
    tunit = parser.parse(filename, filename)
    if tunit:
        parser.traverse(tunit.cursor, [parser, symbol_db, root_directory], indexer_visitor)
        store_tunit_diagnostics(tunit.diagnostics, symbol_db, root_directory)
        symbol_db.flush()
    logging.info("Indexing of {0} completed.".format(filename))
    return tunit is not None

def store_tunit_diagnostics(diagnostics, symbol_db, root_directory):
    for diag in diagnostics:
        diagnostics_id = None
        diag_location = diag.location
        if diag_location:
            diag_location_file = diag_location.file
            if diag_location_file:
                diagnostics_id = symbol_db.insert_diagnostics_entry(
                    remove_root_dir_from_filename(root_directory, diag_location_file.name),
                    diag_location.line,
                    diag_location.column,
                    diag.spelling,
                    diag.severity
                )
                if diagnostics_id is not None:
                    # Now do the same for children ...
                    for child_diagnostics in diag.children:
                        diag_location = child_diagnostics.location
                        if diag_location:
                            diag_location_file = diag_location.file
                            if diag_location_file:
                                symbol_db.insert_diagnostics_details_entry(
                                    diagnostics_id,
                                    remove_root_dir_from_filename(root_directory, diag_location_file.name),
                                    diag_location.line,
                                    diag_location.column,
                                    child_diagnostics.spelling,
                                    child_diagnostics.severity
                                )

def remove_root_dir_from_filename(root_dir, full_path):
    return full_path[len(root_dir):].lstrip(os.sep)

def get_clang_index_path():
    this_script_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(this_script_directory, 'clang_index.py')

def get_cpp_file_list(root_directory, blacklisted_directories, recognized_file_extensions):
    cpp_file_list = []
    for dirpath, dirs, files in os.walk(root_directory):
        for filename in files:
            name, extension = os.path.splitext(filename)
            if extension in recognized_file_extensions:
                if not CxxdConfigParser.is_file_blacklisted(blacklisted_directories, filename):
                    cpp_file_list.append(os.path.join(dirpath, filename))
    return cpp_file_list

def create_indexer_input_list_file(directory, with_prefix, cpp_file_list_chunk):
    chunk_with_no_none_items = '\n'.join(item for item in cpp_file_list_chunk if item)
    cpp_file_list_handle, cpp_file_list = tempfile.mkstemp(prefix=with_prefix, dir=directory)
    os.write(cpp_file_list_handle, chunk_with_no_none_items)
    return cpp_file_list_handle, cpp_file_list

def create_empty_symbol_db(directory, with_prefix):
    symbol_db_handle, symbol_db = tempfile.mkstemp(prefix=with_prefix, dir=directory)
    return symbol_db_handle, symbol_db

def start_indexing_subprocess(root_directory, compiler_args_filename, indexer_input_list_filename, output_db_filename, log_filename):
    cmd = "python2 " + get_clang_index_path() + \
            " --project_root_directory='" + root_directory + \
            "' --compiler_args_filename='" + compiler_args_filename + \
            "' --input_list='" + indexer_input_list_filename + \
            "' --output_db_filename='" + output_db_filename + \
            "' " + "--log_file='" + log_filename + "'"
    return subprocess.Popen(shlex.split(cmd))
