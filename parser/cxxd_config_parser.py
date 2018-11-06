import json
import logging
import os

class CxxdConfigParser():
    def __init__(self, cxxd_config_filename):
        self.blacklisted_directories = []
        self.clang_tidy_args         = []
        self.clang_format_args       = []
        self.project_builder_args    = []
        if os.path.exists(cxxd_config_filename):
            with open(cxxd_config_filename) as f:
                config = json.load(f)
                self.blacklisted_directories = self._extract_blacklisted_directories(
                    config, os.path.dirname(os.path.realpath(cxxd_config_filename))
                )
                self.clang_tidy_args = self._extract_clang_tidy_args(config)
                self.clang_format_args = self._extract_clang_format_args(config)
                self.project_builder_args = self._extract_project_builder_args(config)
        logging.info('Blacklisted directories {0}'.format(self.blacklisted_directories))
        logging.info('Clang-tidy args {0}'.format(self.clang_tidy_args))
        logging.info('Clang-format args {0}'.format(self.clang_format_args))
        logging.info('Project-builder args {0}'.format(self.project_builder_args))

    def get_blacklisted_directories(self):
        return self.blacklisted_directories

    def get_clang_tidy_args(self):
        return self.clang_tidy_args

    def get_clang_format_args(self):
        return self.clang_format_args

    def get_project_builder_args(self):
        return self.project_builder_args

    @staticmethod
    def is_file_blacklisted(directory_list, filename):
        for dir in directory_list:
            if filename.startswith(dir):
                return True
        return False

    def _extract_blacklisted_directories(self, config, base_dir):
        dirs = [os.path.join(base_dir, dir) for dir in config['indexer']['exclude-dirs']]
        return dirs

    def _extract_clang_tidy_args(self, config):
        args = []
        for arg, value in config['clang-tidy']['args'].iteritems():
            args.append((arg, value),)
        return args

    def _extract_clang_format_args(self, config):
        args = []
        for arg, value in config['clang-format']['args'].iteritems():
            args.append((arg, value),)
        return args

    def _extract_project_builder_args(self, config):
        args = []
        for arg, value in config['project-builder']['args'].iteritems():
            args.append((arg, value),)
        return args
