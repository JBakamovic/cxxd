from builtins import str
from builtins import object
class TypeDeduction(object):
    def __init__(self, parser):
        self.parser = parser

    def __call__(self, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])

        tunit  = self.parser.parse(contents_filename, original_filename)
        cursor = self.parser.get_cursor(tunit, line, column)
        if cursor and cursor.type:
            return True, cursor.type.spelling
        else:
            return False, None
