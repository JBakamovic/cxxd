import clang.cindex
import mock
import os
import tempfile
import unittest

import parser.clang_parser
import parser.tunit_cache
from file_generator import FileGenerator
from services.source_code_model.auto_completion.auto_completion import AutoCompletion
from services.source_code_model.auto_completion.auto_completion import SourceCodeModelAutoCompletionRequestId
from services.source_code_model.auto_completion.auto_completion import AutoCompletionSortingAlgorithmId

def candidate_contains_pattern(candidate, pattern):
    for chunk in candidate.string:
        if chunk.isKindTypedText() and pattern not in chunk.spelling:
            return False
    return True

def extract_typed_text_chunk(candidate):
    return candidate.string[1] # TypedText key is 1

class AutoCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.txt_compilation_database = FileGenerator.gen_txt_compilation_database()
        cls.parser = parser.clang_parser.ClangParser(
            cls.txt_compilation_database.name,
            parser.tunit_cache.TranslationUnitCache(parser.tunit_cache.NoCache())
        )

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.txt_compilation_database)

    def setUp(self):
        self.service = AutoCompletion(self.parser)
        self.fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)

    def tearDown(self):
        pass

    def line_to_byte(self, test_file_line_length, line):
        return test_file_line_length*(line-1) + 1

    def test_if_call_returns_true_and_non_empty_candidate_list_on_include_directive(self):
        self.fd.write('\
#include <vector>                           \n\
                                            \n\
int main() {                                \n\
    return 0;                               \n\
}                                           \n\
        ')

        line, column = 1, 3
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 1)

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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)
        for candidate in completion_candidates:
            self.assertTrue(candidate_contains_pattern(candidate, 'res'))

    def test_if_call_returns_true_and_non_empty_candidate_list_for_pattern_which_is_not_sth_that_any_of_the_candidates_starts_with(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
bool created_1 = false;                     \n\
bool created_2 = false;                     \n\
P create_p3(int x, int y) {return {x, y};}  \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return ate                              \n\
}                                           \n\
        ')

        line, column = 8, 14
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_ALPHABET
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 5)
        self.assertEqual(extract_typed_text_chunk(completion_candidates[0]).spelling, "create_p1")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[1]).spelling, "create_p2")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[2]).spelling, "create_p3")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[3]).spelling, "created_1")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[4]).spelling, "created_2")

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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_dot_operator_and_array_subscript(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p[2] = {{0, 1}, {2, 3}};              \n\
    return p[0].                            \n\
}                                           \n\
        ')

        line, column = 4, 16
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_for_member_access_via_dot_operator_and_function_call(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return create_p(1, 2).                  \n\
}                                           \n\
        ')

        line, column = 4, 26
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
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
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_for_usage_of_scope_operator(self):
        self.fd.write('\
struct Config { static const int N = 10; }; \n\
int main() {                                \n\
    return Config::                         \n\
}                                           \n\
        ')

        line, column = 3, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_when_auto_completing_after_parenthesis(self):
        self.fd.write('\
struct Config { static const int N = 10; }; \n\
int main()                                  \n\
{C                                          \n\
    return 0;                               \n\
}                                           \n\
        ')

        line, column = 3, 2
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_empty_candidate_list_when_member_access_via_arrow_operator_is_not_yet_formed(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p1 = {0, 1};                          \n\
    P *p2 = &p1;                            \n\
    p2-                                     \n\
}                                           \n\
        ')

        line, column = 5, 7
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_empty_candidate_list_when_array_parenthesis_is_opened(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p[2] = {{0, 1}, {2, 3}};              \n\
    p                                       \n\
}                                           \n\
        ')

        line, column = 4, 5
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p[2] = {{0, 1}, {2, 3}};              \n\
    p[                                      \n\
}                                           \n\
        ')

        line, column = 4, 6
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_empty_candidate_list_when_array_parenthesis_is_closed(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p[2] = {{0, 1}, {2, 3}};              \n\
    p                                       \n\
}                                           \n\
        ')

        line, column = 4, 5
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
int main() {                                \n\
    P p[2] = {{0, 1}, {2, 3}};              \n\
    p[0]                                    \n\
}                                           \n\
        ')

        line, column = 4, 8
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_empty_candidate_list_when_scope_operator_is_not_yet_formed(self):
        self.fd.write('\
struct Config { static const int N = 10; }; \n\
int main() {                                \n\
    return Config:                          \n\
}                                           \n\
        ')

        line, column = 3, 18
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_when_function_call_parenthesis_is_opened(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        line, column = 4, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return create_p(                        \n\
}                                           \n\
        ')

        line, column = 4, 20
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_empty_candidate_list_when_function_call_parenthesis_is_closed(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        line, column = 4, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return create_p(1, 0)                   \n\
}                                           \n\
        ')

        line, column = 4, 25
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_is_returned_when_trying_to_autocomplete_local_function(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p(int x, int y) {return {x, y};}   \n\
int main() {                                \n\
    return cre                              \n\
}                                           \n\
        ')

        line, column = 4, 14
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_is_returned_while_inserting_or_deleting_characters_that_match_possible_candidates(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        line, column = 5, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 2)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p1                        \n\
}                                           \n\
        ')

        line, column = 5, 20
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        line, column = 5, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 2)

    def test_if_call_returns_true_and_empty_candidate_list_for_misspelled_expression_but_returns_a_non_empty_one_once_it_is_spelled_correctly(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_r                         \n\
}                                           \n\
        ')

        line, column = 5, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_                          \n\
}                                           \n\
        ')

        line, column = 5, 18
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 2)

    def test_if_call_returns_true_and_auto_completion_is_triggered_only_once_and_further_refinements_are_done_by_filtering_existing_candidates(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        candidate_0_completion_string = mock.MagicMock(clang.cindex.CompletionString)
        type(candidate_0_completion_string).priority = 0
        candidate_0 = mock.MagicMock(clang.cindex.CodeCompletionResult)
        type(candidate_0).kind = clang.cindex.CursorKind.FUNCTION_DECL
        type(candidate_0).string = candidate_0_completion_string

        candidate_1_completion_string = mock.MagicMock(clang.cindex.CompletionString)
        type(candidate_1_completion_string).priority = 0
        candidate_1 = mock.MagicMock(clang.cindex.CodeCompletionResult)
        type(candidate_1).kind = clang.cindex.CursorKind.FUNCTION_DECL
        type(candidate_1).string = candidate_1_completion_string

        candidates = mock.MagicMock(clang.cindex.CodeCompletionResults)
        type(candidates).results = [candidate_0, candidate_1]

        with mock.patch.object(self.service, '_AutoCompletion__filter_completion_candidates', return_value=candidates.results) as mock_filter_completion_candidates:
            line, column = 5, 19
            success, completion_candidates = self.service([
                SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
                self.fd.name, self.fd.name,
                line,
                column,
                self.line_to_byte(45, line),
                AutoCompletionSortingAlgorithmId.BY_PRIORITY
            ])
        mock_filter_completion_candidates.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 2)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p1                        \n\
}                                           \n\
        ')

        with mock.patch.object(self.service, '_AutoCompletion__filter_completion_candidates', return_value=candidates.results[0:1]) as mock_filter_completion_candidates:
            line, column = 5, 20
            success, completion_candidates = self.service([
                SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
                self.fd.name, self.fd.name,
                line,
                column,
                self.line_to_byte(45, line),
                AutoCompletionSortingAlgorithmId.BY_PRIORITY
            ])
        mock_filter_completion_candidates.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

        self.fd.seek(0)
        self.fd.truncate()
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        with mock.patch.object(self.service, '_AutoCompletion__filter_completion_candidates', return_value=candidates.results) as mock_filter_completion_candidates:
            line, column = 5, 19
            success, completion_candidates = self.service([
                SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
                self.fd.name, self.fd.name,
                line,
                column,
                self.line_to_byte(45, line),
                AutoCompletionSortingAlgorithmId.BY_PRIORITY
            ])
        mock_filter_completion_candidates.assert_called_once()
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 2)

    def test_if_call_returns_true_and_non_empty_candidate_list_sorted_in_alphabetical_order(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
P create_p3(int x, int y) {return {x, y};}  \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create_p                         \n\
}                                           \n\
        ')

        line, column = 6, 19
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_ALPHABET
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 3)
        self.assertEqual(extract_typed_text_chunk(completion_candidates[0]).spelling, "create_p1")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[1]).spelling, "create_p2")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[2]).spelling, "create_p3")

    def test_if_call_returns_true_and_non_empty_candidate_list_sorted_by_their_kind(self):
        self.fd.write('\
struct P { int x; int y; };                 \n\
bool created_1 = false;                     \n\
bool created_2 = false;                     \n\
P create_p3(int x, int y) {return {x, y};}  \n\
P create_p1(int x, int y) {return {x, y};}  \n\
P create_p2(int x, int y) {return {x, y};}  \n\
int main() {                                \n\
    return create                           \n\
}                                           \n\
        ')

        line, column = 8, 17
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_KIND
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 5)
        self.assertEqual(extract_typed_text_chunk(completion_candidates[0]).spelling, "create_p3")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[1]).spelling, "create_p1")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[2]).spelling, "create_p2")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[3]).spelling, "created_1")
        self.assertEqual(extract_typed_text_chunk(completion_candidates[4]).spelling, "created_2")

    def test_if_call_returns_true_and_auto_completion_doesnt_work_when_inside_the_udt(self):
        self.fd.write('\
int my_var = 59;                            \n\
class Point {                               \n\
public:                                     \n\
  Point(int x, int y) : _x(x), _y(y) {      \n\
    my_                                     \n\
  }                                         \n\
                                            \n\
private:                                    \n\
  void calc_z() {_z = _x + _y;}             \n\
                                            \n\
private:                                    \n\
  int _x; int _y; int _z;                   \n\
};                                          \n\
        ')

        line, column = 5, 7
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_macro_auto_completion_doesnt_work(self):
        self.fd.write('\
#define MY_VAR 5                            \n\
int main() {                                \n\
MY                                          \n\
}                                           \n\
        ')

        line, column = 3, 2
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_when_we_are_completing_at_column_nr_one(self):
        self.fd.write('\
int my_var = 5;                             \n\
int main() {                                \n\
m                                           \n\
}                                           \n\
        ')

        line, column = 3, 1
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertNotEqual(len(completion_candidates), 0)

    def test_if_call_returns_true_and_non_empty_candidate_list_when_there_is_no_non_identifier_prior_to_line_column_we_are_completing_at(self):
        self.fd.write('\
int my_var = 5;                             \n\
int main() {                                \n\
my_                                         \n\
}                                           \n\
        ')

        line, column = 3, 3
        success, completion_candidates = self.service([
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE,
            self.fd.name, self.fd.name,
            line,
            column,
            self.line_to_byte(45, line),
            AutoCompletionSortingAlgorithmId.BY_PRIORITY
        ])
        self.assertEqual(success, True)
        self.assertEqual(len(completion_candidates), 1)

