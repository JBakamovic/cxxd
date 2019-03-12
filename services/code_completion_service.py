import logging
import cxxd.parser.clang_parser
import cxxd.parser.tunit_cache
import cxxd.service
from source_code_model.auto_completion.auto_completion import AutoCompletion

class CodeCompletion(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.parser = None
        self.code_completion = None

    def startup_callback(self, args):
        compiler_args_filename = str(args[0])
        self.parser = cxxd.parser.clang_parser.ClangParser(
            compiler_args_filename,
            cxxd.parser.tunit_cache.TranslationUnitCache(cxxd.parser.tunit_cache.FifoCache(20))
        )
        self.code_completion = AutoCompletion(self.parser)
        logging.info('Code-completion service started.')

    def shutdown_callback(self, args):
        logging.info('Code-completion service stopped.')

    def __call__(self, args):
        return self.code_completion(args)
