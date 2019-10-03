import mock
import unittest

class ServiceTest(unittest.TestCase):
    def setUp(self):
        from . import cxxd_mocks
        import service
        self.unsupported_request = 0xFF
        self.payload = [0x1, 0x2, 0x3]
        self.service = service.Service(cxxd_mocks.ServicePluginMock())

    def test_if_send_startup_request_enqueues_correct_data(self):
        with mock.patch.object(self.service.queue, 'put') as mock_queue_put:
            self.service.send_startup_request(self.payload)
        mock_queue_put.assert_called_once_with([0x0, self.payload])

    def test_if_send_shutdown_request_enqueues_correct_data(self):
        with mock.patch.object(self.service.queue, 'put') as mock_queue_put:
            self.service.send_shutdown_request(self.payload)
        mock_queue_put.assert_called_once_with([0x1, self.payload])

    def test_if_send_request_enqueues_correct_data(self):
        with mock.patch.object(self.service.queue, 'put') as mock_queue_put:
            self.service.send_request(self.payload)
        mock_queue_put.assert_called_once_with([0x2, self.payload])

    def test_if_service_is_not_started_by_default(self):
        self.assertEqual(self.service.is_started_up(), False)

    def test_if_service_is_started_after_send_startup_request(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)

    def test_if_service_is_shut_down_after_send_shutdown_request(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)
        self.service.send_shutdown_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), False)

    def test_if_service_is_left_started_after_send_request(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)
        self.service.send_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)

    def test_if_send_startup_request_makes_no_effect_if_service_is_already_started(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_startup_request(self.payload)
        with mock.patch.object(self.service, 'startup_callback') as mock_service_startup_callback:
            with mock.patch.object(self.service.service_plugin, 'startup_callback') as mock_service_plugin_startup_callback:
                self.service.process_request()
        mock_service_startup_callback.assert_not_called()
        mock_service_plugin_startup_callback.assert_not_called()

    def test_if_send_shutdown_request_makes_no_effect_if_service_is_not_started(self):
        self.service.send_shutdown_request(self.payload)
        with mock.patch.object(self.service, 'shutdown_callback') as mock_service_shutdown_callback:
            with mock.patch.object(self.service.service_plugin, 'shutdown_callback') as mock_service_plugin_shutdown_callback:
                self.service.process_request()
        mock_service_shutdown_callback.assert_not_called()
        mock_service_plugin_shutdown_callback.assert_not_called()

    def test_if_send_shutdown_request_makes_no_effect_if_service_is_already_shutdown(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        with mock.patch.object(self.service, 'shutdown_callback') as mock_service_shutdown_callback:
            with mock.patch.object(self.service.service_plugin, 'shutdown_callback') as mock_service_plugin_shutdown_callback:
                self.service.process_request()
        mock_service_shutdown_callback.assert_not_called()
        mock_service_plugin_shutdown_callback.assert_not_called()

    def test_if_send_request_makes_no_effect_if_service_is_not_started(self):
        self.service.send_request(self.payload)
        with mock.patch.object(self.service, '__call__') as mock_service_request:
            with mock.patch.object(self.service.service_plugin, '__call__') as mock_service_plugin_request:
                self.service.process_request()
        mock_service_request.assert_not_called()
        mock_service_plugin_request.assert_not_called()

    def test_if_send_startup_request_triggers_service_startup_callback(self):
        self.service.send_startup_request(self.payload)
        with mock.patch.object(self.service, 'startup_callback') as mock_startup_callback:
            self.service.process_request()
        mock_startup_callback.assert_called_once_with(self.payload)

    def test_if_send_startup_request_triggers_service_plugin_startup_callback(self):
        self.service.send_startup_request(self.payload)
        with mock.patch.object(self.service.service_plugin, 'startup_callback') as mock_startup_callback:
            self.service.process_request()
        mock_startup_callback.assert_called_once_with(True, self.payload)

    def test_if_send_startup_request_triggers_service_startup_request_first_and_service_plugin_startup_request_second(self):
        manager = mock.MagicMock()
        self.service.send_startup_request(self.payload)
        with mock.patch.object(self.service, 'startup_callback') as mock_service_startup_callback:
            with mock.patch.object(self.service.service_plugin, 'startup_callback') as mock_service_plugin_startup_callback:
                manager.attach_mock(mock_service_startup_callback, 'mock_service_startup_callback')
                manager.attach_mock(mock_service_plugin_startup_callback, 'mock_service_plugin_startup_callback')
                self.service.process_request()
        mock_service_startup_callback.assert_called_once_with(self.payload)
        mock_service_plugin_startup_callback.assert_called_once_with(True, self.payload)
        manager.assert_has_calls(
            [mock.call.mock_service_startup_callback(self.payload), mock.call.mock_service_plugin_startup_callback(True, self.payload)]
        )

    def test_if_send_shutdown_request_triggers_service_shutdown_callback(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        with mock.patch.object(self.service, 'shutdown_callback') as mock_shutdown_callback:
            self.service.process_request()
        mock_shutdown_callback.assert_called_once_with(self.payload)

    def test_if_send_shutdown_request_triggers_service_plugin_shutdown_callback(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        with mock.patch.object(self.service.service_plugin, 'shutdown_callback') as mock_shutdown_callback:
            self.service.process_request()
        mock_shutdown_callback.assert_called_once_with(True, self.payload)

    def test_if_send_shutdown_request_triggers_service_shutdown_request_first_and_service_plugin_shutdown_request_second(self):
        manager = mock.MagicMock()
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        with mock.patch.object(self.service, 'shutdown_callback') as mock_service_shutdown_callback:
            with mock.patch.object(self.service.service_plugin, 'shutdown_callback') as mock_service_plugin_shutdown_callback:
                manager.attach_mock(mock_service_shutdown_callback, 'mock_service_shutdown_callback')
                manager.attach_mock(mock_service_plugin_shutdown_callback, 'mock_service_plugin_shutdown_callback')
                self.service.process_request()
        mock_service_shutdown_callback.assert_called_once_with(self.payload)
        mock_service_plugin_shutdown_callback.assert_called_once_with(True, self.payload)
        manager.assert_has_calls(
            [mock.call.mock_service_shutdown_callback(self.payload), mock.call.mock_service_plugin_shutdown_callback(True, self.payload)]
        )

    def test_if_send_request_triggers_service_request(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_request(self.payload)
        with mock.patch.object(self.service, '__call__', mock.Mock(return_value=(True, None))) as mock_service_request:
            self.service.process_request()
        mock_service_request.assert_called_once_with(self.payload)

    def test_if_send_request_triggers_service_plugin_request(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_request(self.payload)
        with mock.patch.object(self.service, '__call__', mock.Mock(return_value=(True, None))) as mock_service_request:
            with mock.patch.object(self.service.service_plugin, '__call__') as mock_service_plugin_request:
                self.service.process_request()
        mock_service_plugin_request.assert_called_once_with(True, self.payload, None)

    def test_if_send_request_triggers_service_request_first_and_service_plugin_request_second(self):
        manager = mock.MagicMock()
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_request(self.payload)
        with mock.patch.object(self.service, '__call__', mock.Mock(return_value=(True, None))) as mock_service_request:
            with mock.patch.object(self.service.service_plugin, '__call__') as mock_service_plugin_request:
                manager.attach_mock(mock_service_request, 'mock_service_request')
                manager.attach_mock(mock_service_plugin_request, 'mock_service_plugin_request')
                self.service.process_request()
        mock_service_request.assert_called_once_with(self.payload)
        mock_service_plugin_request.assert_called_once_with(True, self.payload, None)
        manager.assert_has_calls(
            [mock.call.mock_service_request(self.payload), mock.call.mock_service_plugin_request(True, self.payload, None)]
        )

    def test_if_send_startup_request_returns_true_after_first_startup(self):
        self.service.send_startup_request(self.payload)
        self.assertEqual(self.service.process_request(), True)

    def test_if_send_startup_request_returns_true_if_service_is_already_started(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_startup_request(self.payload)
        self.assertEqual(self.service.process_request(), True)

    def test_if_send_shutdown_request_returns_false_after_shutdown(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        self.assertEqual(self.service.process_request(), False)

    def test_if_send_shutdown_request_returns_false_if_service_is_already_shutdown(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        self.service.process_request()
        self.service.send_shutdown_request(self.payload)
        self.assertEqual(self.service.process_request(), False)

    def test_if_send_request_returns_true_if_service_is_started(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.send_request(self.payload)
        self.assertEqual(self.service.process_request(), True)

    def test_if_send_request_returns_false_if_service_is_not_started(self):
        self.service.send_request(self.payload)
        self.assertEqual(self.service.process_request(), False)

    def test_if_unsupported_request_returns_true_if_service_is_started(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.service.queue.put([self.unsupported_request, self.payload])
        self.assertEqual(self.service.process_request(), True)

    def test_if_unsupported_request_returns_false_if_service_is_not_started(self):
        self.service.queue.put([self.unsupported_request, self.payload])
        self.assertEqual(self.service.process_request(), False)

    def test_if_service_restart_is_handled_well(self):
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)
        self.service.send_shutdown_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), False)
        self.service.send_startup_request(self.payload)
        self.service.process_request()
        self.assertEqual(self.service.is_started_up(), True)

if __name__ == '__main__':
    unittest.main()
