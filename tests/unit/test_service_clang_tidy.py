import os
import unittest

from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class ClangTidyWithCompilationDatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_tidy_on = FileGenerator.gen_simple_cpp_file()
        cls.project_root_directory        = os.path.dirname(cls.file_to_perform_clang_tidy_on.name)
        cls.json_compilation_database     = FileGenerator.gen_json_compilation_database(cls.file_to_perform_clang_tidy_on.name)
        cls.target                        = 'debug'
        cls.cxxd_config_with_json_comp_db = FileGenerator.gen_cxxd_config_filename(cls.target, os.path.dirname(cls.json_compilation_database.name))

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_tidy_on)
        FileGenerator.close_gen_file(cls.json_compilation_database)
        FileGenerator.close_gen_file(cls.cxxd_config_with_json_comp_db)

    def setUp(self):
        import cxxd_mocks
        from services.clang_tidy_service import ClangTidy
        self.service = ClangTidy(self.project_root_directory, CxxdConfigParser(self.cxxd_config_with_json_comp_db.name, self.project_root_directory), self.target, cxxd_mocks.ServicePluginMock())

    def test_if_clang_tidy_binary_is_available_on_the_system_path(self):
        self.assertNotEqual(self.service.clang_tidy_binary, None)

    def test_if_compile_flags_are_set_accordingly_to_json_compilation_database_provided(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, '-p ' + self.json_compilation_database.name)

    def test_if_call_returns_true_for_success_and_file_containing_clang_tidy_output_when_run_on_existing_file_without_applying_fixes(self):
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])
        self.assertEqual(success, True)
        self.assertNotEqual(clang_tidy_output, None)

    def test_if_call_returns_true_for_success_and_file_containing_clang_tidy_output_when_run_on_existing_file_with_applying_fixes(self):
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, True])
        self.assertEqual(success, True)
        self.assertNotEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_run_on_inexisting_file_without_applying_fixes(self):
        success, clang_tidy_output = self.service(['inexisting_filename', False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_run_on_inexisting_file_with_applying_fixes(self):
        success, clang_tidy_output = self.service(['inexisting_filename', True])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_clang_tidy_binary_is_not_available_on_the_system_path(self):
        self.service.clang_tidy_binary = None
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

    def test_if_call_returns_false_for_success_and_no_output_when_compile_flags_are_not_available(self):
        self.service.clang_tidy_compile_flags = None
        success, clang_tidy_output = self.service([self.file_to_perform_clang_tidy_on.name, False])        
        self.assertEqual(success, False)
        self.assertEqual(clang_tidy_output, None)

class ClangTidyWithTxtConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_tidy_on = FileGenerator.gen_simple_cpp_file()
        cls.project_root_directory        = os.path.dirname(cls.file_to_perform_clang_tidy_on.name)
        cls.txt_compilation_database      = FileGenerator.gen_txt_compilation_database()
        cls.target                        = 'debug'
        cls.cxxd_config_with_simple_txt   = FileGenerator.gen_cxxd_config_filename(cls.target, os.path.dirname(cls.txt_compilation_database.name), 'compile-flags')

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_tidy_on)
        FileGenerator.close_gen_file(cls.txt_compilation_database)
        FileGenerator.close_gen_file(cls.cxxd_config_with_simple_txt)

    def setUp(self):
        import cxxd_mocks
        from services.clang_tidy_service import ClangTidy
        self.service = ClangTidy(self.project_root_directory, CxxdConfigParser(self.cxxd_config_with_simple_txt.name, self.project_root_directory), self.target, cxxd_mocks.ServicePluginMock())

    def test_if_compile_flags_are_set_accordingly_to_txt_compilation_database_provided(self):
        with open(self.txt_compilation_database.name, 'r') as fd_compile_flags:
            compile_flags = [flag.strip() for flag in fd_compile_flags.readlines()]
            self.assertEqual(self.service.clang_tidy_compile_flags, '-- ' + ' '.join(compile_flags))

class ClangTidyWithNoConfigAvailable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_tidy_on = FileGenerator.gen_simple_cpp_file()
        cls.project_root_directory        = os.path.dirname(cls.file_to_perform_clang_tidy_on.name)
        cls.target                        = 'debug'

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_tidy_on)

    def setUp(self):
        import cxxd_mocks
        from services.clang_tidy_service import ClangTidy
        self.service = ClangTidy(self.project_root_directory, CxxdConfigParser('inexisting_config_file', self.project_root_directory), self.target, cxxd_mocks.ServicePluginMock())

    def test_if_compile_flags_are_set_to_none_when_no_configuration_is_found(self):
        self.assertEqual(self.service.clang_tidy_compile_flags, None)

if __name__ == '__main__':
    unittest.main()

