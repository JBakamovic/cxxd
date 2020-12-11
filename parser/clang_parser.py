import clang.cindex
import logging
import os
import sys
from ast_node_identifier import ASTNodeId
from compiler_args import CompilerArgs

class ChildVisitResult(clang.cindex.BaseEnumeration):
    """
    A ChildVisitResult describes how the traversal of the children of a particular cursor should proceed after visiting a particular child cursor.
    """
    _kinds = []
    _name_map = None

    def __repr__(self):
        return 'ChildVisitResult.%s' % (self.name,)

ChildVisitResult.BREAK = ChildVisitResult(0) # Terminates the cursor traversal.
ChildVisitResult.CONTINUE = ChildVisitResult(1) # Continues the cursor traversal with the next sibling of the cursor just visited, without visiting its children.
ChildVisitResult.RECURSE = ChildVisitResult(2) # Recursively traverse the children of this cursor, using the same visitor and client data.

def default_visitor(child, parent, client_data):
    """Default implementation of AST node visitor."""

    return ChildVisitResult.CONTINUE.value

def traverse(cursor, client_data, client_visitor = default_visitor):
    """Traverse AST using the client provided visitor."""

    def visitor(child, parent, client_data):
        assert child != clang.cindex.conf.lib.clang_getNullCursor()
        child._tu = cursor._tu
        child.ast_parent = parent
        return client_visitor(child, parent, client_data)

    return clang.cindex.conf.lib.clang_visitChildren(cursor, clang.cindex.callbacks['cursor_visit'](visitor), client_data)

def get_children_patched(self, traversal_type = ChildVisitResult.CONTINUE):
    """
    Return an iterator for accessing the children of this cursor.
    This is a patched version of Cursor.get_children() but which is built on top of new traversal interface.
    See traverse() for more details.
    """

    def visitor(child, parent, children):
        children.append(child)
        return traversal_type.value

    children = []
    traverse(self, children, visitor)
    return iter(children)

"""
Monkey-patch the existing Cursor.get_children() with get_children_patched().
This is a temporary solution and should be removed once, and if, it becomes available in official libclang Python bindings.
New version provides more functionality (i.e. AST parent node) which is needed in certain cases.
"""
clang.cindex.Cursor.get_children = get_children_patched

class ClangParser():
    def __init__(self, compiler_args_filename, tunit_cache):
        self.index         = clang.cindex.Index.create()
        self.compiler_args = CompilerArgs(compiler_args_filename)
        self.tunit_cache   = tunit_cache
        logging.info("libclang version: '{0}'".format(ClangParser.__get_clang_version()))

    def default_parsing_flags(self):
        # TODO Add support for PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION
        # TODO CXTranslationUnit_KeepGoing?
        return \
            clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD | \
            clang.cindex.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS | \
            clang.cindex.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE | \
            clang.cindex.TranslationUnit.PARSE_INCOMPLETE

    def get_compiler_args_db(self):
        return self.compiler_args

    def code_complete(self, contents_filename, original_filename, line, column, complete_macros=False, complete_lang_constructs=False):
        # Check if TUnit is already cached. If not, we have to parse it first ...
        tunit, tunit_build_flags, tunit_timestamp = self.tunit_cache.fetch(original_filename)
        if tunit is None:
            tunit = self.parse(contents_filename, original_filename)
        # Now, trigger the code-complete on given TUnit ...
        with open(contents_filename) as f:
            return tunit.codeComplete(
                tunit.spelling,
                line,
                column + 1,
                include_macros=complete_macros,
                include_code_patterns=complete_lang_constructs,
                unsaved_files=[(original_filename, f.read()),]
            )

    def sort_code_completion_results(self, auto_completion_candidates):
        _libclang = clang.cindex.conf.get_cindex_library()
        _libclang.clang_sortCodeCompletionResults.argtypes = [clang.cindex.CCRStructure]
        _libclang.clang_sortCodeCompletionResults.restype  = None
        _libclang.clang_sortCodeCompletionResults(auto_completion_candidates.results, len(auto_completion_candidates.results))

    def parse(self, contents_filename, original_filename, opts=None):
        def do_parse(contents_filename, original_filename, build_flags):
            try:
                return self.index.parse(
                    path = contents_filename,
                    args = build_flags,
                    options = self.default_parsing_flags() if opts is None else opts
                )
            except:
                logging.error(sys.exc_info())

        # Check if we have this tunit already in the cache ...
        tunit, tunit_build_flags, tunit_timestamp = self.tunit_cache.fetch(original_filename)
        if tunit is None:
            logging.info('TUnit NOT found in cache!')
            build_flags = self.compiler_args.get(original_filename, contents_filename != original_filename)
            tunit = do_parse(
                contents_filename,
                original_filename,
                build_flags
            )
            if tunit:
                self.tunit_cache.insert(original_filename, tunit, build_flags, os.path.getmtime(original_filename))
        else:
            logging.info('TUnit found in cache!')
            if original_filename != contents_filename:
                new_tunit_timestamp = os.path.getmtime(contents_filename)
                if tunit_timestamp != new_tunit_timestamp:      # We still have to make sure that cached tunit is not out-of-date.
                    logging.info('But it is too old ... reparsing')
                    tunit = do_parse(contents_filename, original_filename, tunit_build_flags)
                    if tunit:
                        self.tunit_cache.insert(original_filename, tunit, tunit_build_flags, os.path.getmtime(tunit.spelling))
                    #with open(contents_filename) as f:
                    #    tunit.reparse([(original_filename, f.read()),])
                    #    self.tunit_cache.update(original_filename, tunit, new_tunit_timestamp)

        return tunit

    def get_diagnostics(self, tunit):
        if not tunit:
            return None

        diag = tunit.diagnostics
        logging.info("Fetching diagnostics for {0}: {1}".format(tunit.spelling, diag))
        return diag

    def get_top_level_includes(self, tunit):
        def visitor(cursor, parent, include_directives_list):
            if cursor.location.file and cursor.location.file.name == tunit.spelling:  # we're only interested in symbols from associated translation unit
                if cursor.kind == clang.cindex.CursorKind.INCLUSION_DIRECTIVE:
                    included_file_name = ClangParser.__get_included_file_name(cursor)
                    if included_file_name:
                        include_directives_list.append((included_file_name, cursor.location.line, cursor.location.column),)
                return ChildVisitResult.CONTINUE.value  # We don't want to waste time traversing recursively for include directives
            return ChildVisitResult.CONTINUE.value

        top_level_includes = []
        if tunit:
            traverse(tunit.cursor, top_level_includes, visitor)
        logging.info(top_level_includes)
        return top_level_includes

    def traverse(self, cursor, client_data, client_visitor):
        traverse(cursor, client_data, client_visitor)

    def get_ast_node_id(self, cursor):
        # We have to handle (at least) two different situations when libclang API will not give us enough details about the given cursor directly:
        #   1. When Cursor.TypeKind is DEPENDENT
        #       * Cursor.TypeKind happens to be set to DEPENDENT for constructs whose semantics may differ from one
        #         instantiation to another. These are called dependent names (see 14.6.2 [temp.dep] in C++ standard).
        #       * Example can be a call expression on non-instantiated function template, or even a reference to
        #         a data member of non-instantiated class template.
        #       * In this case we try to extract the right CursorKind by tokenizing the given cursor, selecting the
        #         right token and, depending on its position in the AST tree, return the right CursorKind information.
        #         See ClangParser.__extract_dependent_type_kind() for more details.
        #       * Similar actions have to be taken for extracting spelling and location for such cursors.
        #   2. When Cursor.Kind is OVERLOADED_DECL_REF
        #       * Cursor.Kind.OVERLOADED_DECL_REF basically identifies a reference to a set of overloaded functions
        #         or function templates which have not yet been resolved to a specific function or function template.
        #       * This means that token kind might be one of the following:
        #            Cursor.Kind.FUNCTION_DECL, Cursor.Kind.FUNCTION_TEMPLATE, Cursor.Kind.CXX_METHOD
        #       * To extract more information about the token we can use `clang_getNumOverloadedDecls()` to get how
        #         many overloads there are and then use `clang_getOverloadedDecl()` to get a specific overload.
        #       * In our case, we can always use the first overload which explains hard-coded 0 as an index.
        if cursor.type.kind == clang.cindex.TypeKind.DEPENDENT:
            return ClangParser.to_ast_node_id(ClangParser.__extract_dependent_type_kind(cursor))
        else:
            if cursor.referenced:
                if (cursor.referenced.kind == clang.cindex.CursorKind.OVERLOADED_DECL_REF):
                    if (ClangParser.__get_num_overloaded_decls(cursor.referenced)):
                        return ClangParser.to_ast_node_id(ClangParser.__get_overloaded_decl(cursor.referenced, 0).kind)
                return ClangParser.to_ast_node_id(cursor.referenced.kind)
            if (cursor.kind == clang.cindex.CursorKind.OVERLOADED_DECL_REF):
                if (ClangParser.__get_num_overloaded_decls(cursor)):
                    return ClangParser.to_ast_node_id(ClangParser.__get_overloaded_decl(cursor, 0).kind)
        return ClangParser.to_ast_node_id(cursor.kind)

    def get_ast_node_name(self, cursor):
        if cursor.type.kind == clang.cindex.TypeKind.DEPENDENT:
            return ClangParser.__extract_dependent_type_spelling(cursor)
        else:
            if (cursor.referenced):
                return cursor.referenced.spelling
            else:
                return cursor.spelling

    def get_ast_node_line(self, cursor):
        if cursor.type.kind == clang.cindex.TypeKind.DEPENDENT:
            return ClangParser.__extract_dependent_type_location(cursor).line
        return cursor.location.line

    def get_ast_node_column(self, cursor):
        if cursor.type.kind == clang.cindex.TypeKind.DEPENDENT:
            return ClangParser.__extract_dependent_type_location(cursor).column
        return cursor.location.column

    def get_cursor(self, tunit, line, column):
        if not tunit:
            return None

        logging.info("Extracting cursor from [{0}, {1}]: {2}.".format(line, column, tunit.spelling))
        cursor = clang.cindex.Cursor.from_location(
                    tunit,
                    clang.cindex.SourceLocation.from_position(
                        tunit,
                        clang.cindex.File.from_name(tunit, tunit.spelling),
                        line,
                        column
                    )
                 )
        return cursor

    def get_definition(self, cursor):
        if cursor:
            logging.info("Extracting definition of cursor from '{0}': [{1},{2}] '{3}'.".format(
                cursor.location.file.name, cursor.location.line, cursor.location.column, cursor.spelling)
            )
            return cursor.get_definition()
        return None

    def dump_tokens(self, cursor):
        for token in cursor.get_tokens():
            logging.debug(
                '%-22s' % ('[' + str(token.extent.start.line) + ', ' + str(token.extent.start.column) + ']:[' + str(token.extent.end.line) + ', ' + str(token.extent.end.column) + ']') +
                '%-30s' % token.spelling +
                '%-40s' % str(token.kind) +
                '%-40s' % str(token.cursor.kind) +
                'Token.Cursor.Extent %-25s' % ('[' + str(token.cursor.extent.start.line) + ', ' + str(token.cursor.extent.start.column) + ']:[' + str(token.cursor.extent.end.line) + ', ' + str(token.cursor.extent.end.column) + ']') +
                'Cursor.Extent %-25s' % ('[' + str(cursor.extent.start.line) + ', ' + str(cursor.extent.start.column) + ']:[' + str(cursor.extent.end.line) + ', ' + str(cursor.extent.end.column) + ']'))

    def dump_ast_nodes(self, tunit):
        def visitor(ast_node, ast_parent_node, client_data):
            if ast_node.location.file and ast_node.location.file.name == tunit.spelling:  # we're only interested in symbols from given file
                # if ast_node.kind in [clang.cindex.CursorKind.CALL_EXPR, clang.cindex.CursorKind.MEMBER_REF_EXPR]:
                #    self.dump_tokens(ast_node)

                logging.debug(
                    '%-12s' % ('[' + str(ast_node.location.line) + ', ' + str(ast_node.location.column) + ']') +
                    '%-25s' % ('[' + str(ast_node.extent.start.line) + ', ' + str(ast_node.extent.start.column) + ']:[' + str(ast_node.extent.end.line) + ', ' + str(ast_node.extent.end.column) + ']') +
                    '%-40s' % str(ast_node.spelling) +
                    '%-40s' % str(ast_node.kind) +
                    '%-40s' % str(ast_parent_node.kind) +
                    '%-40s' % str(ast_node.type.spelling) +
                    '%-40s' % str(ast_node.type.kind) +
                    ('%-25s' % ('[' + str(ast_node.type.get_declaration().location.line) + ', ' + str(ast_node.type.get_declaration().location.column) + ']') if (ast_node.type and ast_node.type.get_declaration()) else '%-25s' % '-') +
                    ('%-25s' % ('[' + str(ast_node.get_definition().location.line) + ', ' + str(ast_node.get_definition().location.column) + ']') if (ast_node.get_definition()) else '%-25s' % '-') +
                    '%-40s' % str(ast_node.get_usr()) +
                    ('%-40s' % str(ClangParser.__get_overloaded_decl(ast_node, 0).spelling) if (ast_node.kind ==
                        clang.cindex.CursorKind.OVERLOADED_DECL_REF and ClangParser.__get_num_overloaded_decls(ast_node)) else '%-40s' % '-') +
                    ('%-40s' % str(ClangParser.__get_overloaded_decl(ast_node, 0).kind) if (ast_node.kind ==
                        clang.cindex.CursorKind.OVERLOADED_DECL_REF and ClangParser.__get_num_overloaded_decls(ast_node)) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.spelling) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.kind) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.type.spelling) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.type.kind) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.result_type.spelling) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.result_type.kind) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.canonical.spelling) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.canonical.kind) if (ast_node.referenced) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.semantic_parent.spelling) if (ast_node.referenced and ast_node.referenced.semantic_parent) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.semantic_parent.kind) if (ast_node.referenced and ast_node.referenced.semantic_parent) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.lexical_parent.spelling) if (ast_node.referenced and ast_node.referenced.lexical_parent) else '%-40s' % '-') +
                    ('%-40s' % str(ast_node.referenced.lexical_parent.kind) if (ast_node.referenced and ast_node.referenced.lexical_parent) else '%-40s' % '-') +
                    ('%-25s' % ('[' + str(ast_node.referenced.type.get_declaration().location.line) + ', ' + str(ast_node.referenced.type.get_declaration().location.column) + ']')
                        if (ast_node.referenced and ast_node.referenced.type and ast_node.referenced.type.get_declaration()) else '%-25s' % '-') +
                    ('%-25s' % ('[' + str(ast_node.referenced.get_definition().location.line) + ', ' + str(ast_node.referenced.get_definition().location.column) + ']')
                        if (ast_node.referenced and ast_node.referenced.get_definition()) else '%-25s' % '-') +
                    ('%-40s' % str(ast_node.referenced.get_usr()) if ast_node.referenced else '%-40s' % '-')
                )
                return ChildVisitResult.RECURSE.value  # If we are positioned in TU of interest, then we'll traverse through all descendants
            return ChildVisitResult.CONTINUE.value  # Otherwise, we'll skip to the next sibling


        if tunit:
            logging.debug(
                '%-12s' % '[Line, Col]' +
                '%-25s' % 'Extent' +
                '%-40s' % 'Spelling' +
                '%-40s' % 'Kind' +
                '%-40s' % 'Parent.Kind' +
                '%-40s' % 'Type.Spelling' +
                '%-40s' % 'Type.Kind' +
                '%-25s' % 'Declaration.Location' +
                '%-25s' % 'Definition.Location' +
                '%-40s' % 'USR' +
                '%-40s' % 'OverloadedDecl' + '%-40s' % 'NumOverloadedDecls' +
                '%-40s' % 'Referenced.Spelling' + '%-40s' % 'Referenced.Kind' +
                '%-40s' % 'Referenced.Type.Spelling' + '%-40s' % 'Referenced.Type.Kind' +
                '%-40s' % 'Referenced.ResultType.Spelling' + '%-40s' % 'Referenced.ResultType.Kind' +
                '%-40s' % 'Referenced.Canonical.Spelling' + '%-40s' % 'Referenced.Canonical.Kind' +
                '%-40s' % 'Referenced.SemanticParent.Spelling' + '%-40s' % 'Referenced.SemanticParent.Kind' +
                '%-40s' % 'Referenced.LexicalParent.Spelling' + '%-40s' % 'Referenced.LexicalParent.Kind' +
                '%-25s' % 'Referenced.Declaration.Location' +
                '%-25s' % 'Referenced.Definition.Location' +
                '%-25s' % 'Referenced.USR'
            )

            logging.debug('----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------')
            self.traverse(tunit.cursor, None, visitor)

    @staticmethod
    def __extract_dependent_type_kind(cursor):
        # For cursors whose CursorKind is MEMBER_REF_EXPR and whose TypeKind is DEPENDENT we don't get much information
        # from libclang API directly (i.e. cursor spelling will be empty).
        # Instead, we can extract such information indirectly by:
        #   1. Tokenizing the cursor
        #       * It will contain all the tokens that make up the MEMBER_REF_EXPR and therefore all the spellings, locations, extents, etc.
        #   2. Finding a token whose:
        #       * TokenKind is IDENTIFIER
        #       * CursorKind of a cursor that it corresponds to matches the MEMBER_REF_EXPR
        #       * Extent of a cursor that it corresponds to matches the extent of original cursor
        #   3. If CursorKind of original cursor AST parent is CALL_EXPR then we know that token found is CursorKind.CXX_METHOD
        #      If CursorKind of original cursor AST parent is not CALL_EXPR then we know that token found is CursorKind.FIELD_DECL
        assert cursor.type.kind == clang.cindex.TypeKind.DEPENDENT
        if cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
            # TODO It seems that there's no libclang-level API to retrieve the parent of given cursor.
            #      Issue can be worked around by storing a parent-node information during the AST traversal but that implies
            #      that we have to traverse the AST in order to have that information. That is not going to be true for
            #      use-cases where we simply want to extract information from given cursor without going into the
            #      traversal itself.
            if hasattr(cursor, 'ast_parent') and (cursor.ast_parent.kind == clang.cindex.CursorKind.CALL_EXPR):
                for token in cursor.get_tokens():
                    if (token.kind == clang.cindex.TokenKind.IDENTIFIER) and (token.cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR) and (token.cursor.extent == cursor.extent):
                        return clang.cindex.CursorKind.CXX_METHOD # We've got a function member call
            else:
                for token in cursor.get_tokens():
                    if (token.kind == clang.cindex.TokenKind.IDENTIFIER) and (token.cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR) and (token.cursor.extent == cursor.extent):
                        return clang.cindex.CursorKind.FIELD_DECL # We've got a data member
        return cursor.kind

    @staticmethod
    def __extract_dependent_type_spelling(cursor):
        # See __extract_dependent_type_kind() for more details but in essence we have to tokenize the cursor and
        # return the spelling of appropriate token.
        assert cursor.type.kind == clang.cindex.TypeKind.DEPENDENT
        if cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
            for token in cursor.get_tokens():
                if (token.kind == clang.cindex.TokenKind.IDENTIFIER) and (token.cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR) and (token.cursor.extent == cursor.extent):
                    return token.spelling
        return cursor.spelling

    @staticmethod
    def __extract_dependent_type_location(cursor):
        # See __extract_dependent_type_kind() for more details but in essence we have to tokenize the cursor and
        # return the location of appropriate token.
        assert cursor.type.kind == clang.cindex.TypeKind.DEPENDENT
        if cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
            for token in cursor.get_tokens():
                if (token.kind == clang.cindex.TokenKind.IDENTIFIER) and (token.cursor.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR) and (token.cursor.extent == cursor.extent):
                    return token.location
        return cursor.location

    @staticmethod
    def to_ast_node_id(kind):
        if (kind == clang.cindex.CursorKind.NAMESPACE):
            return ASTNodeId.getNamespaceId()
        if (kind in [clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.CLASS_TEMPLATE, clang.cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]):
            return ASTNodeId.getClassId()
        if (kind == clang.cindex.CursorKind.STRUCT_DECL):
            return ASTNodeId.getStructId()
        if (kind == clang.cindex.CursorKind.ENUM_DECL):
            return ASTNodeId.getEnumId()
        if (kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL):
            return ASTNodeId.getEnumValueId()
        if (kind == clang.cindex.CursorKind.UNION_DECL):
            return ASTNodeId.getUnionId()
        if (kind == clang.cindex.CursorKind.FIELD_DECL):
            return ASTNodeId.getFieldId()
        if (kind == clang.cindex.CursorKind.VAR_DECL):
            return ASTNodeId.getLocalVariableId()
        if (kind in [clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.FUNCTION_TEMPLATE]):
            return ASTNodeId.getFunctionId()
        if (kind in [clang.cindex.CursorKind.CXX_METHOD, clang.cindex.CursorKind.CONSTRUCTOR, clang.cindex.CursorKind.DESTRUCTOR]):
            return ASTNodeId.getMethodId()
        if (kind == clang.cindex.CursorKind.PARM_DECL):
            return ASTNodeId.getFunctionParameterId()
        if (kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER):
            return ASTNodeId.getTemplateTypeParameterId()
        if (kind == clang.cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER):
            return ASTNodeId.getTemplateNonTypeParameterId()
        if (kind == clang.cindex.CursorKind.TEMPLATE_TEMPLATE_PARAMETER):
            return ASTNodeId.getTemplateTemplateParameterId()
        if (kind == clang.cindex.CursorKind.MACRO_DEFINITION):
            return ASTNodeId.getMacroDefinitionId()
        if (kind == clang.cindex.CursorKind.MACRO_INSTANTIATION):
            return ASTNodeId.getMacroInstantiationId()
        if (kind in [clang.cindex.CursorKind.TYPEDEF_DECL, clang.cindex.CursorKind.TYPE_ALIAS_DECL]):
            return ASTNodeId.getTypedefId()
        if (kind == clang.cindex.CursorKind.NAMESPACE_ALIAS):
            return ASTNodeId.getNamespaceAliasId()
        if (kind == clang.cindex.CursorKind.USING_DIRECTIVE):
            return ASTNodeId.getUsingDirectiveId()
        if (kind == clang.cindex.CursorKind.USING_DECLARATION):
            return ASTNodeId.getUsingDeclarationId()
        return ASTNodeId.getUnsupportedId()

    # TODO Shall be removed once 'cindex.py' exposes it in its interface.
    @staticmethod
    def __get_num_overloaded_decls(cursor):
        return clang.cindex.conf.lib.clang_getNumOverloadedDecls(cursor)

    # TODO Shall be removed once 'cindex.py' exposes it in its interface.
    @staticmethod
    def __get_overloaded_decl(cursor, num):
        return clang.cindex.conf.lib.clang_getOverloadedDecl(cursor, num)

    # TODO Shall be removed once 'cindex.py' exposes it in its interface.
    @staticmethod
    def __get_included_file_name(inclusion_directive_cursor):
        #
        # NOTE Python binding for clang_getIncludedFile() is currently
        #      incompatible with the implementation of clang.cindex.File.
        #      Assert is being risen because clang.cindex.File object is
        #      being constructed with the type which is not of ClangObject
        #      type (e.g. clang.cindex.Cursor is ctypes.Structure)
        #
        #      This implementation workarounds this limitation.
        #
        _libclang = clang.cindex.conf.get_cindex_library()
        _libclang.clang_getIncludedFile.argtypes = [clang.cindex.Cursor]
        _libclang.clang_getIncludedFile.restype  =  clang.cindex.c_object_p
        _libclang.clang_getFileName.argtypes     = [clang.cindex.c_object_p]
        _libclang.clang_getFileName.restype      =  clang.cindex._CXString

        return clang.cindex.conf.lib.clang_getCString(
            _libclang.clang_getFileName(
                _libclang.clang_getIncludedFile(
                    inclusion_directive_cursor
                )
            )
        )

    @staticmethod
    def __get_clang_version():
        # NOTE There is no API exposed for getting the version in libclang Python
        #      bindings so we do it by ourselves here.
        _libclang = clang.cindex.conf.get_cindex_library()
        _libclang.clang_getClangVersion.argtypes = None
        _libclang.clang_getClangVersion.restype  = clang.cindex._CXString

        return clang.cindex.conf.lib.clang_getCString(
            _libclang.clang_getClangVersion()
        )

