import os
import unittest

from file_generator import FileGenerator

class ProjectBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_be_built = FileGenerator.gen_simple_cpp_file()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_be_built)

    def setUp(self):
        import cxxd_mocks
        from services.project_builder_service import ProjectBuilder
        self.service = ProjectBuilder(cxxd_mocks.ServicePluginMock())
        self.build_cmd = 'gcc -o {0}.o -c {1}'.format(self.file_to_be_built.name, self.file_to_be_built.name)

    def test_if_build_cmd_directory_is_set_to_none_by_default(self):
        self.assertEqual(self.service.build_cmd_dir, None)

    def test_if_build_cmd_output_file_is_set_to_none_by_default(self):
        self.assertEqual(self.service.build_cmd_output_file, None)

    def test_if_startup_callback_sets_build_cmd_dir_and_output_file_accordingly_when_dir_is_existing(self):
        self.assertEqual(self.service.build_cmd_dir, None)
        self.assertEqual(self.service.build_cmd_output_file, None)
        self.service.startup_callback([os.path.dirname(self.file_to_be_built.name)])
        self.assertNotEqual(self.service.build_cmd_dir, None)
        self.assertNotEqual(self.service.build_cmd_output_file, None)

    def test_if_startup_callback_sets_build_cmd_dir_and_output_file_accordingly_when_dir_is_inexisting(self):
        self.assertEqual(self.service.build_cmd_dir, None)
        self.assertEqual(self.service.build_cmd_output_file, None)
        self.service.startup_callback(['inexisting_directory'])
        self.assertEqual(self.service.build_cmd_dir, None)
        self.assertEqual(self.service.build_cmd_output_file, None)

    def test_if_call_returns_true_for_success_file_containing_build_output_and_duration_when_run_on_existing_file(self):
        self.service.startup_callback([os.path.dirname(self.file_to_be_built.name)])
        success, args = self.service([self.build_cmd])
        self.assertEqual(success, True)
        self.assertNotEqual(args, None)
        build_output, exit_code, duration = args
        self.assertNotEqual(build_output, '')
        self.assertEqual(exit_code, 0)
        self.assertNotEqual(duration, -1)

    def test_if_call_returns_false_for_success_and_none_build_output_when_run_on_inexisting_directory(self):
        self.service.startup_callback(['inexisting_directory'])
        success, args = self.service([self.build_cmd])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

if __name__ == '__main__':
    unittest.main()

