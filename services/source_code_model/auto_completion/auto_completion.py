import logging
import os

class SourceCodeModelAutoCompletionRequestId():
    CODE_COMPLETE     = 0x0
    REFINE_CANDIDATES = 0x1

def extract_symbol(line_string):
    #logging.info('line to extract length {0}, line = {1}'.format(len(line_string), line_string))
    line_string_len = len(line_string)
    for idx, s in enumerate(line_string[::-1]):
        #logging.info('Current char is {0}'.format(s))
        if not s.isdigit() and not s.isalpha() and s != '_' or idx+1 == line_string_len:
            return idx
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
            SourceCodeModelAutoCompletionRequestId.REFINE_CANDIDATES : self.__refine_candidates,
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
        column            = int(args[3]) - 1
        offset            = int(args[4]) - 1

        line_string = read_line(contents_filename, offset)
        logging.info("Filtering from [{0}, {1}] with offset = {2}: line = '{3}', len = {4}".format(line, column, offset, line_string, len(line_string)))

        last_char_idx = column - 1
        if last_char_idx < len(line_string):
            last_char_input = line_string[last_char_idx-1]
            logging.info("last_char_input = '{0}'".format(last_char_input))
            if last_char_input == '\n' or last_char_input == '\r':
                logging.info('Carriage return detected ...')
                pass
            elif last_char_input.isspace() or last_char_input == ',' or last_char_input == ';' or last_char_input == '=':
                logging.info('Delimiting character detected ... Clearing up the completion candidates.')
                del self.completion_candidates[:]
            else:
                logging.info("Will extract symbol from '{0}'".format(line_string[0:last_char_idx]))
                logging.info('Trying harder ...')
                idx = extract_symbol(line_string[0:last_char_idx])
                if idx != -1:
                    expression = line_string[(last_char_idx-idx):last_char_idx] #.rstrip()
                    logging.info("expression found = '{0}'".format(expression))
                    last_char_input = expression[len(expression)-1] if len(expression) else ''
                    logging.info("last_char_input = '{0}'".format(last_char_input))
                    if last_char_input == ':' or last_char_input == '>' or last_char_input == '.' or last_char_input == '' or len(self.completion_candidates) == 0 and last_char_input != '-':
                        logging.info('Getting new list of candidates ...')
                        del self.completion_candidates[:]
                        tunit = self.parser.parse(contents_filename, original_filename)
                        self.auto_complete = self.parser.auto_complete(
                                tunit, line, column + 1
                        )
                        self.completion_candidates = self.__filter_completion_candidates(self.auto_complete.results, expression) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
                    else:
                        logging.info("Filtering by expression = '{0}' from '{1}' starting from {2}".format(expression,
                            line_string[0:last_char_idx], idx))
                        self.completion_candidates = self.__filter_completion_candidates(self.completion_candidates, expression) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)   
                    logging.info('Found {0} candidates.'.format(len(self.completion_candidates)))
                else:
                    logging.error('Failed to extract the symbol!') # Can't do nothing about it ...

        return True, self.completion_candidates

    def __code_complete_old(self, id, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4])

        line_string = read_line(contents_filename, offset)
        logging.info("Filtering from [{0}, {1}] with offset = {2}: line = '{3}'".format(line, column, offset, line_string))

        column = column - 1 # We need 0-based index column to work with strings ...
        logging.info("Will extract symbol from '{0}'".format(line_string[0:column]))
        last_char_input = line_string[column-1] if column > 0 else line_string[0]
        logging.info("last_char_input = '{0}'".format(last_char_input))

        if last_char_input == '\n' or last_char_input == '\r':
            logging.info('Carriage return detected ...')
            pass
        elif last_char_input.isspace() or last_char_input == ',' or last_char_input == ';' or last_char_input == '=':
            logging.info('Delimiting character detected ... Clearing up the completion candidates.')
            del self.completion_candidates[:]
        else:
            logging.info('Trying harder ...')
            idx = extract_symbol(line_string[0:column])
            if idx != -1:
                expression = line_string[(column-idx):column] #.rstrip()
                logging.info("expression found = '{0}'".format(expression))
                last_char_input = expression[len(expression)-1] if len(expression) else ''
                logging.info("last_char_input = '{0}'".format(last_char_input))
                if last_char_input == ':' or last_char_input == '>' or last_char_input == '.' or last_char_input == '' or len(self.completion_candidates) == 0:
                    logging.info('Getting new list of candidates ...')
                    del self.completion_candidates[:]
                    tunit = self.parser.parse(contents_filename, original_filename)
                    self.auto_complete = self.parser.auto_complete(
                            tunit, line, column + 2
                    )
                    self.completion_candidates = self.__filter_completion_candidates(self.auto_complete.results, expression) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)
                else:
                    logging.info("Filtering by expression = '{0}' from '{1}' starting from {2}".format(expression, line_string[0:column], idx))
                    self.completion_candidates = self.__filter_completion_candidates(self.completion_candidates, expression) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)   
                logging.info('Found {0} candidates.'.format(len(self.completion_candidates)))
            else:
                logging.error('Failed to extract the symbol!') # Can't do nothing about it ...

        return True, self.completion_candidates

    def __refine_candidates(self, id, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4])

        line_string = read_line(contents_filename, offset)
        #logging.info("Filtering from {0}, {1} with offset = {2}: line = '{3}'".format(line, column, offset, line_string))

        column = column - 1 # We need 0-based index column to work with strings ...
        #logging.info("Will extract symbol from '{0}'".format(line_string[0:column]))
        idx = extract_symbol(line_string[0:column])
        if idx != -1:
            expression = line_string[(column-idx):column].rstrip()
            #logging.info("Filtering by expression = '{0}' from '{1}' starting from {2}".format(expression, line_string[0:column], idx))
            self.completion_candidates = self.__filter_completion_candidates(self.completion_candidates, expression) # At this point we might already have something to work with (e.g. part of the string we may trigger filtering with)   
            #logging.info('Found {0} candidates.'.format(len(self.completion_candidates)))
        else:
            logging.error('Failed to extract the symbol!') # Can't do nothing about it ...
        return True, self.completion_candidates

    def __filter_completion_candidates(self, candidates, pattern):
        filtered_completion_candidates = []
        for result in candidates:
            for completion_chunk in result.string:
                if completion_chunk.isKindTypedText() and pattern in completion_chunk.spelling:
                    filtered_completion_candidates.append(result)
                    break
        return filtered_completion_candidates
