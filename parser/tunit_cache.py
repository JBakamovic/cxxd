import os
from collections import OrderedDict

class NoCache():
    def __init__(self):
        pass

    def fetch(self, tunit_filename):
        return (None, None,)

    def insert(self, tunit_filename, tunit):
        pass

    def iterkeys(self):
        return iter(())

    def itervalues(self):
        return iter(())

    def iteritems(self):
        return iter(())

    def __setitem__(self, key, item):
        self.insert(key, item)

    def __getitem__(self, key):
        return self.fetch(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

class UnlimitedCache():
    def __init__(self):
        self.store = {}

    def iterkeys(self):
        return iter(self.store.keys())

    def itervalues(self):
        return iter(self.store.values())

    def iteritems(self):
        return iter(self.store.items())

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        if key in self.store:
            del self.store[key]
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return self.store.__iter__()

    def __len__(self):
        return len(self.store)

class FifoCache():
    def __init__(self, max_capacity):
        self.max_capacity = max_capacity
        self.store = OrderedDict()

    def iterkeys(self):
        return iter(self.store.keys())

    def itervalues(self):
        return iter(self.store.values())

    def iteritems(self):
        return iter(self.store.items())

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        if key in self.store:
            del self.store[key]
        else:
            if len(self.store) == self.max_capacity:
                self.store.popitem(last=False) # last=False --> FIFO, last=True --> LIFO
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return self.store.__iter__()

    def __len__(self):
        return len(self.store)

class TranslationUnitCache():
    def __init__(self, cache_impl):
        self.tunit = cache_impl

    def fetch(self, tunit_filename):
        if tunit_filename in self.tunit:
            return self.tunit[tunit_filename]
        return (None, None, None,)

    def insert(self, tunit_filename, tunit, build_flags, mtime):
        self.tunit[tunit_filename] = (tunit, build_flags, mtime,)

    def update(self, tunit_filename, tunit, build_flags, mtime):
        del self.tunit[tunit_filename]
        self.insert(tunit_filename, tunit, build_flags, mtime)

    def iterkeys(self):
        return iter(self.tunit.keys())

    def itervalues(self):
        return iter(self.tunit.values())

    def iteritems(self):
        return iter(self.tunit.items())

    def __setitem__(self, key, item):
        self.insert(key, item)

    def __getitem__(self, key):
        return self.fetch(key)

    def __iter__(self):
        return self.tunit.__iter__()

    def __len__(self):
        return len(self.tunit)

