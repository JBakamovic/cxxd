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

    def test_if_call_returns_true_and_candidates_matching_the_given_pattern_are_returned(self):
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

    def test_if_call_returns_true_and_empty_candidates_list_for_a_column_pointing_to_other_special_characters(self):
        self.fd.write('\
int main() {                                \n\
    int   a = 10;                           \n\
    int   b = ~a;                           \n\
    int   c = a^2;                          \n\
    int   d = a % 2;                        \n\
    int  *e = &d;                           \n\
    int   f = a * 2;                        \n\
    int   g = (a * 2);                      \n\
    int   h = a + 2;                        \n\
    int   i = a - 2;                        \n\
    int   j = a / 2;                        \n\
    int   k = a > 2 ? 1 : 2                 \n\
    bool  l = true | false;                 \n\
    int   m = { 1 };                        \n\
    int   n[10] = {0};                      \n\
    int   o, p;                             \n\
    bool  r = a > c;                        \n\
    bool  s = a < c;                        \n\
    char *t = "test"                        \n\
    bool  u = !a;                           \n\
}                                           \n\
        ')

        # Character: =
        line, column = 2, 13
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: whitespace
        line, column = 2, 14
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ;
        line, column = 2, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: carriage return
        line, column = 2, 45
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ~
        line, column = 3, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ^
        line, column = 4, 16
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: %
        line, column = 5, 18
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: &
        line, column = 6, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: *
        line, column = 7, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: (
        line, column = 8, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: )
        line, column = 8, 21
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: +
        line, column = 9, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: -
        line, column = 10, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: /
        line, column = 11, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ?
        line, column = 12, 21
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: :
        line, column = 12, 25
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: |
        line, column = 13, 20
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: {
        line, column = 14, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: }
        line, column = 14, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: [
        line, column = 15, 12
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ]
        line, column = 15, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: ,
        line, column = 16, 12
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: >
        line, column = 17, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: >
        line, column = 18, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: "
        line, column = 19, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        # Character: !
        line, column = 20, 15
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line)
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_dot_operator(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p1 = {0, 1};                          \n\
    return p1.                              \n\
}                                           \n\
        ')

        line, column = 4, 14
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

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_arrow_operator(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p1 = {0, 1};                          \n\
    P *p2 = &p1;                            \n\
    p2->                                    \n\
}                                           \n\
        ')

        line, column = 5, 8
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

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_ptr_to_member_of_object(self):
        self.fd.write('\
struct P { int x; int y; int *z;};          \n\
int main() {                                \n\
    int z = 10;                             \n\
    P p1 = {0, 1, &z};                      \n\
    p1.*                                    \n\
}                                           \n\
        ')

        line, column = 5, 8
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

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_ptr_to_member_of_ptr(self):
        self.fd.write('\
struct P { int x; int y; int *z;};          \n\
int main() {                                \n\
    int z = 10;                             \n\
    P p1 = {0, 1, &z};                      \n\
    P *p2 = &p1;                            \n\
    p2->*                                   \n\
}                                           \n\
        ')

        line, column = 6, 9
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

