from builtins import object
class ServicePlugin(object):
    def __init__(self):
        pass

    def __startup_callback(self, success, payload):
        pass

    def __shutdown_callback(self, success, payload):
        pass

    def __call__(self, success, payload, args):
        pass
