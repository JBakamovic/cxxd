import unittest

from file_generator import FileGenerator

class ClangFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_perform_clang_format_on = FileGenerator.gen_simple_cpp_file()
        cls.clang_format_config_file        = FileGenerator.gen_clang_format_config_file()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_perform_clang_format_on)
        FileGenerator.close_gen_file(cls.clang_format_config_file)

    def setUp(self):
        import cxxd_mocks
        from services.clang_format_service import ClangFormat
        self.service = ClangFormat(cxxd_mocks.ServicePluginMock())

    def test_if_config_file_is_set_to_none_by_default(self):
        self.assertEqual(self.service.clang_format_config_file, None)

    def test_if_clang_format_binary_is_available_on_the_system_path(self):
        self.assertNotEqual(self.service.clang_format_binary, None)

    def test_if_startup_callback_sets_config_file_accordingly_when_clang_format_binary_is_not_available_on_the_system_path(self):
        self.service.clang_format_binary = None
        self.assertEqual(self.service.clang_format_config_file, None)
        self.service.startup_callback([self.clang_format_config_file.name])
        self.assertEqual(self.service.clang_format_config_file, None)

    def test_if_startup_callback_sets_config_file_accordingly_when_config_file_is_not_existing(self):
        self.assertEqual(self.service.clang_format_config_file, None)
        self.service.startup_callback(['some_totally_config_file_random_name'])
        self.assertEqual(self.service.clang_format_config_file, None)

    def test_if_call_returns_true_for_success_and_none_for_args_when_run_on_existing_file(self):
        self.service.startup_callback([self.clang_format_config_file.name])
        success, args = self.service([self.file_to_perform_clang_format_on.name])
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_call_returns_false_for_success_and_none_for_args_when_run_on_inexisting_file(self):
        self.service.startup_callback([self.clang_format_config_file.name])
        success, args = self.service(['inexisting_filename'])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_call_returns_false_for_success_and_none_for_args_when_run_on_inexisting_file_when_clang_format_binary_is_not_available_on_the_system_path(self):
        self.service.clang_format_binary = None
        self.service.startup_callback([self.clang_format_config_file.name])
        success, args = self.service([self.file_to_perform_clang_format_on.name])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_call_returns_false_for_success_and_none_for_args_when_clang_format_config_file_is_not_available(self):
        self.service.startup_callback(['inexisting_clang_format_config_file'])
        success, args = self.service([self.file_to_perform_clang_format_on.name])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

if __name__ == '__main__':
    unittest.main()
