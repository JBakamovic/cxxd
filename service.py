import logging
from multiprocessing import Queue

# TODO Service impl. is where bits from ServiceHandler impl. should really go

class Service():
    def __init__(self, service_plugin):
        self.queue = Queue()
        self.service_plugin = service_plugin
        self.action = {
            0x0 : self.__startup_request,
            0x1 : self.__shutdown_request,
            0x2 : self.__request
        }
        self.started_up = False
        logging.info("Actions: {0}".format(self.action))

    def __startup_request(self, payload):
        if self.started_up:
            logging.warning('Service is already started!')
        else:
            logging.info("Service startup ... Payload = {0}".format(payload))
            self.startup_callback(payload)
            self.service_plugin.startup_callback(True, payload)
            self.started_up = True
        return self.started_up

    def __shutdown_request(self, payload):
        if self.started_up:
            logging.info("Service shutdown ... Payload = {0}".format(payload))
            self.shutdown_callback(payload)
            self.service_plugin.shutdown_callback(True, payload)
            self.started_up = False
        else:
            logging.warning('Service must be started before issuing any other kind of requests!')
        return self.started_up

    def __request(self, payload):
        if self.started_up:
            logging.info("Service request ... Payload = {0}".format(payload))
            success, args = self.__call__(payload)
            self.service_plugin.__call__(success, payload, args)
        else:
            logging.warning('Service must be started before issuing any other kind of requests!')
        return self.started_up

    def __unknown_action(self, payload):
        logging.error("Unknown action triggered! Valid actions are: {0}".format(self.action))
        return self.started_up

    def startup_callback(self, payload):
        pass

    def shutdown_callback(self, payload):
        pass

    def __call__(self, payload):
        return False, None

    def process_request(self):
        payload = self.queue.get()
        still_running = self.action.get(payload[0], self.__unknown_action)(payload[1])
        return still_running

    def send_startup_request(self, payload):
        self.queue.put([0x0, payload])

    def send_shutdown_request(self, payload):
        self.queue.put([0x1, payload])

    def send_request(self, payload):
        self.queue.put([0x2, payload])

    def is_started_up(self):
        return self.started_up

def service_listener(service):
    keep_listening = True
    while keep_listening:
        keep_listening = service.process_request()
    logging.info('Service listener shut down ...')
