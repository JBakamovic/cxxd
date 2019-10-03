from __future__ import absolute_import
import mock
import multiprocessing
import tempfile
import unittest

import api
from . import cxxd_mocks
import server
from . file_generator import FileGenerator

class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root_directory        = tempfile.gettempdir()
        cls.json_compilation_database     = FileGenerator.gen_json_compilation_database('doesnt_matter.cpp')
        cls.target                        = 'debug'

    @classmethod
    def tearDownClass(cls):
        FileGenerator.close_gen_file(cls.json_compilation_database)

    def setUp(self):
        self.payload = [0x1, 0x2, 0x3]
        self.inexisting_service_id = 0xFF
        self.handle = multiprocessing.Queue()
        self.server = server.Server(
            self.handle,
            self.project_root_directory,
            self.target,
            cxxd_mocks.ServicePluginMock(),
            cxxd_mocks.ServicePluginMock(),
            cxxd_mocks.ServicePluginMock(),
            cxxd_mocks.ServicePluginMock(),
            cxxd_mocks.ServicePluginMock()
        )

    def test_if_server_is_considered_started_up_as_soon_as_instantiated(self):
        self.assertEqual(self.server.is_started_up(), True)

    def test_if_start_all_services_starts_service_listener_first_and_then_sends_startup_request_for_each_service(self):
        manager = mock.MagicMock()
        api.server_start_all_services(self.handle, self.payload)
        with mock.patch('server.Server.ServiceHandler.start_listening') as mock_start_listening:
            with mock.patch('server.Server.ServiceHandler.startup_request') as mock_startup_request:
                manager.attach_mock(mock_start_listening, 'mock_start_listening')
                manager.attach_mock(mock_startup_request, 'mock_startup_request')
                self.server.process_request()
        mock_start_listening.assert_called()
        self.assertEqual(mock_start_listening.call_count, len(self.server.service))
        mock_startup_request.assert_called_with([self.payload])
        self.assertEqual(mock_startup_request.call_count, len(self.server.service))
        manager.assert_has_calls(
            [mock.call.mock_start_listening(), mock.call.mock_startup_request([self.payload])]
        )

    def test_if_shutdown_all_services_sends_shutdown_request_first_and_then_stops_service_listener_for_each_service(self):
        manager = mock.MagicMock()
        api.server_stop_all_services(self.handle, self.payload)
        with mock.patch('server.Server.ServiceHandler.shutdown_request') as mock_shutdown_request:
            with mock.patch('server.Server.ServiceHandler.stop_listening') as mock_stop_listening:
                manager.attach_mock(mock_shutdown_request, 'mock_shutdown_request')
                manager.attach_mock(mock_stop_listening, 'mock_stop_listening')
                self.server.process_request()
        mock_stop_listening.assert_called()
        self.assertEqual(mock_stop_listening.call_count, len(self.server.service))
        mock_shutdown_request.assert_called_with([self.payload])
        self.assertEqual(mock_shutdown_request.call_count, len(self.server.service))
        manager.assert_has_calls(
            [mock.call.mock_shutdown_request([self.payload]), mock.call.mock_stop_listening()]
        )

    def test_if_start_service_starts_service_listener_first_and_then_sends_startup_request(self):
        manager = mock.MagicMock()
        api._server_start_service(self.handle, server.ServiceId.SOURCE_CODE_MODEL, self.payload)
        with mock.patch('server.Server.ServiceHandler.start_listening') as mock_start_listening:
            with mock.patch('server.Server.ServiceHandler.startup_request') as mock_startup_request:
                manager.attach_mock(mock_start_listening, 'mock_start_listening')
                manager.attach_mock(mock_startup_request, 'mock_startup_request')
                self.server.process_request()
        mock_start_listening.assert_called_once()
        mock_startup_request.assert_called_once_with([self.payload])
        manager.assert_has_calls(
            [mock.call.mock_start_listening(), mock.call.mock_startup_request([self.payload])]
        )

    def test_if_start_service_does_not_start_service_listener_or_sends_startup_request_for_unknown_service_id(self):
        api._server_start_service(self.handle, self.inexisting_service_id, self.payload)
        with mock.patch('server.Server.ServiceHandler.start_listening') as mock_start_listening:
            with mock.patch('server.Server.ServiceHandler.startup_request') as mock_startup_request:
                self.server.process_request()
        mock_start_listening.assert_not_called()
        mock_startup_request.assert_not_called()

    def test_if_shutdown_service_sends_shutdown_request_first_and_then_shuts_down_service_listener(self):
        manager = mock.MagicMock()
        api._server_stop_service(self.handle, server.ServiceId.SOURCE_CODE_MODEL, self.payload)
        with mock.patch('server.Server.ServiceHandler.shutdown_request') as mock_shutdown_request:
            with mock.patch('server.Server.ServiceHandler.stop_listening') as mock_stop_listening:
                manager.attach_mock(mock_shutdown_request, 'mock_shutdown_request')
                manager.attach_mock(mock_stop_listening, 'mock_stop_listening')
                self.server.process_request()
        mock_shutdown_request.assert_called_once_with([self.payload])
        mock_stop_listening.assert_called_once()
        manager.assert_has_calls(
            [mock.call.mock_shutdown_request([self.payload]), mock.call.mock_stop_listening()]
        )

    def test_if_shutdown_service_does_not_shutdown_service_listener_or_sends_shutdown_request_for_unknown_service_id(self):
        api._server_stop_service(self.handle, self.inexisting_service_id, self.payload)
        with mock.patch('server.Server.ServiceHandler.shutdown_request') as mock_shutdown_request:
            with mock.patch('server.Server.ServiceHandler.stop_listening') as mock_stop_listening:
                self.server.process_request()
        mock_shutdown_request.assert_not_called()
        mock_stop_listening.assert_not_called()

    def test_if_shutdown_and_exit_shuts_down_all_services_and_shuts_server_down(self):
        dummy_service_id = 0x0
        api.server_stop(self.handle, self.payload)
        with mock.patch('server.Server._Server__shutdown_all_services') as mock_shutdown_all_services:
            self.assertEqual(self.server.process_request(), False)
        mock_shutdown_all_services.assert_called_once_with(dummy_service_id, [self.payload])

    def test_if_send_service_request_sends_request(self):
        api._server_request_service(self.handle, server.ServiceId.SOURCE_CODE_MODEL, self.payload)
        with mock.patch('server.Server.ServiceHandler.request') as mock_send_request:
            self.assertEqual(self.server.process_request(), True)
        mock_send_request.assert_called_once_with([self.payload])

    def test_if_unsupported_server_request_is_well_handled(self):
        unsupported_server_request = 0xFAFAFA
        dummy_service_id = 0x0
        self.server.handle.put([unsupported_server_request, dummy_service_id, [self.payload]])
        with mock.patch('server.Server._Server__unknown_action') as mock_unknown_action:
            self.server.process_request()
        mock_unknown_action.assert_called_once_with(dummy_service_id, [self.payload])

class ServiceHandlerTest(unittest.TestCase):
    def setUp(self):
        self.payload = [0x1, 0x2, 0x3]        
        self.service_handler = server.Server.ServiceHandler(cxxd_mocks.ServiceMock())

    def test_if_service_handler_instance_does_not_implicitly_start_service_main_loop(self):
        self.assertEqual(self.service_handler.is_started(), False)

    def test_if_start_listening_starts_service_main_loop(self):
        with mock.patch('multiprocessing.Process.start') as mock_start_service_main_loop:
            self.service_handler.start_listening()
        mock_start_service_main_loop.assert_called_once()

    def test_if_start_listening_does_not_start_service_if_service_is_already_started(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch('multiprocessing.Process.start') as mock_start_service_main_loop:
                self.service_handler.start_listening()
        mock_start_service_main_loop.assert_not_called()

    def test_if_stop_listening_stops_service_main_loop(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch('multiprocessing.Process.join') as mock_stop_service_main_loop:
                self.service_handler.process = multiprocessing.Process()
                self.service_handler.stop_listening()
        mock_stop_service_main_loop.assert_called_once()

    def test_if_stop_listening_does_not_stop_service_if_service_is_already_stopped(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=False) as mock_is_started:
            with mock.patch('multiprocessing.Process.join') as mock_stop_service_main_loop:
                self.service_handler.stop_listening()
        mock_stop_service_main_loop.assert_not_called()

    def test_if_restarting_service_main_loop_is_handled_well(self):
        with mock.patch('multiprocessing.Process.start') as mock_start_service_main_loop_1:
            self.service_handler.start_listening()
        mock_start_service_main_loop_1.assert_called_once()
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch('multiprocessing.Process.join') as mock_stop_service_main_loop:
                self.service_handler.stop_listening()
        mock_stop_service_main_loop.assert_called_once()
        with mock.patch('multiprocessing.Process.start') as mock_start_service_main_loop_2:
            self.service_handler.start_listening()
        mock_start_service_main_loop_2.assert_called_once()

    def test_if_startup_request_does_not_send_startup_request_if_service_is_not_started(self):
        self.assertEqual(self.service_handler.is_started(), False)
        with mock.patch.object(self.service_handler.service, 'send_startup_request') as mock_send_startup_request:
            self.service_handler.startup_request(self.payload)
        mock_send_startup_request.assert_not_called()

    def test_if_startup_request_sends_startup_request_if_service_is_started(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch.object(self.service_handler.service, 'send_startup_request') as mock_send_startup_request:
                self.service_handler.startup_request(self.payload)
        mock_send_startup_request.assert_called_once_with(self.payload)

    def test_if_shutdown_request_does_not_send_shutdown_request_if_service_is_not_started(self):
        self.assertEqual(self.service_handler.is_started(), False)
        with mock.patch.object(self.service_handler.service, 'send_shutdown_request') as mock_send_shutdown_request:
            self.service_handler.shutdown_request(self.payload)
        mock_send_shutdown_request.assert_not_called()

    def test_if_shutdown_request_sends_shutdown_request_if_service_is_started(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch.object(self.service_handler.service, 'send_shutdown_request') as mock_send_shutdown_request:
                self.service_handler.shutdown_request(self.payload)
        mock_send_shutdown_request.assert_called_once_with(self.payload)

    def test_if_request_does_not_send_request_if_service_is_not_started(self):
        self.assertEqual(self.service_handler.is_started(), False)
        with mock.patch.object(self.service_handler.service, 'send_request') as mock_send_request:
            self.service_handler.request(self.payload)
        mock_send_request.assert_not_called()

    def test_if_request_sends_request_if_service_is_started(self):
        with mock.patch('server.Server.ServiceHandler.is_started', return_value=True) as mock_is_started:
            with mock.patch.object(self.service_handler.service, 'send_request') as mock_send_request:
                self.service_handler.request(self.payload)
        mock_send_request.assert_called_once_with(self.payload)

if __name__ == '__main__':
    unittest.main()
