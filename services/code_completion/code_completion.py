import logging

from . expression_parser_utils import *

class CodeCompletionRequestId():
    CODE_COMPLETE = 0x0
    CACHE_WARMUP  = 0x1

class CodeCompletionSortingAlgorithmId():
    BY_PRIORITY  = 0x0
    BY_KIND      = 0x1
    BY_ALPHABET  = 0x2

def read_line(filename, offset):
    f = open(filename, 'r')
    f.seek(offset)
    l = f.readline()
    f.close()
    return l

class CodeCompletion():
    def __init__(self, parser):
        self.parser = parser
        self.op = {
            CodeCompletionRequestId.CODE_COMPLETE : self.__code_complete,
            CodeCompletionRequestId.CACHE_WARMUP  : self.__cache_warmup,
        }
        self.sorting_fun = {
            CodeCompletionSortingAlgorithmId.BY_PRIORITY    : self.__sort_code_completion_candidates_by_priority,
            CodeCompletionSortingAlgorithmId.BY_KIND        : self.__sort_code_completion_candidates_by_kind,
            CodeCompletionSortingAlgorithmId.BY_ALPHABET    : self.__sort_code_completion_candidates_by_alphabet,
        }
        self.completion_candidates = []

    def __call__(self, args):
        return self.op.get(int(args[0]), self.__unknown_op)(int(args[0]), args[1:len(args)])

    def __unknown_op(self, id, args):
        logging.error("Unknown operation with ID={0} triggered! Valid operations are: {1}".format(id, self.op))
        return False, None

    def __cache_warmup(self, id, args):
        filename = str(args[0])
        line     = int(args[1])
        column   = int(args[2])
        return True, self.parser.code_complete_cache_warmup(filename, line+1, 1)

    def __code_complete(self, id, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4]) - 1
        sorting_algo_id   = int(args[5])

        line_string = read_line(contents_filename, offset)

        curr_char_idx = column - 1
        prev_char_idx = curr_char_idx - 1
        next_char_idx = curr_char_idx + 1

        if curr_char_idx < len(line_string):
            current_char = line_string[curr_char_idx]

            # First, let's handle the obvious non-identifiers ...
            if is_carriage_return(current_char):
                self.__drop_completion_candidate_list()
            elif is_semicolon(current_char):
                self.__drop_completion_candidate_list()
            elif is_single_line_comment(line_string[:curr_char_idx]):
                self.__drop_completion_candidate_list()
            elif is_multi_line_comment(line_string[:curr_char_idx], curr_char_idx):
                self.__drop_completion_candidate_list()
            # TODO  Detecting that we are in the middle of multi-line comment is a bit more difficult task
            #       We would have to search accross multiple lines to be able to deduce that we are in the
            #       middle of multi-line comment. That doesn't seem very optimal in this particular use-case.
            elif is_whitespace(current_char):
                self.__drop_completion_candidate_list()
            elif is_opening_paren(current_char) or is_closing_paren(current_char):
                self.__drop_completion_candidate_list()
            # Member access or scope operator will give us a fresh list of new candidates
            elif is_member_access(line_string[prev_char_idx:next_char_idx]) or\
                is_scope_operator(line_string[prev_char_idx:next_char_idx]):
                self.__drop_completion_candidate_list()
                self.code_complete = self.parser.code_complete(contents_filename, original_filename, line, column)
                self.completion_candidates = list(self.code_complete.results) # Can't do any pre-filtering here
            # We pay more attention when handling identifiers
            elif is_identifier(current_char):
                idx = last_occurence_of_non_identifier(line_string[0:next_char_idx]) # [begin:end] slice is actually [begin:end> or [begin:end-1]
                if idx != -1:
                    symbol = line_string[(curr_char_idx-idx+1):next_char_idx]
                else:
                    symbol = line_string[0:next_char_idx] # If no non-identifier is found in [0:next_char_idx] range, then we have our symbol already

                if len(self.completion_candidates) == 0:
                    self.code_complete = self.parser.code_complete(contents_filename, original_filename, line, column)
                    self.completion_candidates = self.__filter_completion_candidates(
                        self.code_complete.results,
                        symbol.strip()
                    ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
                else:
                    # TODO This situation can be improved further by:
                    #       * if moving forward we can use list of already filtered candidates
                    #       * if moving backwards (backspace, delete) we have to re-use all (non-filtered)
                    #         candidates list or cache one ourselves?
                    self.completion_candidates = self.__filter_completion_candidates(
                        self.code_complete.results,
                        symbol.strip()
                    ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
            # Other special characters
            else:
                self.__drop_completion_candidate_list()

        self.sorting_fun.get(sorting_algo_id, self.__sort_code_completion_candidates_by_priority)(self.completion_candidates)
        return True, self.completion_candidates

    def __drop_completion_candidate_list(self):
        del self.completion_candidates[:]

    def __filter_completion_candidates(self, candidates, pattern):
        filtered_completion_candidates = []
        for result in candidates:
            for completion_chunk in result.string:
                if completion_chunk.isKindTypedText() and pattern in completion_chunk.spelling:
                    filtered_completion_candidates.append(result)
                    break
        return filtered_completion_candidates

    def __sort_code_completion_candidates_by_kind(self, code_completion_candidates):
        code_completion_candidates.sort(key=lambda candidate: candidate.kind)

    def __sort_code_completion_candidates_by_priority(self, code_completion_candidates):
        code_completion_candidates.sort(key=lambda candidate: candidate.string.priority)

    def __sort_code_completion_candidates_by_alphabet(self, code_completion_candidates):
        def extract_typed_text_completion_chunk(completion_string):
            for chunk in completion_string:
                if chunk.isKindTypedText():
                    return chunk
            return None
        code_completion_candidates.sort(key=lambda candidate: extract_typed_text_completion_chunk(candidate.string).spelling)
