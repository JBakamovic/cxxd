import logging
import cxxd.parser.clang_parser
import cxxd.parser.tunit_cache
import cxxd.service
from source_code_model.auto_completion.auto_completion import AutoCompletion

class CodeCompletion(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.configuration = cxxd_config_parser.get_configuration_for_target(target)

    def startup_callback(self, args):
        self.parser = cxxd.parser.clang_parser.ClangParser(
            self.configuration,
            cxxd.parser.tunit_cache.TranslationUnitCache(cxxd.parser.tunit_cache.FifoCache(20))
        )
        self.code_completion = AutoCompletion(self.parser)
        logging.info('Code-completion service started.')

    def shutdown_callback(self, args):
        logging.info('Code-completion service stopped.')

    def __call__(self, args):
        return self.code_completion(args)
