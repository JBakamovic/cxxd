from __future__ import absolute_import
import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator

class TypeDeductionTest(unittest.TestCase):
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
        from  import cxxd_mocks
        from services.source_code_model.type_deduction.type_deduction import TypeDeduction
        self.service = TypeDeduction(self.parser)

    def test_if_call_returns_true_and_type_is_deducted_for_location_containing_symbol(self):
        success, type_spelling = self.service([self.test_file.name, self.test_file.name, 3, 5])
        self.assertEqual(success, True)
        self.assertNotEqual(type_spelling, None)

    def test_if_call_returns_true_and_type_is_deducted_for_location_containing_symbol_in_edited_cpp_file(self):
        success, type_spelling = self.service([self.test_file.name, self.test_file_edited.name, 4, 5])
        self.assertEqual(success, True)
        self.assertNotEqual(type_spelling, None)

    def test_if_call_returns_true_and_empty_type_spelling_for_location_containing_no_symbol(self):
        success, type_spelling = self.service([self.test_file.name, self.test_file.name, 2, 1])
        self.assertEqual(success, True)
        self.assertEqual(type_spelling, '')

    def test_if_call_returns_true_and_empty_type_spelling_for_location_containing_no_symbol_in_edited_cpp_file(self):
        success, type_spelling = self.service([self.test_file.name, self.test_file_edited.name, 3, 1])
        self.assertEqual(success, True)
        self.assertEqual(type_spelling, '')

    def test_if_call_returns_true_and_empty_type_spelling_for_files_containing_compilation_error(self):
        success, type_spelling = self.service([self.test_file_broken.name, self.test_file_broken.name, 7, 5])
        self.assertEqual(success, True)
        self.assertEqual(type_spelling, '')

    def test_if_call_returns_true_and_empty_type_spelling_for_files_containing_compilation_error_in_edited_cpp_file(self):
        success, type_spelling = self.service([self.test_file_broken.name, self.test_file_broken_edited.name, 6, 5])
        self.assertEqual(success, True)
        self.assertEqual(type_spelling, '')
