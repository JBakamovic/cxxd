from builtins import object
class TUnitPool(object):
    def __init__(self):
        self.tunits = {}

    def get(self, filename):
        return self.tunits.get(filename, None)

    def set(self, filename, tunit):
        self.tunits[filename] = tunit

    def drop(self, filename):
        if filename in self.tunits:
            del self.tunits[filename]

    def clear(self):
        self.tunits.clear()

    def __len__(self):
        return len(self.tunits)

    def __setitem__(self, key, item):
        self.set(key, item)

    def __getitem__(self, key):
        return self.get(key)

    def __delitem__(self, filename):
        self.drop(filename)

    def __iter__(self):
        return iter(self.tunits.items())


class ImmutableSourceLocation(object):
    """
    Reason of existance of this class is because clang.cindex.SourceLocation is not designed to be hashable.
    """

    def __init__(self, filename, line, column, offset):
        self.filename = filename
        self.line = line
        self.column = column
        self.offset = offset

    @property
    def filename(self):
        """Get the filename represented by this source location."""
        return self.filename

    @property
    def line(self):
        """Get the line represented by this source location."""
        return self.line

    @property
    def column(self):
        """Get the column represented by this source location."""
        return self.column

    @property
    def offset(self):
        """Get the file offset represented by this source location."""
        return self.offset

    def __eq__(self, other):
        return self.filename == other.filename and self.line == other.line and self.column == other.column and self.offset == other.offset

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.filename) ^ hash(self.line) ^ hash(self.column) ^ hash(self.offset)

    def __repr__(self):
        return "<ImmutableSourceLocation file %r, line %r, column %r>" % (self.filename, self.line, self.column)


