import os
import unittest

from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class ClangFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_format_on = FileGenerator.gen_simple_cpp_file()
        cls.clang_format_config_file        = FileGenerator.gen_clang_format_config_file()
        cls.json_compilation_database       = FileGenerator.gen_json_compilation_database(cls.file_to_perform_clang_format_on.name)
        cls.cxxd_config                     = FileGenerator.gen_cxxd_config_filename('debug', os.path.dirname(cls.json_compilation_database.name))
        cls.project_root_directory          = os.path.dirname(cls.file_to_perform_clang_format_on.name)

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_format_on)
        FileGenerator.close_gen_file(cls.clang_format_config_file)
        FileGenerator.close_gen_file(cls.cxxd_config)

    def setUp(self):
        import cxxd_mocks
        from services.clang_format_service import ClangFormat
        self.service = ClangFormat(self.project_root_directory, CxxdConfigParser(self.cxxd_config.name, self.project_root_directory), cxxd_mocks.ServicePluginMock())

    def test_if_clang_format_binary_is_available_on_the_system_path(self):
        self.assertNotEqual(self.service.clang_format_binary, None)

    def test_if_call_returns_true_for_success_and_none_for_args_when_run_on_existing_file(self):
        success, args = self.service([self.file_to_perform_clang_format_on.name])
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_call_returns_false_for_success_and_none_for_args_when_run_on_inexisting_file(self):
        success, args = self.service(['inexisting_filename'])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_call_returns_false_for_success_and_none_for_args_when_run_on_inexisting_file_when_clang_format_binary_is_not_available_on_the_system_path(self):
        clang_format_binary = self.service.clang_format_binary
        self.service.clang_format_binary = None
        success, args = self.service([self.file_to_perform_clang_format_on.name])
        self.service.clang_format_binary = clang_format_binary
        self.assertEqual(success, False)
        self.assertEqual(args, None)

if __name__ == '__main__':
    unittest.main()
