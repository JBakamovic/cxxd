class SymbolDatabaseMock():
    def get_definition(self, id):
        pass

    def get_filename(self, row):
        pass

    def get_line(self, row):
        pass

    def get_column(self, row):
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

class TranslationUnitMock():
    def __init__(self, filename):
        self.filename = filename

    @property
    def spelling(self):
        return self.filename

