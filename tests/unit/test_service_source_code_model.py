import os
import tempfile
import unittest

from file_generator import FileGenerator
from services.source_code_model_service import SourceCodeModelSubServiceId

class SourceCodeModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root_directory = tempfile.gettempdir()
        cls.target                 = ''

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        import cxxd_mocks
        from services.source_code_model_service import SourceCodeModel
        self.service = SourceCodeModel(self.project_root_directory, cxxd_mocks.CxxdConfigParserMock(), self.target, cxxd_mocks.ServicePluginMock())
        self.unknown_subservice_id = 0xABABABA

    def test_if_call_returns_false_and_none_when_triggered_with_unknown_sub_service_id(self):
        success, args = self.service([self.unknown_subservice_id])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

if __name__ == '__main__':
    unittest.main()
