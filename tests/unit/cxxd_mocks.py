class SymbolDatabaseMock():
    def get_symbol_filename(self, row):
        pass

    def get_symbol_line(self, row):
        pass

    def get_symbol_column(self, row):
        pass

    def fetch_symbol_definition_by_usr(self, usr):
        pass

class ServiceMock():
    def send_startup_request(self, payload):
        pass

    def send_shutdown_request(self, payload):
        pass

    def send_request(self, payload):
        pass

class ServicePluginMock():
    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        pass

class SourceLocationMock():
    class File:
        def __init__(self, filename):
            self.filename = filename

        @property
        def name(self):
            return self.filename

    def __init__(self, filename, line, column):
        self.file = self.File(filename)
        self.line = line
        self.column = column

    @property
    def file(self):
        return self.file

class DiagnosticMock():
    def __init__(self, location, spelling, severity, children):
        self._location = location
        self._spelling = spelling
        self._severity = severity
        self._children = children

    @property
    def location(self):
        return self._location

    @property
    def spelling(self):
        return self._spelling

    @property
    def severity(self):
        return self._severity

    @property
    def children(self):
        return self._children

class TranslationUnitMock():
    def __init__(self, filename, diagnostics=None):
        self.filename = filename
        self.diag = diagnostics

    @property
    def spelling(self):
        return self.filename

    @property
    def diagnostics(self):
        return self.diag

class CxxdConfigParserMock():
    def get_blacklisted_directories(self):
        return []
