import ctypes
import clang.cindex
from clang.cindex import conf

from . expression_parser_utils import *
from cxxd.parser.clang_parser import ClangParser
from cxxd.parser.ast_node_identifier import ASTNodeId

import logging
import time

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
        self.all_candidates_cache = []

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

        start_time = time.time()
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
            elif is_whitespace(current_char):
                self.__drop_completion_candidate_list()
            elif is_opening_paren(current_char) or is_closing_paren(current_char):
                self.__drop_completion_candidate_list()
            # Member access or scope operator will give us a fresh list of new candidates
            elif is_member_access(line_string[prev_char_idx:next_char_idx]) or\
                is_scope_operator(line_string[prev_char_idx:next_char_idx]):
                self.__drop_completion_candidate_list()
                t0 = time.time()
                self.code_complete = self.parser.code_complete(contents_filename, original_filename, line, column)
                logging.debug(f"PERF: parser.code_complete took {time.time() - t0:.4f}s")
                t1 = time.time()
                raw_results = self.code_complete.results
                self.__cache_candidates_optimized(raw_results)
                self.completion_candidates = list(self.all_candidates_cache) # Start with all
                logging.debug(f"PERF: conversion to cached tuples took {time.time() - t1:.4f}s (count={len(self.completion_candidates)})")
            # We pay more attention when handling identifiers
            elif is_identifier(current_char):
                idx = last_occurence_of_non_identifier(line_string[0:next_char_idx])
                if idx != -1:
                    symbol = line_string[(curr_char_idx-idx+1):next_char_idx]
                else:
                    symbol = line_string[0:next_char_idx]

                if len(self.completion_candidates) == 0:
                    t0 = time.time()
                    self.code_complete = self.parser.code_complete(contents_filename, original_filename, line, column)
                    logging.debug(f"PERF: parser.code_complete (fallback) took {time.time() - t0:.4f}s")
                    t1 = time.time()
                    raw_results = self.code_complete.results
                    self.__cache_candidates_optimized(raw_results)
                    logging.debug(f"PERF: caching fallback took {time.time() - t1:.4f}s")
                    t1 = time.time()
                    self.completion_candidates = self.__filter_completion_candidates(
                        self.all_candidates_cache,
                        symbol.strip()
                    )
                    logging.debug(f"PERF: filter_candidates (initial) took {time.time() - t1:.4f}s (count={len(self.completion_candidates)})")
                else:
                    t1 = time.time()
                    # Use all_candidates_cache for filtering to support backspace correctly without complex logic
                    # Ideally we would filter the already filtered list if pattern grows, but for now 
                    # filtering from full cache is fast enough (<10ms for 20k items usually).
                    self.completion_candidates = self.__filter_completion_candidates(
                        self.all_candidates_cache, # Always filter from full cache to be safe
                        symbol.strip()
                    )
                    logging.debug(f"PERF: filter_candidates (refinement) took {time.time() - t1:.4f}s");
            # Other special characters
            else:
                self.__drop_completion_candidate_list()
        t2 = time.time()
        self.sorting_fun.get(sorting_algo_id, self.__sort_code_completion_candidates_by_priority)(self.completion_candidates)
        logging.debug(f"PERF: sorting took {time.time() - t2:.4f}s")
        logging.debug(f"PERF: Total __code_complete took {time.time() - start_time:.4f}s")
        return True, self.completion_candidates

    def __drop_completion_candidate_list(self):
        del self.completion_candidates[:]

    def __filter_completion_candidates(self, candidates, pattern):
        # Optimized filtering: 'candidates' is now a list of (typed_text, completion_result) tuples
        filtered_completion_candidates = []
        for typed_text, result in candidates:
            if pattern in typed_text:
                filtered_completion_candidates.append((typed_text, result))
        return filtered_completion_candidates

    def __sort_code_completion_candidates_by_kind(self, code_completion_candidates):
        # candidate is (typed_text, completion_result)
        code_completion_candidates.sort(key=lambda candidate: candidate[1].kind)

    def __sort_code_completion_candidates_by_priority(self, code_completion_candidates):
        # candidate is (typed_text, completion_result)
        code_completion_candidates.sort(key=lambda candidate: candidate[1].string.priority)

    def __sort_code_completion_candidates_by_alphabet(self, code_completion_candidates):
        # candidate is (typed_text, completion_result)
        code_completion_candidates.sort(key=lambda candidate: candidate[1])

    def __cache_candidates_optimized(self, raw_results):
        try:
            library_file = conf.lib._name
            if not library_file:
                 if clang.cindex.Config.library_file:
                     library_file = clang.cindex.Config.library_file
                 else:
                     raise Exception("Library file not found for isolated CDLL")

            my_lib = ctypes.CDLL(library_file)

            _getChunkKind = my_lib.clang_getCompletionChunkKind
            _getChunkText = my_lib.clang_getCompletionChunkText
            _getChunkText.restype = clang.cindex._CXString
            _getCString = my_lib.clang_getCString
            _getCString.restype = ctypes.c_char_p # This returns bytes in Py3 directly
            _disposeString = my_lib.clang_disposeString
            _getNumChunks = my_lib.clang_getNumCompletionChunks

            self.all_candidates_cache = []
            for res in raw_results:
                 typed_text = ""
                 # Access internal obj pointer from CompletionString (inherits from ClangObject)
                 cs_obj = res.string.obj 
                 num = _getNumChunks(cs_obj)
                 for i in range(num):
                     if _getChunkKind(cs_obj, i) == 1: # CXCompletionChunk_TypedText = 1
                         cx_str = _getChunkText(cs_obj, i)
                         # Explicitly call getCString on the struct
                         c_str = _getCString(cx_str)
                         if c_str:
                             typed_text = c_str.decode('utf-8', 'ignore')
                         _disposeString(cx_str)
                         break
                 self.all_candidates_cache.append((typed_text, res))
        except Exception as e:
            # Fallback to slower loop (TODO measure again)
            self.all_candidates_cache = []
            for res in raw_results:
                typed_text = ""
                for chunk in res.string:
                    if chunk.isKindTypedText():
                        typed_text = chunk.spelling
                        break
                self.all_candidates_cache.append((typed_text, res))

