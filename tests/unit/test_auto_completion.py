import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator

class AutoCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_file                = FileGenerator.gen_simple_cpp_file()
        #cls.test_file_edited         = FileGenerator.gen_simple_cpp_file(edited=True)
        cls.test_file_broken         = FileGenerator.gen_broken_cpp_file()
        #cls.test_file_broken_edited  = FileGenerator.gen_broken_cpp_file(edited=True)
        cls.txt_compilation_database = FileGenerator.gen_txt_compilation_database()

        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.test_file)
        #FileGenerator.close_gen_file(cls.test_file_edited)
        FileGenerator.close_gen_file(cls.test_file_broken)
        #FileGenerator.close_gen_file(cls.test_file_broken_edited)
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        import cxxd_mocks
        from services.source_code_model.auto_completion.auto_completion import AutoCompletion
        self.service = AutoCompletion(self.parser)

    def test_if_call_returns_true_and_std_vector_candidate_is_returned(self):
        success, completion_candidates = self.service([self.test_file.name, self.test_file.name, 8, 12])
        self.assertEqual(success, True)
        self.assertNotEqual(completion_candidates, [])
        print completion_candidates

    def test_if_call_returns_true_and_foobar_candidate_is_returned(self):
        success, completion_candidates = self.service([self.test_file.name, self.test_file.name, 9, 15])
        self.assertEqual(success, True)
        self.assertNotEqual(completion_candidates, [])
        print completion_candidates

