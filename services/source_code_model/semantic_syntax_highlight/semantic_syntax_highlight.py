from builtins import str
from builtins import object
import logging
from cxxd.parser.ast_node_identifier import ASTNodeId
from cxxd.parser.clang_parser import ChildVisitResult

class SemanticSyntaxHighlight(object):
    def __init__(self, parser):
        self.parser = parser

    def __traverse__(self, tunit, line_begin, line_end, callback, client_data):
        self.parser.traverse(tunit.cursor, (self.parser, tunit.spelling, line_begin, line_end, callback, client_data), semantic_syntax_highlight_visitor)

    def __call__(self, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line_begin = int(args[2])
        line_end = int(args[3])

        tunit = self.parser.parse(contents_filename, original_filename)
        return tunit is not None, [tunit, line_begin, line_end, self.__traverse__]

def semantic_syntax_highlight_visitor(ast_node, ast_parent_node, data):
    parser, tunit_spelling, line_begin, line_end, client_callback, client_data = data
    if ast_node.location.file and ast_node.location.file.name == tunit_spelling:  # we're only interested in symbols from associated translation unit
        ast_node_line = parser.get_ast_node_line(ast_node)
        if ast_node_line >= line_begin and ast_node_line <= line_end:
            ast_node_id = parser.get_ast_node_id(ast_node)
            if ast_node_id != ASTNodeId.getUnsupportedId():
                client_callback(
                    ast_node_id,
                    parser.get_ast_node_name(ast_node),
                    ast_node_line,
                    parser.get_ast_node_column(ast_node),
                    client_data
                )
            else:
                logging.debug("Unsupported token id: [{0}, {1}]: {2} '{3}'".format(
                        ast_node.location.line, ast_node.location.column,
                        ast_node.kind, ast_node.spelling
                    )
                )
        elif ast_node_line > line_end:
            return ChildVisitResult.BREAK.value # It means we're done and we don't need to waste any more time traversing till the end of TU
        else:
            pass
        return ChildVisitResult.RECURSE.value  # If we are positioned in TU of interest, then we'll traverse through all descendants
    return ChildVisitResult.CONTINUE.value  # Otherwise, we'll skip to the next sibling

