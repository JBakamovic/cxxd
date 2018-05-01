import logging
import os

class AutoCompletion():
    def __init__(self, parser):
        self.parser = parser

    def __call__(self, args):
        expression        = str(args[0])
        original_filename = str(args[1])
        contents_filename = str(args[2])
        line              = int(args[3])
        column            = int(args[4])

        auto_complete = self.parser.auto_complete(
                    self.parser.parse(contents_filename, original_filename),
                    line, column
                )

        completion_candidates = []
        logging.info('Expression = {0}, Line = {1}, column = {2}'.format(expression, line, column))
        for result in auto_complete.results:
            for completion_chunk in result.string:
                if completion_chunk.isKindTypedText() and expression in completion_chunk.spelling:
                    completion_candidates.append(result)
                else:
                    pass

        for candidate in completion_candidates:
            logging.info('{0}'.format(candidate))

        return auto_complete is not None, completion_candidates

