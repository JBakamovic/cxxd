import os
import tempfile
import unittest

import cxxd_mocks
from file_generator import FileGenerator
from parser.cxxd_config_parser import CxxdConfigParser

class CxxdConfigParserWithNonEmptyConfigFileAndCompilationDb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                    = 'debug'
        cls.json_compilation_database = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.cxxd_config               = FileGenerator.gen_cxxd_config_filename(cls.target, os.path.dirname(cls.json_compilation_database.name))
        cls.project_root_directory    = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.json_compilation_database)
        FileGenerator.close_gen_file(cls.cxxd_config)

    def setUp(self):
        self.parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)

    def test_if_cxxd_config_parser_returns_compilation_database_type(self):
        self.assertEqual(self.parser.get_configuration_type(), 'compilation-database')

    def test_if_cxxd_config_parser_returns_configuration_for_given_target(self):
        self.assertEqual(os.path.normpath(self.parser.get_configuration_for_target(self.target)), self.json_compilation_database.name)

    def test_if_cxxd_config_parser_returns_none_for_inexisting_target(self):
        self.assertEqual(self.parser.get_configuration_for_target('inexisting_target'), None)

    def test_if_cxxd_config_parser_returns_non_empty_blacklisted_dir_list(self):
        self.assertNotEqual(self.parser.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_non_empty_extra_file_extensions_list(self):
        self.assertNotEqual(self.parser.get_extra_file_extensions(), [])

    def test_if_cxxd_config_parser_returns_clang_tidy_binary(self):
        self.assertNotEqual(self.parser.get_clang_tidy_binary_path(), None)

    def test_if_cxxd_config_parser_returns_non_empty_clang_tidy_arg_list(self):
        self.assertNotEqual(self.parser.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_clang_format_binary(self):
        self.assertNotEqual(self.parser.get_clang_format_binary_path(), None)

    def test_if_cxxd_config_parser_returns_non_empty_clang_format_arg_list(self):
        self.assertNotEqual(self.parser.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_non_empty_project_builder_arg_list(self):
        self.assertNotEqual(self.parser.get_project_builder_args(), [])

    def test_if_is_file_blacklisted_handles_files_from_blacklisted_dirs_correctly(self):
        directory_list = ['/tmp']
        filename = '/tmp/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), True)

    def test_if_is_file_blacklisted_handles_files_not_in_blacklisted_dirs_correctly(self):
        directory_list = ['/tmp']
        filename = '/home/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), False)

    def test_if_is_file_blacklisted_handles_file_for_given_dir_recursively(self):
        directory_list = ['/tmp']
        filename = '/tmp/dir1/dir2/dir3/filename.cpp'
        self.assertEqual(CxxdConfigParser.is_file_blacklisted(directory_list, filename), True)

class CxxdConfigParserWithEmptyConfigFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                    = 'debug'
        cls.json_compilation_database = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.empty_cxxd_config         = FileGenerator.gen_empty_cxxd_config_filename()
        cls.project_root_directory    = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.json_compilation_database)
        FileGenerator.close_gen_file(cls.empty_cxxd_config)

    def setUp(self):
        self.parser_with_empty_config_file = CxxdConfigParser(self.empty_cxxd_config.name, self.project_root_directory)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_mode(self):
        self.assertEqual(self.parser_with_empty_config_file.get_configuration_type(), 'auto-discovery-try-harder')

    def test_if_cxxd_config_parser_returns_first_configuration_found_regardless_of_target(self):
        self.assertEqual(os.path.normpath(self.parser_with_empty_config_file.get_configuration_for_target('')), self.json_compilation_database.name)
        self.assertEqual(os.path.normpath(self.parser_with_empty_config_file.get_configuration_for_target('whatever')), self.json_compilation_database.name)

    def test_if_cxxd_config_parser_favors_compilation_db_over_txt_when_both_are_present(self):
        txt_comp_db = FileGenerator.gen_txt_compilation_database()
        self.assertEqual(os.path.normpath(self.parser_with_empty_config_file.get_configuration_for_target('')), self.json_compilation_database.name)
        FileGenerator.close_gen_file(txt_comp_db)

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list(self):
        self.assertEqual(self.parser_with_empty_config_file.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_empty_extra_file_extensions_list(self):
        self.assertEqual(self.parser_with_empty_config_file.get_extra_file_extensions(), [])

    def test_if_cxxd_config_parser_returns_clang_tidy_binary(self):
        self.assertNotEqual(self.parser_with_empty_config_file.get_clang_tidy_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list_(self):
        self.assertEqual(self.parser_with_empty_config_file.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_clang_format_binary(self):
        self.assertNotEqual(self.parser_with_empty_config_file.get_clang_format_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list(self):
        self.assertEqual(self.parser_with_empty_config_file.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list(self):
        self.assertEqual(self.parser_with_empty_config_file.get_project_builder_args(), [])


class CxxdConfigParserWithCornerCaseConfigEntriesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                    = 'debug'
        cls.json_compilation_database = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.project_root_directory    = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.json_compilation_database)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_when_configuration_is_missing(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery-try-harder')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_when_configuration_is_misspelled(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configurations" : {                        \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery-try-harder')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_when_type_is_missing(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery-try-harder')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_type_is_not_one_of_valid_values(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "something-unsupported"         \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_compilation_database_for_type(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "compilation-database"          \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'compilation-database')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_compile_flags_for_type(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "compile-flags"                 \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'compile-flags')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_auto_discovery_for_type(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "auto-discovery"                \n\
    }                                           \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery')
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_for_inexisting_target_section(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "compilation-database",         \n\
        "compilation-database" : {              \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_for_misspelled_target_section(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "compilation-database",         \n\
        "compilation-database" : {              \n\
            "targetsss" : {                     \n\
            }                                   \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_for_inexisting_target(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "compilation-database",         \n\
        "compilation-database" : {              \n\
            "target" : {                        \n\
            }                                   \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_auto_discovery_does_not_contain_any_search_paths(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "auto-discovery",               \n\
        "auto-discovery" : {                    \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_auto_discovery_search_path_is_misspelled(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "auto-discovery",               \n\
        "auto-discovery" : {                    \n\
            "search-pathssss" : [               \n\
            ]                                   \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_when_config_is_not_found_in_auto_discovery_search_paths(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "auto-discovery",               \n\
        "auto-discovery" : {                    \n\
            "search-paths" : ["/some_path"]     \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_config_found_in_auto_discovery_search_path(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type": "auto-discovery",               \n\
        "auto-discovery" : {                    \n\
            "search-paths" : ["/tmp"]           \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'auto-discovery')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('whatever'), self.json_compilation_database.name)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_none_configuration_when_config_for_selected_type_is_missing(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type" : "compilation-database",        \n\
        "compile-flags" : {                     \n\
            "target" : {                        \n\
                "rel" : "/rel"                  \n\
            }                                   \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'compilation-database')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('rel'), None)
        FileGenerator.close_gen_file(self.cxxd_config)

    def test_if_cxxd_config_parser_returns_valid_configuration_when_there_are_multiple_configs_existing(self):
        self.cxxd_config = FileGenerator.gen_cxxd_config_filename_with_invalid_section(['\
{                                               \n\
    "configuration" : {                         \n\
        "type" : "compilation-database",        \n\
        "compilation-database" : {              \n\
            "target" : {                        \n\
                "rel" : "/tmp"                  \n\
            }                                   \n\
        },                                      \n\
        "compile-flags" : {                     \n\
            "target" : {                        \n\
                "rel" : "/tmp"                  \n\
            }                                   \n\
        }                                       \n\
     }                                          \n\
}                                               \n\
        '])
        self.cxxd_config_parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)
        self.assertEqual(self.cxxd_config_parser.get_configuration_type(), 'compilation-database')
        self.assertEqual(self.cxxd_config_parser.get_configuration_for_target('rel'), self.json_compilation_database.name)
        FileGenerator.close_gen_file(self.cxxd_config)


class CxxdConfigParserWithNoConfigFileButWithCompilationDbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                    = 'debug'
        cls.json_compilation_database = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.project_root_directory    = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.json_compilation_database)

    def setUp(self):
        self.parser_with_inexisting_config_file = CxxdConfigParser('some_inexisting_cxxd_config_filename', self.project_root_directory)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_mode(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_configuration_type(), 'auto-discovery-try-harder')

    def test_if_cxxd_config_parser_returns_first_configuration_found_regardless_of_target(self):
        self.assertEqual(os.path.normpath(self.parser_with_inexisting_config_file.get_configuration_for_target('')), self.json_compilation_database.name)
        self.assertEqual(os.path.normpath(self.parser_with_inexisting_config_file.get_configuration_for_target('whatever')), self.json_compilation_database.name)

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_clang_tidy_binary(self):
        self.assertNotEqual(self.parser_with_inexisting_config_file.get_clang_tidy_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_extra_file_extensions_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_extra_file_extensions(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_clang_format_binary(self):
        self.assertNotEqual(self.parser_with_inexisting_config_file.get_clang_format_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_project_builder_args(), [])

class CxxdConfigParserWithNoConfigFileButWithCompileFlagsTxtConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                    = 'debug'
        cls.txt_compilation_database = FileGenerator.gen_txt_compilation_database()
        cls.project_root_directory    = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        self.parser_with_inexisting_config_file = CxxdConfigParser('some_inexisting_cxxd_config_filename', self.project_root_directory)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_mode(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_configuration_type(), 'auto-discovery-try-harder')

    def test_if_cxxd_config_parser_returns_first_configuration_found_regardless_of_target(self):
        self.assertEqual(os.path.normpath(self.parser_with_inexisting_config_file.get_configuration_for_target('')), self.txt_compilation_database.name)
        self.assertEqual(os.path.normpath(self.parser_with_inexisting_config_file.get_configuration_for_target('whatever')), self.txt_compilation_database.name)

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_clang_tidy_binary(self):
        self.assertNotEqual(self.parser_with_inexisting_config_file.get_clang_tidy_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_extra_file_extensions_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_extra_file_extensions(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_clang_format_binary(self):
        self.assertNotEqual(self.parser_with_inexisting_config_file.get_clang_format_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list(self):
        self.assertEqual(self.parser_with_inexisting_config_file.get_project_builder_args(), [])

class CxxdConfigParserWithNoConfigFileAndNoCompilationDbOrTxtCompileFlagsConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root_directory = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.parser = CxxdConfigParser('inexisting_cxxd_config_filename', self.project_root_directory)

    def test_if_cxxd_config_parser_returns_auto_discovery_try_harder_mode(self):
        self.assertEqual(self.parser.get_configuration_type(), 'auto-discovery-try-harder')

    def test_if_cxxd_config_parser_returns_none_because_no_configuration_could_be_found(self):
        self.assertEqual(self.parser.get_configuration_for_target(''), None)

    def test_if_cxxd_config_parser_returns_empty_blacklisted_dir_list(self):
        self.assertEqual(self.parser.get_blacklisted_directories(), [])

    def test_if_cxxd_config_parser_returns_clang_tidy_binary(self):
        self.assertNotEqual(self.parser.get_clang_tidy_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_extra_file_extensions_list(self):
        self.assertEqual(self.parser.get_extra_file_extensions(), [])

    def test_if_cxxd_config_parser_returns_empty_clang_tidy_arg_list(self):
        self.assertEqual(self.parser.get_clang_tidy_args(), [])

    def test_if_cxxd_config_parser_returns_clang_format_binary(self):
        self.assertNotEqual(self.parser.get_clang_format_binary_path(), None)

    def test_if_cxxd_config_parser_returns_empty_clang_format_arg_list(self):
        self.assertEqual(self.parser.get_clang_format_args(), [])

    def test_if_cxxd_config_parser_returns_empty_project_builder_arg_list(self):
        self.assertEqual(self.parser.get_project_builder_args(), [])

class CxxdConfigParserWithConfigFileButWithNoCompilationDbOrTxtCompileFlagsConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target                 = 'debug'
        cls.cxxd_config            = FileGenerator.gen_cxxd_config_filename(cls.target, 'inexisting_path')
        cls.project_root_directory = tempfile.gettempdir()

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.cxxd_config)

    def setUp(self):
        self.parser = CxxdConfigParser(self.cxxd_config.name, self.project_root_directory)

    def test_if_cxxd_config_parser_returns_compilation_database_type(self):
        self.assertEqual(self.parser.get_configuration_type(), 'compilation-database')

    def test_if_cxxd_config_parser_returns_none_because_no_configuration_file_could_be_found(self):
        self.assertEqual(self.parser.get_configuration_for_target(''), None)

if __name__ == '__main__':
    unittest.main()
