import json
import logging
import os
import cxxd.parser.clang_parser
import cxxd.parser.tunit_cache
import cxxd.service
from source_code_model.semantic_syntax_highlight.semantic_syntax_highlight import SemanticSyntaxHighlight
from source_code_model.diagnostics.diagnostics import Diagnostics
from source_code_model.indexer.clang_indexer import ClangIndexer
from source_code_model.type_deduction.type_deduction import TypeDeduction
from source_code_model.go_to_definition.go_to_definition import GoToDefinition
from source_code_model.go_to_include.go_to_include import GoToInclude

class SourceCodeModelSubServiceId():
    INDEXER                   = 0x0
    SEMANTIC_SYNTAX_HIGHLIGHT = 0x1
    DIAGNOSTICS               = 0x2
    TYPE_DEDUCTION            = 0x3
    GO_TO_DEFINITION          = 0x4
    GO_TO_INCLUDE             = 0x5

class SourceCodeModel(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.parser = cxxd.parser.clang_parser.ClangParser(
            cxxd_config_parser.get_configuration_for_target(target),
            cxxd.parser.tunit_cache.TranslationUnitCache(cxxd.parser.tunit_cache.FifoCache(20))
        )
        self.clang_indexer = ClangIndexer(self.parser, self.project_root_directory, self.cxxd_config_parser)
        self.service = {
            SourceCodeModelSubServiceId.INDEXER                   : self.clang_indexer,
            SourceCodeModelSubServiceId.SEMANTIC_SYNTAX_HIGHLIGHT : SemanticSyntaxHighlight(self.parser),
            SourceCodeModelSubServiceId.DIAGNOSTICS               : Diagnostics(self.parser),
            SourceCodeModelSubServiceId.TYPE_DEDUCTION            : TypeDeduction(self.parser),
            SourceCodeModelSubServiceId.GO_TO_DEFINITION          : GoToDefinition(self.parser, self.clang_indexer.get_symbol_db(), self.project_root_directory),
            SourceCodeModelSubServiceId.GO_TO_INCLUDE             : GoToInclude(self.parser)
        }

    def __unknown_service(self, args):
        logging.error("Unknown service triggered! Valid services are: {0}".format(self.service))
        return False, None

    def startup_callback(self, args):
        pass

    def shutdown_callback(self, args):
        pass

    def __call__(self, args):
        return self.service.get(int(args[0]), self.__unknown_service)(args[1:len(args)])
