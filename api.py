from server import ServiceId
from server import ServerRequestId
from services.source_code_model_service import SourceCodeModelSubServiceId
from services.source_code_model.indexer.clang_indexer import SourceCodeModelIndexerRequestId

#
# Server API
#
def server_start(get_server_instance, get_server_instance_args, project_root_directory, log_file):
    import logging
    import multiprocessing
    import sys

    def __run_impl(handle, get_server_instance, args, project_root_directory, log_file):
        def __handle_exception(exc_type, exc_value, exc_traceback):
            logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        def __catch_unhandled_exceptions():
            # This is what usually should be enough
            sys.excepthook = __handle_exception

            # But sys.excepthook does not work anymore within multi-threaded/multi-process environment (see https://bugs.python.org/issue1230540)
            # So what we can do is to override the Service.listen() implementation so it includes try-catch block with exceptions
            # being forwarded to the sys.excepthook function.
            from service import service_listener
            run_original = service_listener
            def listen(self):
                try:
                    run_original(self)
                except:
                    sys.excepthook(*sys.exc_info())
            service_listener = listen

        # Logger setup
        FORMAT = '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(filename)s:%(lineno)s] %(funcName)25s(): %(message)s'
        logging.basicConfig(filename=log_file, filemode='w', format=FORMAT, datefmt='%H:%M:%S', level=logging.INFO)
        logging.info('Starting a server for {0}'.format(project_root_directory))

        # Setup catching unhandled exceptions
        __catch_unhandled_exceptions()

        # Instantiate and run the server
        try:
            from server import server_listener
            server_listener(get_server_instance(handle, project_root_directory, args))
        except:
            sys.excepthook(*sys.exc_info())

    server_queue = multiprocessing.Queue()
    server_process = multiprocessing.Process(
        target=__run_impl,
        args=(
            server_queue,
            get_server_instance,
            get_server_instance_args,
            project_root_directory,
            log_file
        ),
        name="cxxd_server"
    )
    server_process.daemon = False
    server_process.start()
    return server_queue

def server_stop(handle, *payload):
    handle.put([ServerRequestId.SHUTDOWN_AND_EXIT, 0x0, list(payload)])

def server_start_all_services(handle, *payload):
    # TODO For this interface to be fully functional, server::_start_all_services
    #      implementation has to be upgraded to support passing service-specific
    #      payloads. I.e. to start all the services and initialize them appropriately,
    #      user might provide a dictionary of the following form:
    #          { service_id0: payload0, service_id1: payload1, ..., service_idN: payloadN }
    handle.put([ServerRequestId.START_ALL_SERVICES, 0x0, list(payload)])

def server_stop_all_services(handle, *payload):
    handle.put([ServerRequestId.SHUTDOWN_ALL_SERVICES, 0x0, list(payload)])

#
# Source code model API
#
def source_code_model_start(handle, compiler_args):
    _server_start_service(handle, ServiceId.SOURCE_CODE_MODEL, compiler_args)

def source_code_model_stop(handle, subscribe_for_callback):
    _server_stop_service(handle, ServiceId.SOURCE_CODE_MODEL, subscribe_for_callback)

def source_code_model_semantic_syntax_highlight_request(handle, filename, contents, line_begin, line_end):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.SEMANTIC_SYNTAX_HIGHLIGHT, filename, contents, line_begin, line_end)

def source_code_model_diagnostics_request(handle, filename, contents):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.DIAGNOSTICS, filename, contents)

def source_code_model_type_deduction_request(handle, filename, contents, line, col):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.TYPE_DEDUCTION, filename, contents, line, col)

def source_code_model_go_to_definition_request(handle, filename, contents, line, col):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.GO_TO_DEFINITION, filename, contents, line, col)

def source_code_model_go_to_include_request(handle, filename, contents, line):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.GO_TO_INCLUDE, filename, contents, line)

def source_code_model_indexer_run_on_single_file_request(handle, filename, contents):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE, filename, contents)

def source_code_model_indexer_run_on_directory_request(handle):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY)

def source_code_model_indexer_drop_single_file_request(handle, filename):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.DROP_SINGLE_FILE, filename)

def source_code_model_indexer_drop_all_request(handle, remove_db_from_disk):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.DROP_ALL, remove_db_from_disk)

def source_code_model_indexer_drop_all_and_run_on_directory_request(handle):
    source_code_model_indexer_drop_all_request(handle, True)
    source_code_model_indexer_run_on_directory_request(handle)

def source_code_model_indexer_find_all_references_request(handle, filename, line, col):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, filename, line, col)

def source_code_model_indexer_fetch_all_diagnostics_request(handle, sorting_strategy):
    _indexer_request(handle, SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS, sorting_strategy)

#
# Project builder service API
#
def project_builder_start(handle):
    _server_start_service(handle, ServiceId.PROJECT_BUILDER)

def project_builder_stop(handle, subscribe_for_callback):
    _server_stop_service(handle, ServiceId.PROJECT_BUILDER, subscribe_for_callback)

def project_builder_request(handle, build_command):
    _server_request_service(handle, ServiceId.PROJECT_BUILDER, build_command)

#
# Clang-format service API
#
def clang_format_start(handle):
    _server_start_service(handle, ServiceId.CLANG_FORMAT)

def clang_format_stop(handle, subscribe_for_callback):
    _server_stop_service(handle, ServiceId.CLANG_FORMAT, subscribe_for_callback)

def clang_format_request(handle, filename):
    _server_request_service(handle, ServiceId.CLANG_FORMAT, filename)

#
# Clang-tidy service API
#
def clang_tidy_start(handle, json_compilation_database):
    _server_start_service(handle, ServiceId.CLANG_TIDY, json_compilation_database)

def clang_tidy_stop(handle, subscribe_for_callback):
    _server_stop_service(handle, ServiceId.CLANG_TIDY, subscribe_for_callback)

def clang_tidy_request(handle, filename, apply_fixes):
    _server_request_service(handle, ServiceId.CLANG_TIDY, filename, apply_fixes)


#
# Helper functions.
#
def _server_start_service(handle, id, *payload):
    handle.put([ServerRequestId.START_SERVICE, id, list(payload)])

def _server_stop_service(handle, id, *payload):
    handle.put([ServerRequestId.SHUTDOWN_SERVICE, id, list(payload)])

def _server_request_service(handle, id, *payload):
    handle.put([ServerRequestId.SEND_SERVICE, id, list(payload)])

def _source_code_model_request(handle, source_code_model_service_id, *source_code_model_service_args):
    _server_request_service(handle, ServiceId.SOURCE_CODE_MODEL, source_code_model_service_id, *source_code_model_service_args)

def _indexer_request(handle, indexer_action_id, *args):
    _source_code_model_request(handle, SourceCodeModelSubServiceId.INDEXER, indexer_action_id, *args)

