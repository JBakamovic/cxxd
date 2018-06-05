import mock
import os
import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator

class SourceCodeModelGoToDefinitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_file                = FileGenerator.gen_simple_cpp_file()
        cls.test_file_edited         = FileGenerator.gen_simple_cpp_file(edited=True)
        cls.txt_compilation_database = FileGenerator.gen_txt_compilation_database()

        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.test_file)
        FileGenerator.close_gen_file(cls.test_file_edited)
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        import cxxd_mocks
        from services.source_code_model.go_to_definition.go_to_definition import GoToDefinition
        self.project_root_directory = os.path.dirname(self.test_file.name)
        self.service = GoToDefinition(self.parser, cxxd_mocks.SymbolDatabaseMock(), self.project_root_directory)

    def test_if_call_returns_true_and_definition_is_found_for_local_symbol(self):
        success, definition = self.service(
            [self.test_file.name, self.test_file.name, 9, 12]
        )
        filename, line, column = definition
        self.assertEqual(success, True)
        self.assertEqual(filename, self.test_file.name)
        self.assertEqual(line, 3)
        self.assertEqual(column, 5)

    def test_if_call_returns_true_and_definition_is_found_for_local_symbol_with_current_tunit_being_modified(self):
        success, definition = self.service(
            [self.test_file.name, self.test_file_edited.name, 10, 18]
        )
        filename, line, column = definition
        self.assertEqual(success, True)
        self.assertEqual(filename, self.test_file.name) # still returns an original filename and not the edited (temporary) one
        self.assertEqual(line, 4)
        self.assertEqual(column, 5)

    def test_if_call_returns_true_and_definition_is_found_for_non_local_symbol_included_via_header(self):
        success, definition = self.service(
            [self.test_file.name, self.test_file.name, 8, 10]
        )
        filename, line, column = definition
        self.assertEqual(success, True)
        self.assertNotEqual(filename, self.test_file.name)
        self.assertGreaterEqual(line, 0)
        self.assertGreaterEqual(column, 0)

    def test_if_call_returns_true_and_definition_is_found_for_non_local_symbol_included_via_header_with_current_tunit_being_modified(self):
        success, definition = self.service(
            [self.test_file.name, self.test_file_edited.name, 9, 10]
        )
        filename, line, column = definition
        self.assertEqual(success, True)
        self.assertNotEqual(filename, self.test_file.name)
        self.assertGreaterEqual(line, 0)
        self.assertGreaterEqual(column, 0)

    def test_if_call_returns_false_and_definition_is_not_found_for_non_local_symbol_not_included_via_header_and_not_found_in_symbol_db(self):
        rows = []
        with mock.patch.object(self.service.symbol_db, 'fetch_symbol_definition_by_usr', return_value=rows) as mock_symbol_db_fetch_symbol_definition_by_usr:
            success, definition = self.service(
                [self.test_file.name, self.test_file.name, 13, 12]
            )
        filename, line, column = definition
        self.assertEqual(success, False)
        self.assertEqual(filename, None)
        self.assertEqual(line, None)
        self.assertEqual(column, None)

    def test_if_call_returns_false_and_definition_is_not_found_for_non_local_symbol_not_included_via_header_and_not_found_in_symbol_db_with_current_tunit_being_modified(self):
        rows = []
        with mock.patch.object(self.service.symbol_db, 'fetch_symbol_definition_by_usr', return_value=rows) as mock_symbol_db_fetch_symbol_definition_by_usr:
            success, definition = self.service(
                [self.test_file.name, self.test_file_edited.name, 15, 12]
            )
        filename, line, column = definition
        self.assertEqual(success, False)
        self.assertEqual(filename, None)
        self.assertEqual(line, None)
        self.assertEqual(column, None)

    def test_if_call_returns_true_and_definition_is_found_for_non_local_symbol_not_included_via_header_but_found_in_symbol_db(self):
        made_up_filename, line, column = 'name_of_some_other_translation_unit_extracted_from_symbol_db', 124, 5
        rows = [(made_up_filename, line, column)]
        with mock.patch.object(self.service.symbol_db, 'fetch_symbol_definition_by_usr', return_value=rows) as mock_symbol_db_fetch_symbol_definition_by_usr:
            with mock.patch.object(self.service.symbol_db, 'get_symbol_filename', return_value=made_up_filename):
                with mock.patch.object(self.service.symbol_db, 'get_symbol_line', return_value=line):
                    with mock.patch.object(self.service.symbol_db, 'get_symbol_column', return_value=column):
                        success, definition = self.service(
                            [self.test_file.name, self.test_file.name, 13, 12]
                        )
        def_filename, def_line, def_column = definition
        self.assertEqual(success, True)
        self.assertNotEqual(def_filename, self.test_file.name)
        self.assertGreaterEqual(def_filename.find(self.project_root_directory), 0)
        self.assertGreaterEqual(def_filename.find(made_up_filename), 0)
        self.assertEqual(def_line, line)
        self.assertEqual(def_column, column)

    def test_if_call_returns_true_and_definition_is_found_for_non_local_symbol_not_included_via_header_but_found_in_symbol_db_with_current_tunit_being_modified(self):
        made_up_filename, line, column = 'name_of_some_other_translation_unit_extracted_from_symbol_db', 124, 5
        rows = [(made_up_filename, line, column)]
        with mock.patch.object(self.service.symbol_db, 'fetch_symbol_definition_by_usr', return_value=rows) as mock_symbol_db_fetch_symbol_definition_by_usr:
            with mock.patch.object(self.service.symbol_db, 'get_symbol_filename', return_value=made_up_filename):
                with mock.patch.object(self.service.symbol_db, 'get_symbol_line', return_value=line):
                    with mock.patch.object(self.service.symbol_db, 'get_symbol_column', return_value=column):
                        success, definition = self.service(
                            [self.test_file.name, self.test_file_edited.name, 15, 12]
                        )
        def_filename, def_line, def_column = definition
        self.assertEqual(success, True)
        self.assertNotEqual(def_filename, self.test_file.name)
        self.assertGreaterEqual(def_filename.find(self.project_root_directory), 0)
        self.assertGreaterEqual(def_filename.find(made_up_filename), 0)
        self.assertEqual(def_line, line)
        self.assertEqual(def_column, column)

    # TODO test for non-parseable translation units (compile errors?)

if __name__ == '__main__':
    unittest.main()

