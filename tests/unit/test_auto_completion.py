import os
import tempfile
import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator
from services.source_code_model.auto_completion.auto_completion import AutoCompletion
from services.source_code_model.auto_completion.auto_completion import SourceCodeModelAutoCompletionRequestId

def candidate_contains_pattern(candidate, pattern):
    for chunk in candidate.string:
        if chunk.isKindTypedText() and pattern not in chunk.spelling:
            return False
    return True


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
        self.service = AutoCompletion(self.parser)
        self.fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)

    def tearDown(self):
        pass
        #os.remove(self.fd.name)

    def line_to_byte(self, test_file_line_length, line):
        return test_file_line_length*(line-1) + 1

    def test_if_call_returns_true_and_std_vector_candidate_is_returned(self):
        line, column = 8, 12
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.test_file.name, self.test_file.name,
            line,
            column,
            self.line_to_byte(29, line)
        ])
        print completion_candidates
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

    def test_if_call_returns_true_and_foobar_candidate_is_returned(self):
        line, column = 9, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.test_file.name, self.test_file.name,
            line,
            column,
            self.line_to_byte(29, line)
        ])
        print completion_candidates
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

    def test_if_call_returns_true_and_no_include_header_candidate_is_returned(self):
        line, column = 1, 3
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.test_file.name, self.test_file.name,
            line,
            column,
            self.line_to_byte(29, line)
        ])
        print completion_candidates
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_std_vector_members_are_returned(self):
        self.fd.write('\
#include <vector>                           \n\
                                            \n\
int main() {                                \n\
    std::vector<int> v;                     \n\
    return v.                               \n\
}                                           \n\
        ')

        line, column = 5, 13
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        print completion_candidates
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_only_candidates_which_include_res_are_returned(self):
        self.fd.write('\
#include <vector>                           \n\
                                            \n\
int main() {                                \n\
    std::vector<int> v;                     \n\
    return v.res                            \n\
}                                           \n\
        ')

        line, column = 5, 16
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        print completion_candidates
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)
        for candidate in completion_candidates:
            self.assertTrue(candidate_contains_pattern(candidate, 'res'))

    def not_test(self):
        self.fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)
        self.fd.write('\
#include <vector>                           \n\
                                            \n\
int default_len() {                         \n\
    return 10;                              \n\
}                                           \n\
                                            \n\
int main() {                                \n\
    std::vector<int> v(default_len());      \n\
    return v.size();                        \n\
}                                           \n\
                                            \n\
        ')

