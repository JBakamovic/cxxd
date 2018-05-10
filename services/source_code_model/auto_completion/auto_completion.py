import logging
import os

class SourceCodeModelAutoCompletionRequestId():
    CODE_COMPLETE     = 0x0
    REFINE_CANDIDATES = 0x1

class AutoCompletion():
    def __init__(self, parser):
        self.parser = parser
        self.op = {
            SourceCodeModelAutoCompletionRequestId.CODE_COMPLETE     : self.__code_complete,
            SourceCodeModelAutoCompletionRequestId.REFINE_CANDIDATES : self.__refine_candidates,
        }

    def __call__(self, args):
        return self.op.get(int(args[0]), self.__unknown_op)(int(args[0]), args[1:len(args)])

    def __unknown_op(self, id, args):
        logging.error("Unknown operation with ID={0} triggered! Valid operations are: {1}".format(id, self.op))
        return False, None

    def __code_complete(self, id, args):
        def read_line(filename, offset):
            f = open(filename, 'r')
            f.seek(offset)
            l = f.readline()
            f.close()
            return l

        def extract_symbol(line_string):
            for idx, s in enumerate(line_string[::-1]):
                if not s.isdigit() and not s.isalpha() and s != '_':
                    return idx
            return -1

        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])
        offset            = int(args[4])

        line_string = read_line(contents_filename, offset)

        tunit = self.parser.parse(contents_filename, original_filename)
        self.auto_complete = self.parser.auto_complete(
                    tunit, line, column + 1
                )

        column = column - 1 # We need 0-based index column to work with strings ...
        completion_candidates = []
        idx = extract_symbol(line_string[0:column])
        if idx != -1:
            expression = line_string[(column-idx):column].rstrip()
            for result in self.auto_complete.results:
                for completion_chunk in result.string:
                    if completion_chunk.isKindTypedText() and expression in completion_chunk.spelling:
                        completion_candidates.append(result)
                        break
        else:
            logging.error('Failed to extract the symbol!') # Can't do nothing about it ...

        return self.auto_complete is not None, completion_candidates

    def __refine_candidates(self, id, args):
        pass

