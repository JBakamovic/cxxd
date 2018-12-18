import cProfile
import os
import pstats
import shutil
import sys
import unittest

import cxxd.api
import cxxd.server
import cxxd.tests.integration.cxxd_callbacks as cxxd_callbacks
import cxxd.tests.integration.cxxd_plugins as cxxd_plugins

# External dependencies we will run the integration tests on ...
current_dir = os.path.dirname(os.path.realpath(__file__))
ext_dep = {
    'chaiscript' : {
        'path' : current_dir + os.sep + 'external' + os.sep + 'ChaiScript',
    }
}

# We have to provide a factory method to instantiate the server the way we want ...
def get_server_instance(handle, proj_root_directory, target_configuration, args):
    source_code_model_cb_result, clang_format_cb_result, clang_tidy_cb_result, project_builder_cb_result  = args
    return cxxd.server.Server(
        handle,
        proj_root_directory,
        target_configuration,
        cxxd_plugins.SourceCodeModelServicePluginMock(source_code_model_cb_result),
        cxxd_plugins.ProjectBuilderServicePluginMock(project_builder_cb_result),
        cxxd_plugins.ClangFormatServicePluginMock(clang_format_cb_result),
        cxxd_plugins.ClangTidyServicePluginMock(clang_tidy_cb_result)
    )

# compile_commands.json is what we have to have in order to run the integration tests
def gen_compile_commands_json(project_root_directory):
    import shlex, subprocess
    cmd = 'cmake . -DCMAKE_EXPORT_COMPILE_COMMANDS=ON'
    return subprocess.call(shlex.split(cmd), cwd=project_root_directory)

# .clang-format is what we have to have in order to run clang-format related integration tests
def gen_clang_format_configuration(project_root_directory):
    import shlex, subprocess
    cmd = 'clang-format -style=llvm -dump-config > .clang-format'
    return subprocess.call(shlex.split(cmd), cwd=project_root_directory)

# In case we need to revert the change caused by some test (i.e. clang-format)
def revert_the_file_content_change(root_dir, filename):
    import shlex, subprocess
    cmd = 'git checkout -- ' + filename
    return subprocess.call(shlex.split(cmd), cwd=root_dir)

class CxxdIntegrationTest(unittest.TestCase):
    DROP_SYMBOL_DB = True
    PROFILER_OUTPUT = None

    @classmethod
    def setUpClass(cls):
        # Setup some paths
        cls.fut = ext_dep['chaiscript']['path'] + os.sep + 'include' + os.sep + 'chaiscript' + os.sep + 'chaiscript_stdlib.hpp'
        cls.fut_cpp = ext_dep['chaiscript']['path'] + os.sep + 'src' + os.sep + 'main.cpp'
        cls.fut_cpp_edited = cls.fut_cpp + '.tmp' # Edited files are serialized into temporary files so we create one here ...
        shutil.copyfile(cls.fut_cpp, cls.fut_cpp_edited)
        cls.proj_root_dir = ext_dep['chaiscript']['path']
        cls.target_configuration = None # We force Cxxd go into auto-discovery mode if we don't provide any configuration
        cls.clang_format_config = cls.proj_root_dir + os.sep + '.clang-format'
        cls.log_file = current_dir + os.sep + 'cxxd.log'

        # Profiling stats
        cls.profiler = None
        cls.profiling_stats = []
        cls.profiling_output = open(CxxdIntegrationTest.PROFILER_OUTPUT, 'w') if CxxdIntegrationTest.PROFILER_OUTPUT else sys.stdout

        # Generate compile_commands.json
        gen_compile_commands_json(cls.proj_root_dir)

        # Generate .clang-format
        gen_clang_format_configuration(cls.proj_root_dir)

        # Define where to store callback results from various requests we will trigger during the tests
        cls.source_code_model_cb_result = cxxd_callbacks.SourceCodeModelCallbackResult()
        cls.clang_format_cb_result = cxxd_callbacks.ClangFormatCallbackResult()
        cls.clang_tidy_cb_result = cxxd_callbacks.ClangTidyCallbackResult()
        cls.project_builder_cb_result = cxxd_callbacks.ProjectBuilderCallbackResult()

        # Start the cxxd server ...
        cls.handle = cxxd.api.server_start(
            get_server_instance,
            (
                cls.source_code_model_cb_result,
                cls.clang_format_cb_result,
                cls.clang_tidy_cb_result,
                cls.project_builder_cb_result,
            ),
            cls.proj_root_dir,
            cls.target_configuration,
            cls.log_file
        )

        # And services that we want to test ...
        cxxd.api.source_code_model_start(cls.handle)
        cxxd.api.clang_format_start(cls.handle)
        cxxd.api.clang_tidy_start(cls.handle)
        cxxd.api.project_builder_start(cls.handle)

        # Run the indexer ... Wait until it completes.
        cxxd.api.source_code_model_indexer_run_on_directory_request(cls.handle)
        cls.source_code_model_cb_result.wait_until_available()
        assert cls.source_code_model_cb_result['indexer'].status == True # can't use unittest asserts here ...

    @classmethod
    def tearDownClass(cls):
        if CxxdIntegrationTest.DROP_SYMBOL_DB:
            cxxd.api.source_code_model_indexer_drop_all_request(cls.handle, remove_db_from_disk=True)
            cls.source_code_model_cb_result.wait_until_available()
            assert cls.source_code_model_cb_result['indexer'].status == True # can't use unittest asserts here ...
        cxxd.api.server_stop(cls.handle)
        os.remove(cls.log_file)
        os.remove(cls.fut_cpp_edited)
        cls.profiling_stats.sort(key=lambda stat: stat.total_tt) # Sort profiling stats by total time
        for stat in cls.profiling_stats: # Dump the profiling stats we collected.
            stat.sort_stats('cumtime').print_stats()

    def setUp(self):
        self.source_code_model_cb_result.reset()
        self.clang_format_cb_result.reset()
        self.clang_tidy_cb_result.reset()
        self.project_builder_cb_result.reset()
        self.profiler = cProfile.Profile() # We don't want to accumulate profiling stats over all tests.
        self.profiler.enable()

    def tearDown(self):
        self.profiler.create_stats()
        self.profiling_stats.append(pstats.Stats(self.profiler, stream=self.profiling_output))

    def test_source_code_model_indexer_run_on_directory(self):
        cxxd.api.source_code_model_indexer_run_on_directory_request(self.handle)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['indexer'].status)

    def test_source_code_model_indexer_drop_single_file(self):
        cxxd.api.source_code_model_indexer_drop_single_file_request(self.handle, self.fut)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['indexer'].status)

    def test_source_code_model_indexer_run_on_single_file(self):
        cxxd.api.source_code_model_indexer_run_on_single_file_request(self.handle, self.fut)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['indexer'].status)

    def test_source_code_model_indexer_find_all_references_request(self):
        cxxd.api.source_code_model_indexer_find_all_references_request(self.handle, self.fut, 56, 76)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['indexer'].status)
        self.assertNotEqual(self.source_code_model_cb_result['indexer'].num_of_references, 0)

    def test_source_code_model_indexer_fetch_all_diagnostics_request(self):
        sorting_strategy = 0 # No sorting
        cxxd.api.source_code_model_indexer_fetch_all_diagnostics_request(self.handle, sorting_strategy)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['indexer'].status)
        self.assertNotEqual(self.source_code_model_cb_result['indexer'].num_of_diagnostics, 0)

    def test_source_code_model_go_to_definition_request(self):
        cxxd.api.source_code_model_go_to_definition_request(self.handle, self.fut, self.fut, 52, 73)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['go_to_definition'].status)
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].filename, '')
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].line, 0)
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].column, 0)

    def test_source_code_model_go_to_definition_on_fwd_declared_symbol_request(self):
        fut = ext_dep['chaiscript']['path'] + os.sep + 'include' + os.sep + 'chaiscript' + os.sep + 'dispatchkit' + os.sep + 'dispatchkit.hpp'
        cxxd.api.source_code_model_go_to_definition_request(self.handle, fut, fut, 49, 7)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['go_to_definition'].status)
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].filename, '')
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].line, 0)
        self.assertNotEqual(self.source_code_model_cb_result['go_to_definition'].column, 0)

    def test_source_code_model_go_to_include_request(self):
        cxxd.api.source_code_model_go_to_include_request(self.handle, self.fut, self.fut, 17)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['go_to_include'].status)
        self.assertNotEqual(self.source_code_model_cb_result['go_to_include'].filename, '')

    def test_source_code_model_type_deduction_request(self):
        cxxd.api.source_code_model_type_deduction_request(self.handle, self.fut, self.fut, 57, 71)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['type_deduction'].status)
        self.assertNotEqual(self.source_code_model_cb_result['type_deduction'].spelling, '')

    def test_source_code_model_semantic_syntax_highlight_request(self):
        cxxd.api.source_code_model_semantic_syntax_highlight_request(self.handle, self.fut, self.fut, 1, 10)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['semantic_syntax_hl'].status)
        self.assertNotEqual(self.source_code_model_cb_result['semantic_syntax_hl'].tunit_spelling, '')
        self.assertNotEqual(self.source_code_model_cb_result['semantic_syntax_hl'].num_of_ast_nodes, 0)

    def test_source_code_model_diagnostics_request(self):
        cxxd.api.source_code_model_diagnostics_request(self.handle, self.fut, self.fut)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['diagnostics'].status)

    def test_source_code_model_auto_completion_code_complete_request_on_a_fresh_non_cached_file(self):
        # This, not so relevant (!), use case involves parsing the file first and THEN triggering the code-complete so it is basically
        # profiling two different things. Generally, code-complete will NOT be operating on inexisting TUnits because there are other
        # services which will parse the file we opened way before the code-complete service even kicks in.
        cxxd.api.source_code_model_auto_completion_code_complete_request(self.handle, self.fut_cpp, self.fut_cpp, 64, 4, 1235, 0)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['auto_completion'].status)
        self.assertNotEqual(self.source_code_model_cb_result['auto_completion'].num_of_code_complete_candidates, 0)

    def test_source_code_model_auto_completion_code_complete_request_on_cached_file(self):
        # This use case relies on a fact that TUnit under test will exist in TUnit cache (which it will because of the previous unit test).
        # We are trying to test how much does it take for code-complete to complete on existing but NOT up-to-date TUnits.
        cxxd.api.source_code_model_auto_completion_code_complete_request(self.handle, self.fut_cpp, self.fut_cpp_edited, 44, 7, 1235, 0)
        self.source_code_model_cb_result.wait_until_available()
        self.assertTrue(self.source_code_model_cb_result['auto_completion'].status)
        self.assertNotEqual(self.source_code_model_cb_result['auto_completion'].num_of_code_complete_candidates, 0)

    def test_clang_tidy_request(self):
        fut = ext_dep['chaiscript']['path'] + os.sep + 'src' + os.sep + 'chaiscript_stdlib_module.cpp'
        cxxd.api.clang_tidy_request(self.handle, fut, apply_fixes=False)
        self.clang_tidy_cb_result.wait_until_available()
        self.assertTrue(self.clang_tidy_cb_result.status)
        self.assertNotEqual(self.clang_tidy_cb_result.output, '')

    def test_clang_format_request(self):
        root_dir = ext_dep['chaiscript']['path']
        filename = 'src' + os.sep + 'chaiscript_stdlib_module.cpp'
        fut      = root_dir + os.sep + filename
        cxxd.api.clang_format_request(self.handle, fut)
        self.clang_format_cb_result.wait_until_available()
        self.assertTrue(self.clang_format_cb_result.status)
        revert_the_file_content_change(root_dir, filename)

    def test_project_builder_request(self):
        fake_build_command = 'cmake --system-information'
        cxxd.api.project_builder_request(self.handle, fake_build_command)
        self.project_builder_cb_result.wait_until_available()
        self.assertTrue(self.project_builder_cb_result.status)
        self.assertNotEqual(self.project_builder_cb_result.output, '')

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--do_not_drop_symbol_db', action='store_true',\
        help='Use if you want to instruct the CxxdIntegrationTest not to drop the symbol database after it has\
        run all of the tests. Dropping the database after each run will slow down the develop-test-debug cycle\
        as indexing operation takes a quite some time. Hence, this flag''s purpose is to override such behavior.'
    )
    parser.add_argument('--profiler_output', help='Name of a file you want profiler to output its stats to. If\
        left empty, profiler stats will be printed to stdout.'
    )
    parser.add_argument('unittest_args', nargs='*')

    args = parser.parse_args()

    # Forward unittest module arguments
    sys.argv[1:] = args.unittest_args

    CxxdIntegrationTest.DROP_SYMBOL_DB = not args.do_not_drop_symbol_db
    CxxdIntegrationTest.PROFILER_OUTPUT = args.profiler_output

    unittest.main()
