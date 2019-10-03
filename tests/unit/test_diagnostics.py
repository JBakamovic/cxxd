from __future__ import absolute_import
import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator

class SourceCodeModelDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_file_with_no_diagnostics        = FileGenerator.gen_simple_cpp_file()
        cls.test_file_with_no_diagnostics_edited = FileGenerator.gen_simple_cpp_file(edited=True)
        cls.test_file_with_compile_errors        = FileGenerator.gen_broken_cpp_file()
        cls.test_file_with_compile_errors_edited = FileGenerator.gen_broken_cpp_file(edited=True)
        cls.txt_compilation_database             = FileGenerator.gen_txt_compilation_database()

        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.test_file_with_no_diagnostics)
        FileGenerator.close_gen_file(cls.test_file_with_no_diagnostics_edited)
        FileGenerator.close_gen_file(cls.test_file_with_compile_errors)
        FileGenerator.close_gen_file(cls.test_file_with_compile_errors_edited)
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        from  import cxxd_mocks
        from services.source_code_model.diagnostics.diagnostics import Diagnostics
        self.service = Diagnostics(self.parser)

    def test_if_call_returns_true_and_empty_diagnostics_iterator_for_diagnostics_free_source_code(self):
        success, [diagnostics_iter, diagnostics_visitor, fixits_visitor] = self.service([self.test_file_with_no_diagnostics.name, self.test_file_with_no_diagnostics.name])
        self.assertEqual(success, True)
        self.assertEqual(len(diagnostics_iter), 0)

    def test_if_call_returns_true_and_empty_diagnostics_iterator_for_edited_diagnostics_free_source_code(self):
        success, [diagnostics_iter, diagnostics_visitor, fixits_visitor] = self.service([self.test_file_with_no_diagnostics.name, self.test_file_with_no_diagnostics_edited.name])
        self.assertEqual(success, True)
        self.assertEqual(len(diagnostics_iter), 0)

    def test_if_call_returns_true_and_empty_diagnostics_iterator_for_source_code_containing_compiling_error(self):
        success, [diagnostics_iter, diagnostics_visitor, fixits_visitor] = self.service([self.test_file_with_compile_errors.name, self.test_file_with_compile_errors.name])
        self.assertEqual(success, True)
        self.assertNotEqual(len(diagnostics_iter), 0)

    def test_if_call_returns_true_and_empty_diagnostics_iterator_for_edited_source_code_containing_compiling_error(self):
        success, [diagnostics_iter, diagnostics_visitor, fixits_visitor] = self.service([self.test_file_with_compile_errors.name, self.test_file_with_compile_errors_edited.name])
        self.assertEqual(success, True)
        self.assertNotEqual(len(diagnostics_iter), 0)

    def test_if_call_returns_false_and_none_as_diagnostics_iterator_for_inexisting_source_code(self):
        success, [diagnostics_iter, diagnostics_visitor, fixits_visitor] = self.service(['inexisting_source_code_filename', 'inexisting_source_code_filename'])
        self.assertEqual(success, False)
        self.assertEqual(diagnostics_iter, None)

if __name__ == '__main__':
    unittest.main()
