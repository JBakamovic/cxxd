
import logging
import cxxd.parser.clang_parser
import cxxd.parser.tunit_cache
import cxxd.service
from code_completion.code_completion import CodeCompletion as CodeCompletionImpl

class CodeCompletion(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.configuration = cxxd_config_parser.get_configuration_for_target(target)

    def startup_callback(self, args):
        self.parser = cxxd.parser.clang_parser.ClangParser(
            self.configuration,
            cxxd.parser.tunit_cache.TranslationUnitCache(cxxd.parser.tunit_cache.FifoCache(20))
        )
        self.code_completion = CodeCompletionImpl(self.parser)
        logging.info('Code-completion service started.')
        return True, []

    def shutdown_callback(self, args):
        logging.info('Code-completion service stopped.')
        return True, []

    def __call__(self, args):
        return self.code_completion(args)
