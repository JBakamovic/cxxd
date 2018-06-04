import clang.cindex
import logging
import os

class SourceCodeModelAutoCompletionRequestId():
    CODE_COMPLETE     = 0x0

def is_identifier(char):
    is_digit = char.isdigit()
    is_alpha = char.isalpha()
    is_underscore = char == '_'
    return is_digit or is_alpha or is_underscore

def is_scope_operator(expr):
    assert len(expr) >= 2
    return expr[0] == ':' and expr[1] == ':'

def is_member_of_ptr(expr):
    assert len(expr) >= 2
    return expr[0] == '-' and expr[1] == '>'

def is_member_of_object(expr):
    assert len(expr) >= 2
    if expr[1] == '.':
        if is_identifier(expr[0]):
            return True
        elif expr[0] == ')':
            return True
        elif expr[0] == ']':
            return True
    return False

def is_ptr_to_member_of_object(expr):
    assert len(expr) >= 2
    return expr[0] == '.' and expr[1] == '*'

def is_ptr_to_member_of_ptr(expr):
    assert len(expr) >= 2
    return expr[0] == '>' and expr[1] == '*'

def is_member_access(expr):
    assert len(expr) >= 2
    return is_member_of_object(expr) or is_member_of_ptr(expr) or is_ptr_to_member_of_object(expr) or is_ptr_to_member_of_ptr(expr)

def is_special_character(char):
    special_characters = [
        '`',
        '~',
        '!',
        '@',
        '#',
        '$',
        '%',
        '^',
        '&',
        '*',
        '(',
        ')',
        #'_',
        '+',
        '-',
        '=',
        '/',
        '\\',
        '?',
        '|',
        '{',
        '}',
        '[',
        ']',
        '.',
        ',',
        '>',
        '<',
        ';',
        ':',
        '\'',
        '"',
    ]
    return char in special_characters

def is_carriage_return(c):
    return c == '\n' or c == '\r'

def is_semicolon(c):
    return c == ';'

def is_whitespace(c):
    return c.isspace()

def find_symbol_idx(line_string):
    line_string_len = len(line_string)
    for idx, s in enumerate(line_string[::-1]):
        if idx+1 == line_string_len:
            return idx
        if not is_identifier(s):
            return idx-1
    return -1

def read_line(filename, offset):
    f = open(filename, 'r')
    f.seek(offset)
    l = f.readline()
    f.close()
    return l

class AutoCompletion():
    def __init__(self, parser):
        self.parser = parser
        self.op = {
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE : self.__code_complete,
        }
        self.completion_candidates = []

    def __call__(self, args):
        return self.op.get(int(args[0]), self.__unknown_op)(int(args[0]), args[1:len(args)])

    def __unknown_op(self, id, args):
        logging.error("Unknown operation with ID={0} triggered! Valid operations are: {1}".format(id, self.op))
        return False, None

    def __get_auto_completion_candidates(self, contents_filename, original_filename, line, column):
        def parsing_flags():
            # TODO Do we need PARSE_DETAILED_PROCESSING_RECORD flag here? It looks like it makes no difference when
            #      auto-completing macro's. It does not get auto-completed regardless of presence of this flag.
            # TODO Add support for PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION
            return \
                clang.cindex.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS | \
                clang.cindex.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE | \
                clang.cindex.TranslationUnit.PARSE_INCOMPLETE

        return self.parser.auto_complete(
            self.parser.parse(
                contents_filename, original_filename,
                parsing_flags()
            ),
            line,
            column + 1
        )

    def __code_complete(self, id, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4]) - 1

        line_string = read_line(contents_filename, offset)

        curr_char_idx = column - 1
        prev_char_idx = curr_char_idx - 1
        next_char_idx = curr_char_idx + 1

        if curr_char_idx < len(line_string):
            current_char = line_string[curr_char_idx]

            if is_carriage_return(current_char):
                del self.completion_candidates[:]
            elif is_semicolon(current_char):
                del self.completion_candidates[:]
            elif is_whitespace(current_char):
                del self.completion_candidates[:]
            else:
                if is_special_character(current_char):
                    # Special character might indicate that we're finished with the expression.
                    del self.completion_candidates[:]

                    # However, in case of member access or scope operator, clang will be able to give us meaningful
                    # completion candidates so we ask for more.
                    member_access  = is_member_access(line_string[prev_char_idx:next_char_idx])  if curr_char_idx != 0 else False
                    scope_operator = is_scope_operator(line_string[prev_char_idx:next_char_idx]) if curr_char_idx != 0 else False
                    if member_access or scope_operator:
                        self.auto_complete = self.__get_auto_completion_candidates(contents_filename, original_filename, line, column)

                        # Member access or scope operator will give us a fresh list so we haven't got anything to filter with.
                        # Hence, we simply forward all the candidates we've got from clang.
                        self.completion_candidates = list(self.auto_complete.results)
                    else: # Otherwise, we won't get much from clang so we save some time here ...
                        pass
                else:
                    idx = find_symbol_idx(line_string[0:next_char_idx]) # [begin:end] slice is actually [begin:end> or [begin:end-1]
                    if idx != -1:
                        symbol = line_string[(curr_char_idx-idx):next_char_idx]
                        if len(self.completion_candidates) == 0 or symbol == '':
                            del self.completion_candidates[:]
                            self.auto_complete = self.__get_auto_completion_candidates(contents_filename, original_filename, line, column)
                            self.completion_candidates = self.__filter_completion_candidates(
                                self.auto_complete.results,
                                symbol.strip()
                            ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
                        else:
                            # TODO This situation can be improved further by:
                            #       * if moving forward we can use list of already filtered candidates
                            #       * if moving backwards (backspace, delete) we have to re-use all (non-filtered)
                            #         candidates list or cache one ourselves?
                            self.completion_candidates = self.__filter_completion_candidates(
                                self.auto_complete.results,
                                symbol.strip()
                            ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)   
                    else:
                        logging.error('Unable to extract symbol. Nothing to be done ...')

        return True, self.completion_candidates

    def __filter_completion_candidates(self, candidates, pattern):
        filtered_completion_candidates = []
        for result in candidates:
            for completion_chunk in result.string:
                if completion_chunk.isKindTypedText() and pattern in completion_chunk.spelling:
                    filtered_completion_candidates.append(result)
                    break
        return filtered_completion_candidates
