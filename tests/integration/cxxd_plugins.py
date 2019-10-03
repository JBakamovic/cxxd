from builtins import object
class SourceCodeModelServicePluginMock(object):
    def __init__(self, callback_result):
        self.callback_result = callback_result

    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        self.callback_result.set(success, payload, args)

class ClangFormatServicePluginMock(object):
    def __init__(self, callback_result):
        self.callback_result = callback_result

    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        self.callback_result.set(success, args)

class ClangTidyServicePluginMock(object):
    def __init__(self, callback_result):
        self.callback_result = callback_result

    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        self.callback_result.set(success, args)

class ProjectBuilderServicePluginMock(object):
    def __init__(self, callback_result):
        self.callback_result = callback_result

    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        self.callback_result.set(success, args)

class CodeCompletionServicePluginMock(object):
    def __init__(self, callback_result):
        self.callback_result = callback_result

    def startup_callback(self, success, payload):
        pass

    def shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        self.callback_result.set(success, args)

