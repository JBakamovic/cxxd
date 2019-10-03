from __future__ import division
from __future__ import absolute_import
from past.utils import old_div
import clang.cindex
import mock
import os
import unittest

from  import cxxd_mocks
import parser.ast_node_identifier
import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator
from services.source_code_model.indexer.clang_indexer import SourceCodeModelIndexerRequestId
from services.source_code_model.indexer.clang_indexer import ClangIndexer
from services.source_code_model.indexer.clang_indexer import create_empty_symbol_db
from services.source_code_model.indexer.clang_indexer import create_indexer_input_list_file
from services.source_code_model.indexer.clang_indexer import get_clang_index_path
from services.source_code_model.indexer.clang_indexer import get_cpp_file_list
from services.source_code_model.indexer.clang_indexer import index_file_list
from services.source_code_model.indexer.clang_indexer import index_single_file
from services.source_code_model.indexer.clang_indexer import indexer_visitor
from services.source_code_model.indexer.clang_indexer import store_tunit_diagnostics
from services.source_code_model.indexer.clang_indexer import remove_root_dir_from_filename
from services.source_code_model.indexer.clang_indexer import start_indexing_subprocess
from services.source_code_model.indexer.symbol_database import SymbolDatabase

class ClangIndexerTest(unittest.TestCase):
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
        self.unsupported_ast_node_ids = [
            parser.ast_node_identifier.ASTNodeId.getNamespaceId(),
            parser.ast_node_identifier.ASTNodeId.getTemplateTypeParameterId(),
            parser.ast_node_identifier.ASTNodeId.getTemplateNonTypeParameterId(),
            parser.ast_node_identifier.ASTNodeId.getTemplateTemplateParameterId(),
            parser.ast_node_identifier.ASTNodeId.getNamespaceAliasId(),
            parser.ast_node_identifier.ASTNodeId.getUsingDirectiveId(),
            parser.ast_node_identifier.ASTNodeId.getUnsupportedId(),
        ]
        self.root_directory = os.path.dirname(self.test_file.name)
        self.service = ClangIndexer(self.parser, self.root_directory, cxxd_mocks.CxxdConfigParserMock())

    def test_if_symbol_db_conn_is_automatically_established_in_case_db_already_exists_on_the_disk(self):
        symbol_db = SymbolDatabase(os.path.join(self.root_directory, self.service.symbol_db_name))
        service = ClangIndexer(self.parser, self.root_directory, cxxd_mocks.CxxdConfigParserMock())
        self.assertTrue(service.symbol_db_exists())
        self.assertTrue(service.get_symbol_db().is_open())
        symbol_db.close()
        os.remove(symbol_db.filename)
        self.assertFalse(service.symbol_db_exists())

    def test_if_symbol_db_conn_is_not_established_in_case_db_does_not_exist_on_the_disk(self):
        service = ClangIndexer(self.parser, self.root_directory, cxxd_mocks.CxxdConfigParserMock())
        self.assertFalse(service.symbol_db_exists())
        self.assertFalse(service.get_symbol_db().is_open())

    def test_if_symbol_db_is_located_in_root_directory(self):
        self.assertEqual(self.service.symbol_db_path, os.path.join(self.root_directory, self.service.symbol_db_name))

    def test_if_call_returns_false_for_unsupported_request(self):
        unsupported_request = 0xFF
        success, args = self.service([unsupported_request])
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_run_on_single_file_skips_indexing_if_symbol_db_is_inexisting(self):
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch('services.source_code_model.indexer.clang_indexer.index_single_file') as mock_index_single_file:
                success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE, self.test_file.name])
        mock_index_single_file.assert_not_called()
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_run_on_single_file_skips_indexing_when_file_is_in_blacklisted_directory(self):
        self.service.blacklisted_directories.append(os.path.dirname(self.test_file.name))
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch('services.source_code_model.indexer.clang_indexer.index_single_file') as mock_index_single_file:
                success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE, self.test_file.name])
        self.service.blacklisted_directories.pop()
        mock_index_single_file.assert_not_called()
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_run_on_single_file_deletes_an_entry_from_symbol_db_using_its_basename_and_then_successfully_indexes_the_file(self):
        manager = mock.MagicMock()
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_entry') as mock_symbol_db_delete_entry:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.remove_root_dir_from_filename', return_value=os.path.basename(self.test_file.name)) as mock_remove_root_dir_from_filename:
                        with mock.patch('services.source_code_model.indexer.clang_indexer.index_single_file', return_value=True) as mock_index_single_file:
                            manager.attach_mock(mock_symbol_db_open, 'mock_symbol_db_open')
                            manager.attach_mock(mock_symbol_db_delete_entry, 'mock_symbol_db_delete_entry')
                            manager.attach_mock(mock_remove_root_dir_from_filename, 'mock_remove_root_dir_from_filename')
                            manager.attach_mock(mock_index_single_file, 'mock_index_single_file')
                            success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE, self.test_file.name])
        manager.assert_has_calls(
            [
                mock.call.mock_symbol_db_open(self.service.symbol_db_path),
                mock.call.mock_remove_root_dir_from_filename(self.root_directory, self.test_file.name),
                mock.call.mock_symbol_db_delete_entry(mock_remove_root_dir_from_filename.return_value),
                mock.call.mock_index_single_file(self.service.parser, self.service.root_directory, self.test_file.name, self.service.symbol_db)
            ]
        )
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_single_file_deletes_an_entry_from_symbol_db_using_its_basename_and_then_failes_to_index_the_file(self):
        manager = mock.MagicMock()
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_entry') as mock_symbol_db_delete_entry:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.remove_root_dir_from_filename', return_value=os.path.basename(self.test_file.name)) as mock_remove_root_dir_from_filename:
                        with mock.patch('services.source_code_model.indexer.clang_indexer.index_single_file', return_value=False) as mock_index_single_file:
                            manager.attach_mock(mock_symbol_db_open, 'mock_symbol_db_open')
                            manager.attach_mock(mock_symbol_db_delete_entry, 'mock_symbol_db_delete_entry')
                            manager.attach_mock(mock_remove_root_dir_from_filename, 'mock_remove_root_dir_from_filename')
                            manager.attach_mock(mock_index_single_file, 'mock_index_single_file')
                            success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_SINGLE_FILE, self.test_file.name])
            manager.assert_has_calls(
                [
                    mock.call.mock_symbol_db_open(self.service.symbol_db_path),
                    mock.call.mock_remove_root_dir_from_filename(self.root_directory, self.test_file.name),
                    mock.call.mock_symbol_db_delete_entry(mock_remove_root_dir_from_filename.return_value),
                    mock.call.mock_index_single_file(self.service.parser, self.service.root_directory, self.test_file.name, self.service.symbol_db)
                ]
            )
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_run_on_directory_checks_for_symbol_db_schema_change(self):
        with mock.patch.object(self.service, 'symbol_db_schema_changed', return_value=False) as mock_symbol_db_schema_changed:
            with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
                success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_schema_changed.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_directory_drops_the_db_when_symbol_db_schema_gets_changed(self):
        with mock.patch.object(self.service, 'symbol_db_schema_changed', return_value=True) as mock_symbol_db_schema_changed:
            with mock.patch.object(self.service, '_ClangIndexer__drop_all') as mock_drop_all:
                with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
                    success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_schema_changed.assert_called_once()
        mock_drop_all.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_directory_skips_indexing_if_symbol_db_already_exists_in_root_directory(self):
        with mock.patch.object(self.service, 'symbol_db_schema_changed', return_value=False) as mock_symbol_db_schema_changed:
            with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
                with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                    with mock.patch.object(self.service.symbol_db, 'create_data_model') as mock_symbol_db_create_data_model:
                        success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_open.assert_not_called()
        mock_symbol_db_create_data_model.assert_not_called()
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_directory_creates_a_list_of_cpp_files_wrt_blacklisted_directories(self):
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'create_data_model') as mock_symbol_db_create_data_model:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.get_cpp_file_list', return_value=[]) as mock_get_cpp_file_list:
                        success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_open.assert_called_once_with(self.service.symbol_db_path)
        mock_symbol_db_create_data_model.assert_called_once()
        mock_get_cpp_file_list.assert_called_once_with(self.service.root_directory, self.service.blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_directory_handles_when_there_are_no_files_existing_in_root_directory(self):
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'create_data_model') as mock_symbol_db_create_data_model:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.get_cpp_file_list', return_value=[]) as mock_get_cpp_file_list:
                        success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_open.assert_called_once_with(self.service.symbol_db_path)
        mock_symbol_db_create_data_model.assert_called_once()
        mock_get_cpp_file_list.assert_called_once_with(self.service.root_directory, self.service.blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_run_on_directory_handles_when_cpp_file_chunk_list_contains_none_items(self):
        import multiprocessing, logging, subprocess
        logging.getLoggerClass().root.handlers[0].baseFilename = 'log_file'
        dummy_cmd = 'cd'
        cpp_file_list = ['/tmp/a.cpp', '/tmp/b.cpp', '/tmp/c.cpp', '/tmp/d.cpp', '/tmp/e.cpp', '/tmp/f.cpp', '/tmp/g.cpp']
        cpp_file_list_chunks = [[cpp_file_list[0], cpp_file_list[1]], [cpp_file_list[2], cpp_file_list[3]], [cpp_file_list[4], cpp_file_list[5]], [cpp_file_list[6], None]]
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'create_data_model') as mock_symbol_db_create_data_model:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.get_cpp_file_list', return_value=cpp_file_list) as mock_get_cpp_file_list:
                        with mock.patch('services.source_code_model.indexer.clang_indexer.slice_it', return_value=cpp_file_list_chunks) as mock_slice_it, \
                            mock.patch('services.source_code_model.indexer.clang_indexer.create_indexer_input_list_file', return_value=(None, 'indexer_input_list_file',)) as mock_create_indexer_input_list_file, \
                            mock.patch('services.source_code_model.indexer.clang_indexer.create_empty_symbol_db', return_value=(None, 'empty_symbol_db_filename',)) as mock_create_empty_symbol_db, \
                            mock.patch('services.source_code_model.indexer.clang_indexer.start_indexing_subprocess', return_value=subprocess.Popen(dummy_cmd)) as mock_start_indexing_subprocess, \
                            mock.patch('subprocess.Popen.wait') as mock_subprocess_wait, \
                            mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.copy_all_entries_from') as mock_symbol_db_copy_all_entries_from, \
                            mock.patch('os.remove') as mock_os_remove:
                            success, args = self.service([SourceCodeModelIndexerRequestId.RUN_ON_DIRECTORY])
        mock_symbol_db_open.assert_called_once_with(self.service.symbol_db_path)
        mock_symbol_db_create_data_model.assert_called_once()
        mock_get_cpp_file_list.assert_called_once_with(self.service.root_directory, self.service.blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        mock_slice_it.assert_called_once_with(cpp_file_list, old_div(len(cpp_file_list),multiprocessing.cpu_count()))
        mock_create_indexer_input_list_file.assert_called_with(self.service.root_directory, mock.ANY, mock_slice_it.return_value[len(cpp_file_list_chunks)-1])
        mock_create_empty_symbol_db.assert_called_with(self.service.root_directory, self.service.symbol_db_name)
        mock_start_indexing_subprocess.assert_called_with(self.service.root_directory, self.txt_compilation_database.name, mock_create_indexer_input_list_file.return_value[1], mock_create_empty_symbol_db.return_value[1], mock.ANY)
        mock_symbol_db_copy_all_entries_from.assert_called_once()
        self.assertEqual(mock_create_indexer_input_list_file.call_count, len(cpp_file_list_chunks))
        self.assertEqual(mock_create_empty_symbol_db.call_count, len(cpp_file_list_chunks))
        self.assertEqual(mock_start_indexing_subprocess.call_count, len(cpp_file_list_chunks))
        self.assertEqual(mock_os_remove.call_count, 2*len(cpp_file_list_chunks))
        self.assertEqual(mock_subprocess_wait.call_count, len(cpp_file_list_chunks))
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_drop_single_file_skips_deleting_an_entry_if_symbol_db_is_inexisting(self):
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_entry') as mock_symbol_db_delete_entry:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.remove_root_dir_from_filename', return_value=os.path.basename(self.test_file.name)) as mock_remove_root_dir_from_filename:
                        success, args = self.service([SourceCodeModelIndexerRequestId.DROP_SINGLE_FILE, self.test_file.name])
        mock_symbol_db_open.assert_not_called()
        mock_symbol_db_delete_entry.assert_not_called()
        mock_remove_root_dir_from_filename.assert_not_called()
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_drop_single_file_skips_deleting_an_entry_when_file_is_in_blacklisted_directory(self):
        self.service.blacklisted_directories.append(os.path.dirname(self.test_file.name))
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_entry') as mock_symbol_db_delete_entry:
                    success, args = self.service([SourceCodeModelIndexerRequestId.DROP_SINGLE_FILE, self.test_file.name])
        self.service.blacklisted_directories.pop()
        mock_symbol_db_open.assert_not_called()
        mock_symbol_db_delete_entry.assert_not_called()
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_drop_single_file_deletes_an_entry_from_symbol_db(self):
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_entry') as mock_symbol_db_delete_entry:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.remove_root_dir_from_filename', return_value=os.path.basename(self.test_file.name)) as mock_remove_root_dir_from_filename:
                        success, args = self.service([SourceCodeModelIndexerRequestId.DROP_SINGLE_FILE, self.test_file.name])
        mock_symbol_db_open.assert_called_with(self.service.symbol_db_path)
        mock_symbol_db_delete_entry.assert_called_once_with(mock_remove_root_dir_from_filename.return_value)
        mock_remove_root_dir_from_filename.assert_called_once_with(self.root_directory, self.test_file.name)
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_drop_all_skips_deleting_all_entries_if_symbol_db_is_inexisting(self):
        delete_from_disk = False
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_all_entries') as mock_symbol_db_delete_all_entries:
                    success, args = self.service([SourceCodeModelIndexerRequestId.DROP_ALL, delete_from_disk])
        mock_symbol_db_open.assert_not_called()
        mock_symbol_db_delete_all_entries.assert_not_called()
        self.assertEqual(success, False)
        self.assertEqual(args, None)

    def test_if_drop_all_deletes_all_entries_from_symbol_db_but_does_not_delete_the_db_from_disk(self):
        delete_from_disk = False
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_all_entries') as mock_symbol_db_delete_all_entries:
                    with mock.patch.object(self.service.symbol_db, 'close') as mock_symbol_db_close:
                        with mock.patch('os.remove') as mock_os_remove:
                            success, args = self.service([SourceCodeModelIndexerRequestId.DROP_ALL, delete_from_disk])
        mock_symbol_db_open.assert_called_with(self.service.symbol_db_path)
        mock_symbol_db_delete_all_entries.assert_called_once()
        mock_symbol_db_close.assert_not_called()
        mock_os_remove.assert_not_called()
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_drop_all_does_not_delete_all_entries_from_symbol_db_but_deletes_the_db_from_disk(self):
        delete_from_disk = True
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'delete_all_entries') as mock_symbol_db_delete_all_entries:
                    with mock.patch.object(self.service.symbol_db, 'close') as mock_symbol_db_close:
                        with mock.patch('os.remove') as mock_os_remove:
                            success, args = self.service([SourceCodeModelIndexerRequestId.DROP_ALL, delete_from_disk])
        mock_symbol_db_open.assert_not_called()
        mock_symbol_db_delete_all_entries.assert_not_called()
        mock_symbol_db_close.assert_called_once()
        mock_os_remove.assert_called_once_with(self.service.symbol_db.filename)
        self.assertEqual(success, True)
        self.assertEqual(args, None)

    def test_if_find_all_references_returns_false_and_empty_references_list_on_inexisting_symbol_db(self):
        line, column = 1, 1
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            with mock.patch.object(self.service.parser, 'parse') as mock_parser_parse:
                with mock.patch.object(self.service.parser, 'get_cursor') as mock_parser_get_cursor:
                    success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_not_called()
        mock_parser_get_cursor.assert_not_called()
        self.assertEqual(success, False)
        self.assertEqual(len(references), 0)

    def test_if_find_all_references_returns_false_and_empty_references_list_for_invalid_translation_unit(self):
        line, column = 1, 1
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.parser, 'parse', return_value=None) as mock_parser_parse:
                success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        self.assertEqual(success, False)
        self.assertEqual(len(references), 0)

    def test_if_find_all_references_returns_false_and_empty_references_list_for_invalid_cursor(self):
        line, column = 1, 1
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.parser, 'parse') as mock_parser_parse:
                with mock.patch.object(self.service.parser, 'get_cursor', return_value=None) as mock_parser_get_cursor:
                    success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_get_cursor.assert_called_once_with(mock_parser_parse.return_value, line, column)
        self.assertEqual(success, False)
        self.assertEqual(len(references), 0)

    def test_if_find_all_references_returns_true_and_empty_references_list_when_run_on_symbol_which_does_not_have_any_occurence_in_symbol_db(self):
        line, column = 1, 1
        rows = []
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.parser, 'parse') as mock_parser_parse:
                with mock.patch.object(self.service.parser, 'get_cursor') as mock_parser_get_cursor:
                    with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                        with mock.patch.object(self.service.symbol_db, 'fetch_symbols_by_usr', return_value=rows) as mock_symbol_db_fetch_symbols_by_usr:
                            success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_get_cursor.assert_called_once_with(mock_parser_parse.return_value, line, column)
        mock_symbol_db_open.assert_called_with(self.service.symbol_db_path)
        mock_symbol_db_fetch_symbols_by_usr.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(len(references), 0)

    def test_if_find_all_references_returns_true_and_non_empty_references_list_when_run_on_symbol_which_has_occurences_in_symbol_db(self):
        line, column = 1, 1
        rows = [['main.cpp', '22', '5', 'main.cpp#l22#c5#foobar', '    void foobar() {']]
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.parser, 'parse') as mock_parser_parse:
                with mock.patch.object(self.service.parser, 'get_cursor') as mock_parser_get_cursor:
                    with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                        with mock.patch.object(self.service.symbol_db, 'fetch_symbols_by_usr', return_value=rows) as mock_symbol_db_fetch_symbols_by_usr:
                            success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_get_cursor.assert_called_once_with(mock_parser_parse.return_value, line, column)
        mock_symbol_db_open.assert_called_with(self.service.symbol_db_path)
        mock_symbol_db_fetch_symbols_by_usr.assert_called_once()
        self.assertEqual(success, True)
        self.assertNotEqual(len(references), 0)

    def test_if_find_all_references_returns_true_and_in_non_empty_references_filename_columns_are_prepended_with_root_directory(self):
        line, column = 1, 1
        rows = [['main.cpp', '22', '5', 'main.cpp#l22#c5#foobar', '    void foobar() {']]
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.parser, 'parse') as mock_parser_parse:
                with mock.patch.object(self.service.parser, 'get_cursor') as mock_parser_get_cursor:
                    with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                        with mock.patch.object(self.service.symbol_db, 'fetch_symbols_by_usr', return_value=rows) as mock_symbol_db_fetch_symbols_by_usr:
                            success, references = self.service([SourceCodeModelIndexerRequestId.FIND_ALL_REFERENCES, self.test_file.name, line, column])
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_get_cursor.assert_called_once_with(mock_parser_parse.return_value, line, column)
        mock_symbol_db_open.assert_called_with(self.service.symbol_db_path)
        mock_symbol_db_fetch_symbols_by_usr.assert_called_once()
        self.assertEqual(success, True)
        self.assertNotEqual(len(references), 0)
        filename = references[0][0]
        self.assertEqual(filename.startswith(self.root_directory), True)

    def test_if_fetch_all_diagnostics_returns_false_and_empty_diagnostics_list_on_inexisting_symbol_db(self):
        sorting_strategy = 0 # No sorting
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=False):
            success, diagnostics = self.service([SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS, sorting_strategy])
        self.assertEqual(success, False)
        self.assertEqual(len(diagnostics), 0)

    def test_if_fetch_all_diagnostics_returns_true_and_empty_diagnostics_list_when_no_diagnostics_are_available_and_does_not_fetch_additional_diagnostics_details(self):
        sorting_strategy = 0 # No sorting
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'fetch_all_diagnostics', return_value=[]) as mock_symbol_db_fetch_all_diagnostics:
                    with mock.patch.object(self.service.symbol_db, 'fetch_diagnostics_details', return_value=[]) as mock_symbol_db_fetch_all_diagnostics_details:
                        success, diagnostics = self.service([SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS, sorting_strategy])
        mock_symbol_db_open.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics_details.assert_not_called()
        self.assertEqual(success, True)
        self.assertEqual(len(diagnostics), 0)

    def test_if_fetch_all_diagnostics_returns_true_and_non_empty_diagnostics_list_and_does_not_fetch_additional_diagnostics_details_because_there_are_no_any(self):
        sorting_strategy = 0 # No sorting
        diagnostics_from_db = [
            [1, 'filename1', 1, 1, 'diag description 1', 1],
            [2, 'filename2', 2, 2, 'diag description 2', 2],
            [3, 'filename3', 3, 3, 'diag description 3', 2],
            [4, 'filename4', 4, 4, 'diag description 4', 3],
            [5, 'filename5', 5, 5, 'diag description 5', 3],
            [6, 'filename6', 6, 6, 'diag description 6', 4],
        ]
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'fetch_all_diagnostics', return_value=diagnostics_from_db) as mock_symbol_db_fetch_all_diagnostics:
                    with mock.patch.object(self.service.symbol_db, 'fetch_diagnostics_details', return_value=[]) as mock_symbol_db_fetch_all_diagnostics_details:
                        success, diagnostics = self.service([SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS, sorting_strategy])
        mock_symbol_db_open.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics_details.assert_not_called()
        self.assertEqual(success, True)
        self.assertEqual(len(diagnostics), len(diagnostics_from_db))

    def test_if_fetch_all_diagnostics_returns_true_and_non_empty_diagnostics_list_and_does_not_fetch_additional_diagnostics_details_because_there_are_no_any(self):
        sorting_strategy = 0 # No sorting
        diagnostics_from_db = [
            [1, 'filename1', 1, 1, 'diag description 1', 1],
            [2, 'filename2', 2, 2, 'diag description 2', 2],
            [3, 'filename3', 3, 3, 'diag description 3', 2],
            [4, 'filename4', 4, 4, 'diag description 4', 3],
            [5, 'filename5', 5, 5, 'diag description 5', 3],
            [6, 'filename6', 6, 6, 'diag description 6', 4],
        ]
        with mock.patch.object(self.service, 'symbol_db_exists', return_value=True):
            with mock.patch.object(self.service.symbol_db, 'open') as mock_symbol_db_open:
                with mock.patch.object(self.service.symbol_db, 'fetch_all_diagnostics', return_value=diagnostics_from_db) as mock_symbol_db_fetch_all_diagnostics:
                    with mock.patch.object(self.service.symbol_db, 'fetch_diagnostics_details', return_value=diagnostics_from_db) as mock_symbol_db_fetch_all_diagnostics_details:
                        success, diagnostics = self.service([SourceCodeModelIndexerRequestId.FETCH_ALL_DIAGNOSTICS, sorting_strategy])
        mock_symbol_db_open.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics.assert_called_once()
        mock_symbol_db_fetch_all_diagnostics_details.assert_called()
        self.assertEqual(mock_symbol_db_fetch_all_diagnostics_details.call_count, len(diagnostics_from_db))
        self.assertEqual(success, True)
        self.assertEqual(len(diagnostics), len(diagnostics_from_db) + len(diagnostics_from_db)**2)

    def test_if_index_file_list_runs_indexing_for_each_of_the_files_given(self):
        input_filename_list = ['/tmp/a.cpp', '/tmp/b.cpp', '/tmp/c.cpp', '/tmp/d.cpp', '/tmp/e.cpp', '/tmp/f.cpp', '/tmp/g.cpp']
        output_db_filename = 'out.db'
        manager = mock.MagicMock()
        with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.create_data_model') as mock_symbol_db_create_data_model, \
            mock.patch('services.source_code_model.indexer.clang_indexer.ClangParser.__init__', return_value=None) as mock_clang_parser_creation, \
            mock.patch('services.source_code_model.indexer.clang_indexer.TranslationUnitCache') as mock_translation_unit_cache, \
            mock.patch('services.source_code_model.indexer.clang_indexer.NoCache') as mock_translation_unit_no_cache_strategy, \
            mock.patch('services.source_code_model.indexer.clang_indexer.index_single_file') as mock_index_single_file, \
            mock.patch('__builtin__.open', mock.mock_open(read_data='\n'.join(input_filename_list)), create=True), \
            mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.close') as mock_symbol_db_close:
                manager.attach_mock(mock_index_single_file, 'mock_index_single_file')
                index_file_list(self.root_directory, 'file_containing_list_of_files_to_be_indexed', self.txt_compilation_database.name, output_db_filename)
        mock_symbol_db_create_data_model.assert_called_once()
        mock_clang_parser_creation.assert_called_once_with(self.txt_compilation_database.name, mock.ANY) # TODO how to test/mock against NoCache() temp object
        mock_translation_unit_cache.assert_called_once()
        mock_translation_unit_no_cache_strategy.assert_called_once()
        self.assertEqual(mock_index_single_file.call_count, len(input_filename_list))
        manager.assert_has_calls(
            [
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[0], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[1], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[2], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[3], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[4], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[5], mock.ANY
                ),
                mock.call.mock_index_single_file(
                    mock.ANY, self.root_directory,
                    input_filename_list[6], mock.ANY
                )
            ]
        )
        mock_symbol_db_close.assert_called_once()

    def test_if_index_single_file_returns_true_traverses_the_ast_tree_stores_tunit_diagnostics_and_flushes_the_symbol_db(self):
        symbol_db = SymbolDatabase('tmp.db')
        with mock.patch.object(self.parser, 'parse') as mock_parser_parse:
            with mock.patch.object(self.parser, 'traverse') as mock_parser_traverse:
                with mock.patch('services.source_code_model.indexer.clang_indexer.store_tunit_diagnostics') as mock_store_tunit_diagnostics:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.flush') as mock_symbol_db_flush:
                        ret = index_single_file(self.parser, os.path.dirname(self.test_file.name), self.test_file.name, symbol_db)
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_traverse.assert_called_once_with(mock_parser_parse.return_value.cursor, [self.parser, symbol_db, self.root_directory], indexer_visitor)
        mock_store_tunit_diagnostics.assert_called_once_with(mock_parser_parse.return_value.diagnostics, symbol_db, self.root_directory)
        mock_symbol_db_flush.assert_called_once()
        self.assertEqual(ret, True)

    def test_if_index_single_file_returns_false_and_does_not_continue_traversing_or_storing_tunit_diagnostics_for_invalid_tunit(self):
        symbol_db = SymbolDatabase('tmp.db')
        with mock.patch.object(self.parser, 'parse', return_value=None) as mock_parser_parse:
            with mock.patch.object(self.parser, 'traverse') as mock_parser_traverse:
                with mock.patch('services.source_code_model.indexer.clang_indexer.store_tunit_diagnostics') as mock_store_tunit_diagnostics:
                    with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.flush') as mock_symbol_db_flush:
                        ret = index_single_file(self.parser, os.path.dirname(self.test_file.name), self.test_file.name, symbol_db)
        mock_parser_parse.assert_called_once_with(self.test_file.name, self.test_file.name)
        mock_parser_traverse.assert_not_called()
        mock_store_tunit_diagnostics.assert_not_called()
        mock_symbol_db_flush.assert_not_called()
        self.assertEqual(ret, False)

    def test_if_indexer_visitor_inserts_a_single_entry_to_symbol_db_for_ast_node_from_tunit_under_test_and_recurses_further(self):
        import linecache
        line, column = 10, 15
        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, line, column))
        translation_unit_mock = cxxd_mocks.TranslationUnitMock(self.test_file.name)
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        type(ast_node).translation_unit = translation_unit_mock
        type(ast_node).referenced = None
        ast_node._kind_id = clang.cindex.CursorKind.CLASS_DECL
        symbol_db = SymbolDatabase('tmp.db')
        args = [self.parser, symbol_db, self.root_directory]
        with mock.patch.object(self.parser, 'get_ast_node_id', return_value=ClangIndexer.supported_ast_node_ids[0]):
            with mock.patch.object(symbol_db, 'insert_symbol_entry') as mock_symbol_db_insert_symbol_entry:
                with mock.patch.object(ast_node, 'get_usr', return_value='#usr#of#some#symbol') as mock_clang_cursor_get_usr:
                    with mock.patch.object(ast_node, 'is_definition', return_value=True) as mock_clang_cursor_is_definition:
                        with mock.patch('services.source_code_model.indexer.clang_indexer.remove_root_dir_from_filename', return_value=os.path.basename(self.test_file.name)) as mock_remove_root_dir_from_filename:
                            ret = indexer_visitor(ast_node, None, args)
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.RECURSE.value)
        mock_remove_root_dir_from_filename.assert_called_once_with(self.root_directory, translation_unit_mock.spelling)
        mock_symbol_db_insert_symbol_entry.assert_called_once_with(
            mock_remove_root_dir_from_filename.return_value,
            line, column,
            mock_clang_cursor_get_usr.return_value,
            linecache.getline(self.test_file.name, line),
            ast_node._kind_id,
            mock_clang_cursor_is_definition.return_value
        )

    def test_if_indexer_visitor_does_not_insert_an_entry_to_symbol_db_for_unsupported_ast_node_and_recurses_further(self):
        line, column = 10, 15
        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, line, column))
        translation_unit_mock = cxxd_mocks.TranslationUnitMock(self.test_file.name)
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        type(ast_node).translation_unit = translation_unit_mock
        symbol_db = SymbolDatabase('tmp.db')
        args = [self.parser, symbol_db, self.root_directory]
        with mock.patch.object(self.parser, 'get_ast_node_id', return_value=self.unsupported_ast_node_ids[0]) as mock_get_ast_node_id:
            with mock.patch.object(symbol_db, 'insert_symbol_entry') as mock_symbol_db_insert_symbol_entry:
                ret = indexer_visitor(ast_node, None, args)
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.RECURSE.value)
        mock_get_ast_node_id.assert_called_once()
        mock_symbol_db_insert_symbol_entry.assert_not_called()

    def test_if_indexer_visitor_does_not_insert_an_entry_to_symbol_db_for_ast_node_from_another_tunit_and_does_not_recurse_further(self):
        line, column = 10, 15
        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, line, column))
        translation_unit_mock = cxxd_mocks.TranslationUnitMock('some_other_tunit')
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        type(ast_node).translation_unit = translation_unit_mock
        symbol_db = SymbolDatabase('tmp.db')
        args = [self.parser, symbol_db, self.root_directory]
        with mock.patch.object(symbol_db, 'insert_symbol_entry') as mock_symbol_db_insert_symbol_entry:
            ret = indexer_visitor(ast_node, None, args)
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.CONTINUE.value)
        mock_symbol_db_insert_symbol_entry.assert_not_called()

    def test_if_store_tunit_diagnostics_creates_diagnostics_entry_and_no_diagnostics_details_entry_in_symbol_db(self):
        symbol_db = SymbolDatabase('tmp.db')
        diagnostics = [
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 1, 1), 'missing ;', 4, []
            ),
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 2, 2), 'include file not found', 4, []
            ),
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 10, 10), 'implicit narrowing cast from int to short int', 3, []
            ),
        ]
        translation_unit_mock = cxxd_mocks.TranslationUnitMock('some_tunit_with_diagnostics', diagnostics)
        with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.insert_diagnostics_entry') as mock_symbol_db_insert_diagnostics_entry:
            with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.insert_diagnostics_details_entry') as mock_symbol_db_insert_diagnostics_details_entry:
                ret = store_tunit_diagnostics(translation_unit_mock.diagnostics, symbol_db, self.root_directory)
        mock_symbol_db_insert_diagnostics_entry.assert_called()
        self.assertEqual(mock_symbol_db_insert_diagnostics_entry.call_count, len(diagnostics))
        mock_symbol_db_insert_diagnostics_details_entry.assert_not_called()

    def test_if_store_tunit_diagnostics_creates_diagnostics_entry_and_diagnostics_details_entry_in_symbol_db(self):
        symbol_db = SymbolDatabase('tmp.db')
        diag_child_1 = cxxd_mocks.DiagnosticMock(
            cxxd_mocks.SourceLocationMock('some_other_filename_1.cpp', 1, 5), 'missing ;', 4, []
        )
        diag_child_2 = cxxd_mocks.DiagnosticMock(
            cxxd_mocks.SourceLocationMock('some_other_filename_2.cpp', 2, 2), 'include file not found', 4, []
        )
        diag_child_3 = cxxd_mocks.DiagnosticMock(
            cxxd_mocks.SourceLocationMock('some_other_filename_3.cpp', 5, 4), 'implicit narrowing cast from int to short int', 3, []
        )
        diag_child_4 = cxxd_mocks.DiagnosticMock(
            cxxd_mocks.SourceLocationMock('some_other_filename_4.cpp', 8, 2), 'implicit narrowing cast from int to short int', 3, []
        )
        diagnostics = [
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 1, 1), 'missing ;', 4, [diag_child_1, diag_child_2, diag_child_3, diag_child_4]
            ),
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 2, 2), 'include not found', 5, [diag_child_2, diag_child_3]
            ),
            cxxd_mocks.DiagnosticMock(
                cxxd_mocks.SourceLocationMock(self.test_file.name, 10, 10), 'implicit narrowing cast from int to short int', 3, [diag_child_1, diag_child_2, diag_child_3]
            ),
        ]
        translation_unit_mock = cxxd_mocks.TranslationUnitMock('some_tunit_with_diagnostics', diagnostics)
        with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.insert_diagnostics_entry') as mock_symbol_db_insert_diagnostics_entry:
            with mock.patch('services.source_code_model.indexer.clang_indexer.SymbolDatabase.insert_diagnostics_details_entry') as mock_symbol_db_insert_diagnostics_details_entry:
                ret = store_tunit_diagnostics(translation_unit_mock.diagnostics, symbol_db, self.root_directory)
        mock_symbol_db_insert_diagnostics_entry.assert_called()
        self.assertEqual(mock_symbol_db_insert_diagnostics_entry.call_count, len(diagnostics))
        mock_symbol_db_insert_diagnostics_details_entry.assert_called()
        self.assertEqual(mock_symbol_db_insert_diagnostics_details_entry.call_count, len(diagnostics[0].children + diagnostics[1].children + diagnostics[2].children))

    def test_if_remove_root_dir_from_filename_returns_basename_without_root_dir_and_without_path_separator(self):
        self.assertEqual(remove_root_dir_from_filename('/home/user/project_root_dir/', '/home/user/project_root_dir/lib/impl.cpp'), 'lib/impl.cpp')

    def test_if_get_clang_index_path_returns_a_valid_path(self):
        self.assertTrue(os.path.exists(get_clang_index_path()))

    def test_if_get_cpp_file_list_returns_cpp_files_only(self):
        blacklisted_directories = []
        os_walk_dir_list = (self.root_directory)
        os_walk_file_list = ('/tmp/a.cpp', '/tmp/b.cc', '/tmp/c.cxx', '/tmp/d.c', '/tmp/e.h', '/tmp/f.hh', '/tmp/g.hpp')
        with mock.patch('os.walk', return_value=[(self.root_directory, os_walk_dir_list, os_walk_file_list),]) as mock_os_walk:
            cpp_list = get_cpp_file_list(self.root_directory, blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        mock_os_walk.assert_called_once_with(self.root_directory)
        self.assertEqual(len(os_walk_file_list), len(cpp_list))

    def test_if_get_cpp_file_list_does_not_include_non_cpp_files(self):
        blacklisted_directories = []
        os_walk_dir_list = (self.root_directory)
        os_walk_file_list = ('/tmp/a.md', '/tmp/b.txt', '/tmp/c.json')
        with mock.patch('os.walk', return_value=[(self.root_directory, os_walk_dir_list, os_walk_file_list),]) as mock_os_walk:
            cpp_list = get_cpp_file_list(self.root_directory, blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        mock_os_walk.assert_called_once_with(self.root_directory)
        self.assertEqual(0, len(cpp_list))

    def test_if_get_cpp_file_list_returns_empty_list_for_no_files_found(self):
        blacklisted_directories = []
        os_walk_dir_list = (self.root_directory)
        os_walk_file_list = ()
        with mock.patch('os.walk', return_value=[(self.root_directory, os_walk_dir_list, os_walk_file_list),]) as mock_os_walk:
            cpp_list = get_cpp_file_list(self.root_directory, blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        mock_os_walk.assert_called_once_with(self.root_directory)
        self.assertEqual(0, len(cpp_list))

    def test_if_get_cpp_file_list_only_returns_cpp_files_which_are_not_in_blacklisted_directories(self):
        blacklisted_directories = ['/tmp']
        os_walk_dir_list = (self.root_directory)
        os_walk_file_list = ('/home/1.cpp', '/home/2.cpp', '/home/3.cpp', '/tmp/4.cpp')
        with mock.patch('os.walk', return_value=[(self.root_directory, os_walk_dir_list, os_walk_file_list),]) as mock_os_walk:
            cpp_list = get_cpp_file_list(self.root_directory, blacklisted_directories, self.service.recognized_file_extensions + self.service.extra_file_extensions)
        mock_os_walk.assert_called_once_with(self.root_directory)
        self.assertEqual(len(os_walk_file_list)-1, len(cpp_list))

    def test_if_get_cpp_file_list_returns_files_with_non_standard_extension(self):
        blacklisted_directories = []
        extra_file_extensions = ['.ic', '.i', '.tcc', '.txx']
        os_walk_dir_list = (self.root_directory)
        os_walk_file_list = ('/tmp/a.cpp', '/tmp/b.ic', '/tmp/c.i', '/tmp/d.tcc', '/tmp/e.txx')
        with mock.patch('os.walk', return_value=[(self.root_directory, os_walk_dir_list, os_walk_file_list),]) as mock_os_walk:
            cpp_list = get_cpp_file_list(self.root_directory, blacklisted_directories, self.service.recognized_file_extensions + extra_file_extensions)
        mock_os_walk.assert_called_once_with(self.root_directory)
        self.assertEqual(len(os_walk_file_list), len(cpp_list))

    def test_if_create_indexer_input_list_file_creates_a_file_containing_newline_separated_list_of_files_with_given_prefix_in_given_directory(self):
        input_list_prefix = 'input_list_0'
        cpp_file_list = ['/tmp/a.cpp', '/tmp/b.cpp', '/tmp/c.cpp', '/tmp/d.cpp', '/tmp/e.cpp', '/tmp/f.cpp', '/tmp/g.cpp']
        cpp_files_newline_separated = '/tmp/a.cpp\n/tmp/b.cpp\n/tmp/c.cpp\n/tmp/d.cpp\n/tmp/e.cpp\n/tmp/f.cpp\n/tmp/g.cpp'
        with mock.patch('tempfile.mkstemp', return_value=(None, None)) as mock_mkstemp:
            with mock.patch('os.write') as mock_os_write:
                create_indexer_input_list_file(self.root_directory, input_list_prefix, cpp_file_list)
        mock_mkstemp.assert_called_once_with(prefix=input_list_prefix, dir=self.root_directory)
        mock_os_write.assert_called_once_with(mock.ANY, cpp_files_newline_separated)

    def test_if_create_indexer_input_list_file_creates_a_file_containing_newline_separated_list_of_files_with_given_prefix_in_given_directory_and_can_handle_none_items_in_the_list(self):
        input_list_prefix = 'input_list_0'
        cpp_file_list = ['/tmp/a.cpp', '/tmp/b.cpp', '/tmp/c.cpp', '/tmp/d.cpp', '/tmp/e.cpp', '/tmp/f.cpp', '/tmp/g.cpp', None]
        cpp_files_newline_separated = '/tmp/a.cpp\n/tmp/b.cpp\n/tmp/c.cpp\n/tmp/d.cpp\n/tmp/e.cpp\n/tmp/f.cpp\n/tmp/g.cpp'
        with mock.patch('tempfile.mkstemp', return_value=(None, None)) as mock_mkstemp:
            with mock.patch('os.write') as mock_os_write:
                create_indexer_input_list_file(self.root_directory, input_list_prefix, cpp_file_list)
        mock_mkstemp.assert_called_once_with(prefix=input_list_prefix, dir=self.root_directory)
        mock_os_write.assert_called_once_with(mock.ANY, cpp_files_newline_separated)

    def test_if_create_empty_symbol_db_creates_an_empty_file_with_given_prefix_in_given_directory(self):
        symbol_db_prefix = 'tmp_symbol_db'
        with mock.patch('tempfile.mkstemp', return_value=(None, None)) as mock_mkstemp:
            create_empty_symbol_db(self.root_directory, symbol_db_prefix)
        mock_mkstemp.assert_called_once_with(prefix=symbol_db_prefix, dir=self.root_directory)

    def test_if_start_indexing_subprocess_invokes_correctly_clang_index_script(self):
        indexer_input_filename = 'input0'
        output_db_filename = 'output0.db'
        log_filename = 'log.txt'
        expected_cmd = 'python2 ' + \
            get_clang_index_path() + \
            ' --project_root_directory=\'' + self.root_directory + \
            '\' --compiler_args_filename=\'' + self.txt_compilation_database.name + \
            '\' --input_list=\'' + indexer_input_filename + \
            '\' --output_db_filename=\'' + output_db_filename + \
            '\' --log_file=\'' + log_filename + '\''
        with mock.patch('shlex.split') as mock_shlex_split:
            with mock.patch('subprocess.Popen') as mock_subprocess_popen:
                start_indexing_subprocess(self.root_directory, self.txt_compilation_database.name, indexer_input_filename, output_db_filename, log_filename)
        mock_shlex_split.assert_called_once_with(expected_cmd)
        mock_subprocess_popen.assert_called_once()

# TODO fuzz the ClangIndexer interface ...
