import unittest

from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class CxxdConfigParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cxxd_config = FileGenerator.gen_cxxd_config_filename()
        cls.empty_cxxd_config = FileGenerator.gen_empty_cxxd_config_filename()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.cxxd_config)
        FileGenerator.close_gen_file(cls.empty_cxxd_config)

    def setUp(self):
        import cxxd_mocks
        from services.clang_format_service import ClangFormat
        self.parser = CxxdConfigParser(self.cxxd_config.name)
        self.parser_with_empty_config_file = CxxdConfigParser(self.empty_cxxd_config.name)
        self.parser_with_inexisting_config_file = CxxdConfigParser('some_inexisting_cxxd_config_filename')

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list_for_inexisting_cxxd_config_file(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list_for_inexisting_cxxd_config_file(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list_for_inexisting_cxxd_config_file(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list_for_inexisting_cxxd_config_file(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_project_builder_args(), [])

    def test_if_cxxd_config_parser_returns_non_empty_blacklisted_dir_list_for_existing_cxxd_config_file_containing_some_blacklisted_dirs(self):
        self.assertNotEqual(self.parser.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_non_empty_clang_tidy_arg_list_for_existing_cxxd_config_file_containing_some_clang_tidy_args(self):
        self.assertNotEqual(self.parser.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_non_empty_clang_format_arg_list_for_existing_cxxd_config_file_containing_some_clang_format_args(self):
        self.assertNotEqual(self.parser.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_non_empty_project_builder_arg_list_for_existing_cxxd_config_file_containing_some_clang_format_args(self):
        self.assertNotEqual(self.parser.get_project_builder_args(), [])

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list_for_existing_cxxd_config_file_which_does_not_contain_any_blacklisted_dirs(self):
        self.assertEqual(self.parser_with_empty_config_file.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list_for_existing_cxxd_config_file_which_does_not_contain_any_clang_tidy_args(self):
        self.assertEqual(self.parser_with_empty_config_file.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list_for_existing_cxxd_config_file_which_does_not_containing_any_clang_format_args(self):
        self.assertEqual(self.parser_with_empty_config_file.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list_for_existing_cxxd_config_file_which_does_not_containing_any_clang_format_args(self):
        self.assertEqual(self.parser_with_empty_config_file.get_project_builder_args(), [])

    def test_if_is_file_blacklisted_handles_files_from_blacklisted_dirs_correctly(self):
        directory_list = ['/tmp']
        filename = '/tmp/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), True)

    def test_if_is_file_blacklisted_handles_files_not_in_blacklisted_dirs_correctly(self):
        directory_list = ['/tmp']
        filename = '/home/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), False)

    def test_if_is_file_blacklisted_handles_file_for_given_dir_recursively(self):
        directory_list = ['/tmp']
        filename = '/tmp/dir1/dir2/dir3/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), True)

if __name__ == '__main__':
    unittest.main()
