from __future__ import absolute_import
import unittest

import parser.clang_parser
import parser.tunit_cache
from . file_generator import FileGenerator

class GoToIncludeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_file                = FileGenerator.gen_simple_cpp_file()
        cls.test_file_edited         = FileGenerator.gen_simple_cpp_file(edited=True)
        cls.test_file_broken         = FileGenerator.gen_broken_cpp_file()
        cls.test_file_broken_edited  = FileGenerator.gen_broken_cpp_file(edited=True)
        cls.txt_compilation_database = FileGenerator.gen_txt_compilation_database()

        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.test_file)
        FileGenerator.close_gen_file(cls.test_file_edited)
        FileGenerator.close_gen_file(cls.test_file_broken)
        FileGenerator.close_gen_file(cls.test_file_broken_edited)
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        from . import cxxd_mocks
        from services.source_code_model.go_to_include.go_to_include import GoToInclude
        self.service = GoToInclude(self.parser)

    def test_if_call_returns_true_and_system_include_filename_is_found(self):
        success, include = self.service([self.test_file.name, self.test_file.name, 1])
        self.assertEqual(success, True)
        self.assertNotEqual(include, None)

    def test_if_call_returns_true_and_system_include_filename_is_found_in_edited_cpp_file(self):
        success, include = self.service([self.test_file.name, self.test_file_edited.name, 1])
        self.assertEqual(success, True)
        self.assertNotEqual(include, None)

    def test_if_call_returns_false_and_none_for_inexisting_include(self):
        success, include = self.service([self.test_file_broken.name, self.test_file_broken.name, 2])
        self.assertEqual(success, False)
        self.assertEqual(include, None)

    def test_if_call_returns_false_and_none_for_inexisting_include_in_edited_cpp_file(self):
        success, include = self.service([self.test_file_broken.name, self.test_file_broken_edited.name, 2])
        self.assertEqual(success, False)
        self.assertEqual(include, None)
