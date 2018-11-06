import os
import unittest

from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class ClangTidyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_tidy_on = FileGenerator.gen_simple_cpp_file()
        cls.project_root_directory        = os.path.dirname(cls.file_to_perform_clang_tidy_on.name)
        cls.txt_compilation_database      = FileGenerator.gen_txt_compilation_database()
        cls.json_compilation_database     = FileGenerator.gen_json_compilation_database(cls.file_to_perform_clang_tidy_on.name)
        cls.cxxd_config                   = FileGenerator.gen_cxxd_config_filename()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_tidy_on)
        FileGenerator.close_gen_file(cls.json_compilation_database)
        FileGenerator.close_gen_file(cls.txt_compilation_database)
        FileGenerator.close_gen_file(cls.cxxd_config)

    def setUp(self):
        import cxxd_mocks
        from services.clang_tidy_service import ClangTidy
        self.service = ClangTidy(self.project_root_directory, CxxdConfigParser(self.cxxd_config.name), cxxd_mocks.ServicePluginMock())
        self.unsupported_compilation_database = 'compiler_flags.yaml'

    def test_if_compile_flags_are_set_to_none_by_default(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)

    def test_if_clang_tidy_binary_is_available_on_the_system_path(self):
        self.assertNotEqual(self.service.clang_tidy_binary, None)

    def test_if_startup_callback_sets_compile_flags_accordingly_when_json_compilation_database_provided(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)
        self.service.startup_callback([self.json_compilation_database.name])
        self.assertEqual(self.service.clang_tidy_compile_flags, '-p ' + self.json_compilation_database.name)

    def test_if_startup_callback_sets_compile_flags_accordingly_when_txt_compilation_database_provided(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)
        self.service.startup_callback([self.txt_compilation_database.name])
        with open(self.txt_compilation_database.name, 'r') as fd_compile_flags:
            compile_flags = [flag.strip() for flag in fd_compile_flags.readlines()]
            self.assertEqual(self.service.clang_tidy_compile_flags, '-- ' + ' '.join(compile_flags))

    def test_if_startup_callback_sets_compile_flags_accordingly_when_unsupported_compilation_database_provided(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)
        self.service.startup_callback([self.unsupported_compilation_database])
        self.assertEqual(self.service.clang_tidy_compile_flags, None)

    def test_if_startup_callback_sets_compile_flags_accordingly_when_compilation_database_file_provided_is_not_existing(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)
        self.service.startup_callback(['some_totally_compilation_database_random_name'])
        self.assertEqual(self.service.clang_tidy_compile_flags, None)

    def test_if_startup_callback_sets_compile_flags_accordingly_when_clang_tidy_binary_is_not_available_on_the_system_path(self):
        self.service.clang_tidy_binary = None
        self.assertEqual(self.service.clang_tidy_compile_flags, None)
        self.service.startup_callback([self.json_compilation_database.name])
        self.assertEqual(self.service.clang_tidy_compile_flags, None)

    def test_if_call_returns_true_for_success_and_file_containing_clang_tidy_output_when_run_on_existing_file_without_applying_fixes(self):
        self.service.startup_callback([self.json_compilation_database.name])
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])
        self.assertEqual(success, True)
        self.assertNotEqual(clang_tidy_output, None)

    def test_if_call_returns_true_for_success_and_file_containing_clang_tidy_output_when_run_on_existing_file_with_applying_fixes(self):
        self.service.startup_callback([self.json_compilation_database.name])
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, True])
        self.assertEqual(success, True)
        self.assertNotEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_run_on_inexisting_file_without_applying_fixes(self):
        self.service.startup_callback([self.json_compilation_database.name])
        success, clang_tidy_output = self.service(['inexisting_filename', False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_run_on_inexisting_file_with_applying_fixes(self):
        self.service.startup_callback([self.json_compilation_database.name])
        success, clang_tidy_output = self.service(['inexisting_filename', True])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_clang_tidy_binary_is_not_available_on_the_system_path(self):
        self.service.clang_tidy_binary = None
        self.service.startup_callback([self.json_compilation_database.name])
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_compile_flags_are_not_available(self):
        self.service.startup_callback([self.unsupported_compilation_database])
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

if __name__ == '__main__':
    unittest.main()

