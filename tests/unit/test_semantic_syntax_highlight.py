from __future__ import absolute_import
import clang.cindex
import mock
import unittest

from  import cxxd_mocks
import parser.ast_node_identifier
import parser.clang_parser
import parser.tunit_cache
from services.source_code_model.semantic_syntax_highlight.semantic_syntax_highlight import semantic_syntax_highlight_visitor
from file_generator import FileGenerator

class SemanticSyntaxHighlightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_file                    = FileGenerator.gen_simple_cpp_file()
        cls.test_file_with_includes_only = FileGenerator.gen_header_file_containing_includes_only()
        cls.txt_compilation_database     = FileGenerator.gen_txt_compilation_database()
        cls.line_begin                   = 1
        cls.line_end                     = 20

        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.test_file)
        FileGenerator.close_gen_file(cls.test_file_with_includes_only)
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        from services.source_code_model.semantic_syntax_highlight.semantic_syntax_highlight import SemanticSyntaxHighlight
        self.service = SemanticSyntaxHighlight(self.parser)

    def test_if_call_returns_true_and_ast_tree_traversal_callback_does_not_take_place_for_unsupported_ast_nodes(self):
        success, [tunit, line_begin, line_end, ast_traversal_fun] = self.service([self.test_file.name, self.test_file.name, self.line_begin, self.line_end])
        self.assertEqual(success, True)
        self.assertEqual(self.line_begin, line_begin)
        self.assertEqual(self.line_end, line_end)
        self.assertNotEqual(tunit, None)
        self.assertNotEqual(ast_traversal_fun, None)

    def test_if_semantic_syntax_highlight_visitor_does_not_recurse_into_symbols_from_other_tunits(self):
        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, 10, 15))
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        tunit_spelling = 'some_other_tunit_different_from_test_file'
        ret = semantic_syntax_highlight_visitor(ast_node, ast_parent_node=None, data=(self.parser, tunit_spelling, self.line_begin, self.line_end, None, None,))
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.CONTINUE.value)

    def test_if_semantic_syntax_highlight_visitor_does_not_invoke_client_callback_for_unsupported_ast_nodes(self):
        def client_callback(id, name, line, column, client_data):
            self.assertEqual(False, True) # we shouldn't get here

        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, 10, 15))
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        tunit_spelling = self.test_file.name
        with mock.patch.object(self.parser, 'get_ast_node_id', return_value=parser.ast_node_identifier.ASTNodeId.getUnsupportedId()) as mock_get_ast_node_id:
            ret = semantic_syntax_highlight_visitor(ast_node, ast_parent_node=None, data=(self.parser, tunit_spelling, self.line_begin, self.line_end, client_callback, None,))
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.RECURSE.value)
 
    def test_if_semantic_syntax_highlight_visitor_invokes_client_callback_for_supported_ast_nodes(self):
        def client_callback(id, name, line, column, client_data):
            self.assertEqual(id, parser.ast_node_identifier.ASTNodeId.getClassId())
            self.assertEqual(line, 10)
            self.assertEqual(column, 15)
            self.assertEqual(client_data, None)

        location_mock = mock.PropertyMock(return_value=cxxd_mocks.SourceLocationMock(self.test_file.name, 10, 15))
        ast_node = mock.MagicMock(clang.cindex.Cursor)
        type(ast_node).location = location_mock
        tunit_spelling = self.test_file.name
        with mock.patch.object(self.parser, 'get_ast_node_id', return_value=parser.ast_node_identifier.ASTNodeId.getClassId()) as mock_get_ast_node_id:
            ret = semantic_syntax_highlight_visitor(ast_node, ast_parent_node=None, data=(self.parser, tunit_spelling, self.line_begin, self.line_end, client_callback, None,))
        self.assertEqual(ret, parser.clang_parser.ChildVisitResult.RECURSE.value)
 
if __name__ == '__main__':
    unittest.main()
