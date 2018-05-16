import logging
import os

class SourceCodeModelAutoCompletionRequestId():
    CODE_COMPLETE     = 0x0
    REFINE_CANDIDATES = 0x1

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
    logging.info("line to extract length {0}, line = '{1}'".format(len(line_string), line_string))
    line_string_len = len(line_string)
    for idx, s in enumerate(line_string[::-1]):
        logging.info("Current char is '{0}'".format(s))
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
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE     : self.__code_complete,
            #SourceCodeModelAutoCompletionRequestId.REFINE_CANDIDATES : self.__refine_candidates,
        }
        self.completion_candidates = []

    def __call__(self, args):
        return self.op.get(int(args[0]), self.__unknown_op)(int(args[0]), args[1:len(args)])

    def __unknown_op(self, id, args):
        logging.error("Unknown operation with ID={0} triggered! Valid operations are: {1}".format(id, self.op))
        return False, None

    def __code_complete(self, id, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4]) - 1

        line_string = read_line(contents_filename, offset)
        logging.info("Filtering from [{0}, {1}] with offset = {2}: line = '{3}', len = {4}".format(line, column, offset, line_string, len(line_string)))

        curr_char_idx = column - 1
        prev_char_idx = curr_char_idx - 1
        next_char_idx = curr_char_idx + 1

        if curr_char_idx < len(line_string):
            current_char = line_string[curr_char_idx]
            logging.info("current_char = '{0}'".format(current_char))

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
                        tunit = self.parser.parse(contents_filename, original_filename)
                        self.auto_complete = self.parser.auto_complete(
                                tunit, line, column + 1
                        )
                        logging.info('Clang found {0} candidates.'.format(len(self.auto_complete.results)))
                        self.completion_candidates = self.__filter_completion_candidates(
                            self.auto_complete.results,
                            '' # We haven't got anything to filter with
                        )
                    else: # Otherwise, we won't get much from clang so we save some time here ...
                        pass
                    logging.info("previous_char = '{0}' current_char = '{1}' member_access or scope_operator = {2}".format(line_string[prev_char_idx] if prev_char_idx > 0 else 'no prev char', current_char, member_access or scope_operator))
                else:
                    logging.info("Will extract symbol from '{0}'".format(line_string[0:next_char_idx]))
                    idx = find_symbol_idx(line_string[0:next_char_idx]) # [begin:end] slice is actually [begin:end> or [begin:end-1]
                    if idx != -1:
                        symbol = line_string[(curr_char_idx-idx):next_char_idx]
                        logging.info("symbol found = '{0}'".format(symbol))
                        if len(self.completion_candidates) == 0 or symbol == '':
                            logging.info('Getting new list of candidates ...')
                            del self.completion_candidates[:]
                            tunit = self.parser.parse(contents_filename, original_filename)
                            self.auto_complete = self.parser.auto_complete(
                                    tunit, line, column + 1
                            )
                            logging.info('Clang found {0} candidates.'.format(len(self.auto_complete.results)))
                            self.completion_candidates = self.__filter_completion_candidates(
                                self.auto_complete.results,
                                symbol.strip()
                            ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
                        else:
                            logging.info(
                                "Filtering by symbol = '{0}' from '{1}' starting from {2}".format(symbol,
                                    line_string[0:next_char_idx], idx)
                            )
                            # TODO This situation can be improved further by:
                            #       * if moving forward we can use list of already filtered candidates
                            #       * if moving backwards (backspace, delete) we have to re-use all (non-filtered) candidates list
                            self.completion_candidates = self.__filter_completion_candidates(
                                self.auto_complete.results,
                                symbol.strip()
                            ) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)   
                        logging.info('Found {0} candidates.'.format(len(self.completion_candidates)))
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
