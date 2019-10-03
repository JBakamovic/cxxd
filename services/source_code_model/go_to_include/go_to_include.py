from builtins import str
from builtins import object
class GoToInclude(object):
    def __init__(self, parser):
        self.parser = parser

    def __call__(self, args):
        include_filename  = None
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        tunit = self.parser.parse(contents_filename, original_filename)
        for include in self.parser.get_top_level_includes(tunit):
            filename, l, col = include
            if l == line:
                include_filename = filename
                break
        return (tunit is not None and include_filename is not None), include_filename
