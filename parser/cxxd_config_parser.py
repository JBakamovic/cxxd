import distutils.spawn
import json
import logging
import os

class CxxdConfigParser():
    def __init__(self, cxxd_config_filename, project_root_directory):
        self.try_harder_search_paths = [
            '.', 'build', 'build_cmake', 'cmake_build', \
            'debug', 'dbg', 'release', 'rel', 'relwithdbg', 'minsizerel',
            '../build', '../build_cmake', '../cmake_build',
            '../debug', '../dbg', '../release', '../rel', '../relwithdbg', '../minsizerel'
        ]
        self.configuration_type = 'auto-discovery-try-harder' # This is the default mode even when there is NO configuration file
        self.configuration_selected = None
        self.indexer_blacklisted_directories = []
        self.indexer_extra_file_extensions = []
        self.clang_tidy_args = []
        self.clang_tidy_binary_path = None
        self.clang_format_args = []
        self.clang_format_binary_path = None
        self.disassembly_intermix_with_src_code = None
        self.disassembly_visualize_jumps = None
        self.disassembly_syntax = None
        self.disassembly_binary_path = None
        self.disassembly_targets_filter = None
        self.nm_binary_path = None
        self.project_builder_args = []
        self.project_builder_targets = []
        self.project_root_directory = project_root_directory
        self.clang_library_file = None
        if os.path.exists(cxxd_config_filename):
            with open(cxxd_config_filename) as f:
                config = json.load(f)
                self.configuration_type = self._extract_configuration_type(config)
                self.configuration_selected = self._extract_configuration_selected(config, self.configuration_type)
                self.indexer_blacklisted_directories = self._extract_indexer_blacklisted_directories(
                    config, os.path.dirname(os.path.realpath(cxxd_config_filename))
                )
                self.indexer_extra_file_extensions = self._extract_indexer_extra_file_extensions(config)
                self.clang_tidy_args = self._extract_clang_tidy_args(config)
                self.clang_tidy_binary_path = self._extract_clang_tidy_binary_path(config)
                self.clang_format_args = self._extract_clang_format_args(config)
                self.clang_format_binary_path = self._extract_clang_format_binary_path(config)
                self.clang_library_file = self._extract_clang_library_file(config)
                self.disassembly_intermix_with_src_code = self._extract_disassembly_intermix_with_src_code(config)
                self.disassembly_visualize_jumps = self._extract_disassembly_visualize_jumps(config)
                self.disassembly_syntax = self._extract_disassembly_syntax(config)
                self.disassembly_binary_path = self._extract_disassembly_binary_path(config)
                self.disassembly_targets_filter = self._extract_disassembly_targets_filter(config)
                self.nm_binary_path = self._extract_nm_binary_path(config)
                self.project_builder_args = self._extract_project_builder_args(config)
                self.project_builder_targets = self._extract_project_builder_targets(config)
        if not self.clang_tidy_binary_path:
            self.clang_tidy_binary_path = self._find_system_wide_binary('clang-tidy')
        if not self.clang_format_binary_path:
            self.clang_format_binary_path = self._find_system_wide_binary('clang-format')
        if not self.disassembly_binary_path:
            self.disassembly_binary_path = self._find_system_wide_binary('objdump')
        if not self.nm_binary_path:
            self.nm_binary_path = self._find_system_wide_binary('nm')
        logging.info('Configuration: Type {0}'.format(self.configuration_type))
        logging.info('Configuration: Selected {0}'.format(self.configuration_selected))
        logging.info('Indexer: Blacklisted directories {0}'.format(self.indexer_blacklisted_directories))
        logging.info('Indexer: Extra file extensions {0}'.format(self.indexer_extra_file_extensions))
        logging.info('Clang-tidy args {0}'.format(self.clang_tidy_args))
        logging.info('Clang-tidy binary path {0}'.format(self.clang_tidy_binary_path))
        logging.info('Clang-format args {0}'.format(self.clang_format_args))
        logging.info('Clang-format binary path {0}'.format(self.clang_format_binary_path))
        logging.info('Disassembly intermix with source code {0}'.format(self.disassembly_intermix_with_src_code != None))
        logging.info('Disassembly visualize jumps {0}'.format(self.disassembly_visualize_jumps != None))
        logging.info('Disassembly syntax {0}'.format(self.disassembly_syntax if self.disassembly_syntax != None else ''))
        logging.info('Disassembly binary path {0}'.format(self.disassembly_binary_path))
        logging.info('Disassembly targets filter {0}'.format(self.disassembly_targets_filter))
        logging.info('nm binary path {0}'.format(self.nm_binary_path))
        logging.info('Clang library-file {0}'.format(self.clang_library_file))
        logging.info('Project-builder args {0}'.format(self.project_builder_args))
        logging.info('Project-builder targets {0}'.format(self.project_builder_targets))

    def get_configuration_type(self):
        return self.configuration_type;

    def get_configuration_for_target(self, target):
        return self._extract_configuration_for_target(self.configuration_selected, self.configuration_type, target)

    def get_blacklisted_directories(self):
        return self.indexer_blacklisted_directories

    def get_extra_file_extensions(self):
        return self.indexer_extra_file_extensions

    def get_clang_tidy_args(self):
        return self.clang_tidy_args

    def get_clang_tidy_binary_path(self):
        return self.clang_tidy_binary_path

    def get_clang_format_args(self):
        return self.clang_format_args

    def get_clang_format_binary_path(self):
        return self.clang_format_binary_path

    def get_clang_library_file(self):
        return self.clang_library_file

    def get_disassembly_intermix_with_src_code(self):
        return self.disassembly_intermix_with_src_code

    def get_disassembly_visualize_jumps(self):
        return self.disassembly_visualize_jumps

    def get_disassembly_syntax(self):
        return self.disassembly_syntax

    def get_disassembly_binary_path(self):
        return self.disassembly_binary_path

    def get_nm_binary_path(self):
        return self.nm_binary_path

    def get_disassembly_targets_filter(self):
        return self.disassembly_targets_filter

    def get_project_builder_args(self):
        return self.project_builder_args

    def get_common_cpp_file_extensions(self):
        return ['.cpp', '.cxx', '.cc', '.c', '.h', '.hh', '.hpp', '.hxx', '.tpp']

    def get_project_cpp_file_extensions(self):
        return self.get_common_cpp_file_extensions() + self.get_extra_file_extensions()

    def get_project_builder_build_cmd(self, target):
        return self._extract_project_builder_build_cmd(self.project_builder_targets, target)

    def get_project_builder_build_dir(self, target):
        return self._extract_project_builder_build_dir(self.configuration_selected, target)

    @staticmethod
    def is_file_blacklisted(directory_list, filename):
        for dir in directory_list:
            if filename.startswith(dir):
                return True
        return False

    def _find_system_wide_binary(self, binary_name):
        return distutils.spawn.find_executable(binary_name)

    def _extract_configuration_selected(self, config, config_type):
        config_selected = None
        if 'configuration' in config:
            if config_type in config['configuration']:
                config_selected = config['configuration'][config_type]
        return config_selected

    def _extract_configuration_type(self, config):
        config_type = None
        if 'configuration' in config:
            if 'type' in config['configuration']:
                cfg_type = config['configuration']['type']
                if cfg_type in ['compilation-database', 'compile-flags', 'auto-discovery']:
                    config_type = cfg_type
                else:
                    logging.fatal('Invalid configuration-type. Must be one of {compilation-database | compile-flags | auto-discovery}.')
            else:
                config_type = 'auto-discovery-try-harder'
        else:
            config_type = 'auto-discovery-try-harder'

        if config_type == 'auto-discovery-try-harder':
            logging.warning('No configuration-type found! Falling back to auto-discovery-try-harder mode which will try to auto-detect'
                            'the configuration file on the following hard-coded search-paths: \'{0}\'.'.format(self.try_harder_search_paths))
            logging.warning('It is recommended though to define configuration-type yourself providing correct search paths through .cxxd_config.json file.')

        return config_type

    def _extract_configuration_for_target(self, config, config_type, target):
        configuration = None
        if config_type in ['compilation-database', 'compile-flags']:
            if config and 'target' in config:
                if target in config['target']:
                    path = os.path.join(self.project_root_directory, config['target'][target])
                    if os.path.isdir(path):
                        comp_db = os.path.join(path, 'compile_commands.json')
                        comp_flags = os.path.join(path, 'compile_flags.txt')
                        if os.path.isfile(comp_db):
                            configuration = comp_db
                        elif os.path.isfile(comp_flags):
                            configuration = comp_flags
                        else:
                            logging.error('Neither \'compile_commands.json\' nor \'compile_flags.txt\' were found under {0}'.format(path))
        elif config_type in ['auto-discovery']:
            if config and 'search-paths' in config:
                for path in config['search-paths']:
                    path = os.path.join(self.project_root_directory, path)
                    logging.fatal('Looking at {0} path'.format(path))
                    if os.path.isdir(path):
                        comp_db = os.path.join(path, 'compile_commands.json')
                        comp_flags = os.path.join(path, 'compile_flags.txt')
                        if os.path.isfile(comp_db):
                            configuration = comp_db
                            logging.info('Auto-discovery mode: found \'compile_commands.json\' under {0}'.format(path))
                            break
                        elif os.path.isfile(comp_flags):
                            configuration = comp_flags
                            logging.info('Auto-discovery mode: found \'compile_flags.txt\' under {0}'.format(path))
                            break
                        else:
                            logging.info('Auto-discovery mode: nothing found under {0}'.format(path))
                if configuration is None:
                    logging.error('Neither \'compile_commands.json\' nor \'compile_flags.txt\' were found with auto-discovery mode. Make sure one of these files exist on given location(s).')
        elif config_type in ['auto-discovery-try-harder']:
            for path in self.try_harder_search_paths:
                path = os.path.join(self.project_root_directory, path)
                logging.info('Looking at {0} path'.format(path))
                if os.path.isdir(path):
                    comp_db = os.path.join(path, 'compile_commands.json')
                    comp_flags = os.path.join(path, 'compile_flags.txt')
                    if os.path.isfile(comp_db):
                        configuration = comp_db
                        logging.info('Auto-discovery-try-harder mode: found \'compile_commands.json\' under {0}'.format(path))
                        break
                    elif os.path.isfile(comp_flags):
                        configuration = comp_flags
                        logging.info('Auto-discovery-try-harder mode: found \'compile_flags.txt\' under {0}'.format(path))
                        break
                    else:
                        logging.info('Auto-discovery-try-harder mode: nothing found under {0}'.format(path))
            if configuration is None:
                logging.error('Neither \'compile_commands.json\' nor \'compile_flags.txt\' were found with auto-discovery-try-harder mode. Make sure one of these files exist on given location(s).')
        else:
            logging.fatal('Invalid configuration-type. Must be one of {compilation-database | compile-flags | auto-discovery}')
        return configuration

    def _extract_indexer_blacklisted_directories(self, config, base_dir):
        dirs = []
        if 'indexer' in config:
            if 'exclude-dirs' in config['indexer']:
                dirs = [os.path.join(base_dir, dir) for dir in config['indexer']['exclude-dirs']]
        return dirs

    def _extract_indexer_extra_file_extensions(self, config):
        extensions = []
        if 'indexer' in config:
            if 'extra-file-extensions' in config['indexer']:
                extensions = list(config['indexer']['extra-file-extensions'])
        return extensions

    def _extract_clang_tidy_args(self, config):
        args = []
        if 'clang-tidy' in config:
            if 'args' in config['clang-tidy']:
                for arg, value in config['clang-tidy']['args'].items():
                    args.append((arg, value),)
        return args

    def _extract_clang_tidy_binary_path(self, config):
        if 'clang-tidy' in config:
            if 'binary' in config['clang-tidy']:
                return config['clang-tidy']['binary']
        return None

    def _extract_clang_format_args(self, config):
        args = []
        if 'clang-format' in config:
            if 'args' in config['clang-format']:
                for arg, value in config['clang-format']['args'].items():
                    args.append((arg, value),)
        return args

    def _extract_clang_format_binary_path(self, config):
        if 'clang-format' in config:
            if 'binary' in config['clang-format']:
                return config['clang-format']['binary']
        return None

    def _extract_disassembly_intermix_with_src_code(self, config):
        if 'disassembly' in config:
            if 'objdump' in config['disassembly']:
                if 'intermix-with-src-code' in config['disassembly']['objdump']:
                    return config['disassembly']['objdump']['intermix-with-src-code']
        return None

    def _extract_disassembly_visualize_jumps(self, config):
        if 'disassembly' in config:
            if 'objdump' in config['disassembly']:
                if 'visualize-jumps' in config['disassembly']['objdump']:
                    return config['disassembly']['objdump']['visualize-jumps']
        return None

    def _extract_disassembly_syntax(self, config):
        if 'disassembly' in config:
            if 'objdump' in config['disassembly']:
                if 'syntax' in config['disassembly']['objdump']:
                    return config['disassembly']['objdump']['syntax']
        return None

    def _extract_disassembly_binary_path(self, config):
        if 'disassembly' in config:
            if 'objdump' in config['disassembly']:
                if 'binary' in config['disassembly']['objdump']:
                    return config['disassembly']['objdump']['binary']
        return None

    def _extract_nm_binary_path(self, config):
        if 'disassembly' in config:
            if 'nm' in config['disassembly']:
                if 'binary' in config['disassembly']['nm']:
                    return config['disassembly']['nm']['binary']
        return None

    def _extract_disassembly_targets_filter(self, config):
        if 'disassembly' in config:
            if 'targets-filter' in config['disassembly']:
                return config['disassembly']['targets-filter']
        return []

    def _extract_project_builder_args(self, config):
        args = []
        if 'project-builder' in config:
            if 'args' in config['project-builder']:
                for arg, value in config['project-builder']['args'].items():
                    args.append((arg, value),)
        return args

    def _extract_clang_library_file(self, config):
        if 'clang' in config:
            if 'library-file' in config['clang']:
                return config['clang']['library-file']
        return None

    def _extract_project_builder_targets(self, config):
        targets = {}
        if 'project-builder' in config:
            if 'target' in config['project-builder']:
                for target, value in config['project-builder']['target'].items():
                    targets[target] = value
        return targets

    def _extract_project_builder_build_cmd(self, project_builder_targets, target):
        if target in project_builder_targets:
            return project_builder_targets[target]['cmd']
        return None

    def _extract_project_builder_build_dir(self, configuration_selected, target):
        if target in configuration_selected['target']:
            return configuration_selected['target'][target]
        return None
