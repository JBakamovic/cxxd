import os
import unittest

from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class ProjectBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_to_be_built          = FileGenerator.gen_simple_cpp_file()
        cls.json_compilation_database = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.cxxd_config               = FileGenerator.gen_cxxd_config_filename('debug', os.path.dirname(cls.json_compilation_database.name))
        cls.project_root_directory    = os.path.dirname(cls.file_to_be_built.name)

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.file_to_be_built)
        FileGenerator.close_gen_file(cls.cxxd_config)

    def setUp(self):
        import cxxd_mocks
        from services.project_builder_service import ProjectBuilder
        self.service = ProjectBuilder(self.project_root_directory, CxxdConfigParser(self.cxxd_config.name, self.project_root_directory), cxxd_mocks.ServicePluginMock())
        self.build_cmd = 'gcc -o {0}.o -c {1}'.format(self.file_to_be_built.name, self.file_to_be_built.name)

    def test_if_call_returns_true_for_success_file_containing_build_output_and_duration_when_run_on_existing_file(self):
        success, args = self.service([self.build_cmd])
        self.assertEqual(success, True)
        self.assertNotEqual(args, None)
        build_output, exit_code, duration = args
        self.assertNotEqual(build_output, '')
        self.assertEqual(exit_code, 0)
        self.assertNotEqual(duration, -1)

if __name__ == '__main__':
    unittest.main()
