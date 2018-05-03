import linecache
import logging
import os

class AutoCompletion():
    def __init__(self, parser):
        self.parser = parser

    def __call__(self, args):
        def extract_symbol(line_string):
            for idx, s in enumerate(line_string[::-1]):
                if not s.isdigit() and not s.isalpha() and s != '_':
                    return idx
            return -1

        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])

        tunit = self.parser.parse(contents_filename, original_filename)
        self.auto_complete = self.parser.auto_complete(
                    tunit, line, column
                )

        completion_candidates = []
        s = linecache.getline(contents_filename, line)
        logging.info('line = {0}'.format(s))
        idx = extract_symbol(s[0:column])
        logging.info('idx = {0}'.format(column - idx))
        if idx != -1:
            expression = s[(column-idx):column]
        else:
            expression = ' hahahhahahah '
        logging.info('Expression = {0}, Line = {1}, column = {2}'.format(expression, line, column))
        for result in self.auto_complete.results:
            for completion_chunk in result.string:
                if completion_chunk.isKindTypedText() and expression in completion_chunk.spelling:
                    completion_candidates.append(result)
                else:
                    pass

        for candidate in completion_candidates:
            logging.info('{0}'.format(candidate))

        return self.auto_complete is not None, completion_candidates
