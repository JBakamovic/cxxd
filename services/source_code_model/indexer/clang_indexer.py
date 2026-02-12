import linecache
import logging
import math
import multiprocessing
import os
import select
import shlex
import subprocess
import sys
import time
import tempfile
from cxxd.parser.cxxd_config_parser import CxxdConfigParser
from cxxd.parser.clang_parser import ClangParser
from cxxd.parser.tunit_cache import TranslationUnitCache, NoCache
from cxxd.parser.ast_node_identifier import ASTNodeId
from cxxd.parser.clang_parser import ChildVisitResult
from cxxd.services.source_code_model.indexer.symbol_database import SymbolDatabase

# TODO move this to utils
import itertools
def slice_it(iterable, n, padvalue=None):
    return itertools.zip_longest(*[iter(iterable)]*n, fillvalue=padvalue)

class SourceCodeModelIndexerRequestId():
    RUN_ON_SINGLE_FILE        = 0x0
    RUN_ON_DIRECTORY          = 0x1
    DROP_SINGLE_FILE          = 0x2
    DROP_ALL                  = 0x3
    FIND_ALL_REFERENCES       = 0x10
    FETCH_ALL_DIAGNOSTICS     = 0x11
    FETCH_ALL_DEFINITIONS     = 0x12

class ClangIndexer():
    supported_ast_node_ids = [
        ASTNodeId.getClassId(),           ASTNodeId.getStructId(),            ASTNodeId.getEnumId(),             ASTNodeId.getEnumValueId(), # handle user-defined types
        ASTNodeId.getUnionId(),           ASTNodeId.getTypedefId(),           ASTNodeId.getUsingDeclarationId(),
        ASTNodeId.getFunctionId(),        ASTNodeId.getMethodId(),                                                                           # handle functions and methods
        ASTNodeId.getFieldId(),                                                                                                              # handle member variables
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
            SourceCodeModelIndexerRequestId.FETCH_ALL_DEFINITIONS : self.__fetch_all_definitions,
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

            # Load Balancing: Dynamic Work Stealing Scheduler
            num_cores = multiprocessing.cpu_count()
            logging.info(f"Starting Dynamic Load Balancing with {num_cores} workers for {len(cpp_file_list)} files.")

            # Start N interactive workers
            workers = []
            symbol_db_list = []

            for worker_id in range(num_cores):
                # Create per-worker DB
                symbol_db_handle, symbol_db = create_empty_symbol_db(self.root_directory, self.symbol_db_name)
                os.close(symbol_db_handle)
                symbol_db_list.append(symbol_db)

                # Start worker
                proc = start_indexing_subprocess(
                    self.root_directory,
                    self.parser.get_compiler_args_db().filename(),
                    symbol_db,
                    logging.getLoggerClass().root.handlers[0].baseFilename,
                    worker_id + 1
                )
                workers.append(proc)

            # Scheduler State
            # Optimization: Sort files by size (descending) so largest files are processed first.
            logging.info("Sorting files by size to optimize schedule...")
            cpp_file_list.sort(key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0, reverse=True)

            pending_files = list(cpp_file_list) # Copy list
            active_workers = list(workers)      # Workers currently running
            idle_workers = list(workers)        # Workers ready for work

            # Debug: Track what each worker is doing
            worker_state = {} # worker_proc -> {'file': str, 'start_time': float}
            completed_files = 0

            # Helper to send work
            def send_work(worker, filename):
                try:
                    # Write bytes to unbuffered stdin
                    worker.stdin.write((filename + "\n").encode('utf-8'))
                    worker.stdin.flush()
                    worker_state[worker] = {'file': filename, 'start_time': time.time()}
                    logging.debug(f"Master: Sent {filename} to Worker {worker.args}")
                    return True
                except (BrokenPipeError, IOError):
                    logging.error(f"Worker {worker.args} died unexpectedly.")
                    if worker in worker_state:
                         del worker_state[worker]
                    return False

            # Initial Fill: Give one file to each worker
            while idle_workers and pending_files:
                worker = idle_workers.pop(0)
                file_to_process = pending_files.pop(0)
                if not send_work(worker, file_to_process):
                    active_workers.remove(worker)

            # Event Loop
            # We monitor stdout of all active workers to see who finishes
            logging.info("Master: Starting scheduler event loop")
            while active_workers and (pending_files or len(idle_workers) < len(active_workers) or worker_state):
                # Wait for any worker to say "DONE"
                readable_pipes = [w.stdout for w in active_workers if w.stdout]
                if not readable_pipes:
                    break

                # Timeout of 10s to log status if stuck
                ready, _, _ = select.select(readable_pipes, [], [], 10.0)

                if not ready:
                    # Timeout! Log potentially stuck workers
                    logging.warning(f"Master: Watchdog - Waiting for {len(active_workers)} workers. Pending files: {len(pending_files)}")
                    now = time.time()
                    for w, state in worker_state.items():
                        elapsed = now - state['start_time']
                        if elapsed > 30.0:
                            logging.warning(f"  STUCK? Worker {w.args} parsing {state['file']} for {elapsed:.1f}s")
                    continue

                for stdout in ready:
                    # Find which worker this is
                    # (Slow linear search but N is small, <64 typically)
                    worker = next((w for w in active_workers if w.stdout == stdout), None)
                    if not worker:
                        continue

                    # Read the "DONE" message (binary)
                    line = worker.stdout.readline()
                    if not line: # EOF means worker died
                        logging.warning(f"Master: Worker {worker.args} disconnected (EOF).")
                        active_workers.remove(worker)
                        if worker in worker_state:
                             del worker_state[worker]
                        continue

                    # Worker finished a file
                    if worker in worker_state:
                        # elapsed = time.time() - worker_state[worker]['start_time']
                        # logging.debug(f"Worker {worker.args} finished {worker_state[worker]['file']} in {elapsed:.2f}s")
                        del worker_state[worker]

                    completed_files += 1

                    # assign next or mark idle
                    if pending_files:
                        next_file = pending_files.pop(0)
                        if not send_work(worker, next_file):
                            active_workers.remove(worker)
                    else:
                        # No more work, remove from active set
                        active_workers.remove(worker)
                        # Close stdin to signal worker to exit gracefully
                        try:
                            worker.stdin.close()
                        except:
                            pass
                        pass

            # Work is done, shutdown all workers
            for w in workers:
                try:
                    if w.stdin:
                        w.stdin.close() # Sends EOF, worker loop breaks
                except:
                    pass
                w.wait() # Wait for clean exit

            logging.info("Indexing completed.")
            # Merge the results of indexing operations into the single symbol database
            self.symbol_db.copy_all_entries_from(symbol_db_list)

            # Get rid of temporary symbol db's
            for symbol_db in symbol_db_list:
                try:
                    os.remove(symbol_db)
                except OSError:
                    pass

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

    def __fetch_all_definitions(self, id, args):
        # Determine output file path
        if args and len(args) > 0:
            output_file_path = args[0]
        else:
            fd, output_file_path = tempfile.mkstemp(prefix='cxxd_definitions_', suffix='.txt', text=True)
            os.close(fd)

        db_exists = self.symbol_db_exists()
        if db_exists:
            self.symbol_db.open(self.symbol_db_path)
            try:
                count = 0
                # 128KB - buffer writes to minimize syscalls - nr. of symbols will be potentially large
                with open(output_file_path, 'w', buffering=128*1024) as f:
                    for relative_filename, line, column, context in self.symbol_db.fetch_all_definitions_raw():
                        # In the DB, 'filename' is relative. Construct absolute.
                        abs_filename = os.path.join(self.root_directory, relative_filename)
                        text = context.strip() if context else ''
                        f.write(f"{text}\t{abs_filename}:{line}:{column}\n")
                        count += 1
                logging.info(f"__fetch_all_definitions streamed {count} definitions to {output_file_path}")
                return True, [output_file_path] 
            except Exception as e:
                logging.error(f"Error streaming definitions: {e}")
                return False, None
        else:
            logging.error('Action cannot be run if symbol database does not exist yet!')
        return db_exists, None

def index_interactive(root_directory, compiler_args_filename, output_db_filename, worker_id):
    symbol_db = SymbolDatabase(output_db_filename)
    symbol_db.create_data_model()
    cxxd_config_parser = CxxdConfigParser(os.path.join(root_directory, '.cxxd_config.json'), root_directory)
    parser = ClangParser(compiler_args_filename, TranslationUnitCache(NoCache()), cxxd_config_parser.get_clang_library_file())

    worker_prefix = f"[Worker {worker_id}] " if worker_id else ""
    logging.info(f"{worker_prefix}Interactive worker started.")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            # Simple protocol: just filename
            filename = line.strip()
            if not filename:
                continue

            logging.info(f"{worker_prefix}Indexing: {filename}")
            index_single_file(parser, root_directory, filename, symbol_db)

            # Signal completion to master
            print("DONE", flush=True)

        except Exception as e:
            logging.error(f"{worker_prefix}Error in interactive loop: {e}")
            # Even on error, signal done so master doesn't hang (maybe with error code?)
            # For now, just DONE to keep going.
            print("DONE", flush=True)
    symbol_db.close()
    logging.info(f"{worker_prefix}Interactive worker finished.")

def indexer_visitor(ast_node, ast_parent_node, args):
    def extract_cursor_context(filename, line):
        return linecache.getline(filename, line)

    parser, symbol_db, root_directory, symbol_batch = args
    ast_node_location = ast_node.location
    ast_node_tunit_spelling = ast_node.translation_unit.spelling
    ast_node_referenced = ast_node.referenced
    if ast_node_location and ast_node_location.file and ast_node_location.file.name == ast_node_tunit_spelling:  # we are not interested in symbols which got into this TU via includes
        id = parser.get_ast_node_id(ast_node)
        usr = ast_node_referenced.get_usr() if ast_node_referenced else ast_node.get_usr()
        line = int(parser.get_ast_node_line(ast_node))
        column = int(parser.get_ast_node_column(ast_node))
        if id in ClangIndexer.supported_ast_node_ids:
            symbol_batch.append((
                remove_root_dir_from_filename(root_directory, ast_node_tunit_spelling),
                line,
                column,
                usr,
                extract_cursor_context(ast_node_tunit_spelling, line),
                ast_node_referenced._kind_id if ast_node_referenced else ast_node._kind_id,
                ast_node.is_definition()
            ))
        return ChildVisitResult.RECURSE.value  # If we are positioned in TU of interest, then we'll traverse through all descendants
    return ChildVisitResult.CONTINUE.value  # Otherwise, we'll skip to the next sibling

def index_single_file(parser, root_directory, filename, symbol_db):
    logging.debug("Indexing a file '{0}' ... ".format(filename))
    tunit = parser.parse(filename, filename)
    if tunit:
        symbol_batch = []
        parser.traverse(tunit.cursor, [parser, symbol_db, root_directory, symbol_batch], indexer_visitor)
        if symbol_batch:
            symbol_db.insert_symbol_entries_batch(symbol_batch)
        store_tunit_diagnostics(tunit.diagnostics, symbol_db, root_directory)
        symbol_db.flush()
    logging.debug("Indexing of {0} completed.".format(filename))
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
        # Prune blacklisted directories from traversal
        dirs[:] = [d for d in dirs if not CxxdConfigParser.is_file_blacklisted(blacklisted_directories, os.path.join(dirpath, d))]
        for filename in files:
            name, extension = os.path.splitext(filename)
            if extension in recognized_file_extensions:
                full_path = os.path.join(dirpath, filename)
                if not CxxdConfigParser.is_file_blacklisted(blacklisted_directories, full_path):
                    cpp_file_list.append(full_path)
    return cpp_file_list

def create_indexer_input_list_file(directory, with_prefix, cpp_file_list_chunk):
    chunk_with_no_none_items = '\n'.join(item for item in cpp_file_list_chunk if item)
    cpp_file_list_handle, cpp_file_list = tempfile.mkstemp(prefix=with_prefix, dir=directory)
    os.write(cpp_file_list_handle, chunk_with_no_none_items.encode("utf-8"))
    return cpp_file_list_handle, cpp_file_list

def create_empty_symbol_db(directory, with_prefix):
    symbol_db_handle, symbol_db = tempfile.mkstemp(prefix=with_prefix, dir=directory)
    return symbol_db_handle, symbol_db

def start_indexing_subprocess(root_directory, compiler_args_filename, output_db_filename, log_filename, worker_id):
    cmd_args = [
        "python3", get_clang_index_path(),
        "--project_root_directory", root_directory,
        "--compiler_args_filename", compiler_args_filename,
        "--output_db_filename", output_db_filename,
        "--log_file", log_filename,
        "--worker_id", str(worker_id)
    ]
    # Use unbuffered binary mode to avoid select() deadlock with TextIOWrapper buffers
    return subprocess.Popen(cmd_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
