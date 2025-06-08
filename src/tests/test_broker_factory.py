import unittest
from unittest.mock import patch, MagicMock, ANY
import sys
import os

# Adjust path to import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.brokers.broker_factory import broker_factory, BrokerFactory
from src.brokers.base_broker import BaseBroker
from src.brokers.deriv_broker import DerivBroker
from src.brokers.icmarkets_broker import ICMarketsBroker
from src.brokers.xm_broker import XMBroker
from src.brokers.exness_broker import ExnessBroker

# We need to mock MetaTrader5 for ICMarketsBroker and its children (XM, Exness)
# This mock should be active when these broker modules are loaded by the factory or tests.
# It's applied globally here for simplicity during test discovery for this file.
mock_mt5_global = MagicMock()
sys.modules['MetaTrader5'] = mock_mt5_global
sys.modules['MetaTrader5'].TIMEFRAME_M1 = 1
# Add other MT5 constants if needed by the parts of ICMarketsBroker that might be touched
sys.modules['MetaTrader5'].TRADE_RETCODE_DONE = 10009
sys.modules['MetaTrader5'].TRADE_RETCODE_PLACED = 10008


# Helper to create mock MT5 info objects, similar to test_icmarkets_broker.py
def create_mock_mt5_account_info(login, balance, currency):
    info = MagicMock()
    info.login = login
    info.balance = balance
    info.currency = currency
    return info

def create_mock_mt5_terminal_info(connected=True):
    info = MagicMock()
    info.connected = connected
    return info


class TestBrokerFactory(unittest.TestCase):

    def setUp(self):
        # Reset parts of the broker_factory instance if necessary.
        # broker_factory is a singleton. Its _broker_instances cache might need clearing.
        # For these tests, we are primarily concerned with it being able to *create* new instances.
        # The BROKER_IMPLEMENTATIONS dict is populated at import time of broker_factory module.

        # Reset the global MT5 mock before each test involving MT5 brokers
        global mock_mt5_global
        mock_mt5_global.reset_mock() # Clears call counts, return_values, side_effects from previous tests

        # Ensure MT5 constants are on the fresh mock
        mock_mt5_global.TIMEFRAME_M1 = 1
        mock_mt5_global.TRADE_RETCODE_DONE = 10009
        mock_mt5_global.TRADE_RETCODE_PLACED = 10008
        mock_mt5_global.ORDER_TYPE_BUY = 0
        mock_mt5_global.ORDER_TYPE_SELL = 1
        mock_mt5_global.ORDER_ACTION_DEAL = 1
        # ... any other constants used during connection or basic ops ...


    @patch('src.brokers.deriv_broker.websocket.WebSocketApp') # Mock Deriv's WebSocketApp
    @patch('src.brokers.deriv_broker.threading.Thread') # Mock Deriv's Thread
    def test_get_deriv_broker_successful_connection(self, mock_thread, mock_ws_app_constructor):
        mock_ws_app_instance = MagicMock()
        mock_ws_app_constructor.return_value = mock_ws_app_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Simulate successful connection and ping for DerivBroker's connect()
        # This involves _send_json_request being called for authorize and then for ping
        def send_request_side_effect(*args, **kwargs):
            payload = args[0] # The payload is the first argument to _send_json_request
            if payload.get("authorize"):
                return {
                    "authorize": {"loginid": "VRTC123", "currency": "USD"},
                    "echo_req": {"authorize": "testtoken", "req_id": payload.get("req_id")}
                }
            if payload.get("ping"):
                return {"ping": "pong", "echo_req": {"ping": 1, "req_id": payload.get("req_id")}}
            return {}

        # Need to patch _send_json_request on the DerivBroker class temporarily, or on the instance
        # Patching it on the instance after creation is easier if get_broker doesn't fail before that.
        # However, get_broker calls connect which calls _send_json_request.
        # So, we patch it on the class for the duration of this test.

        with patch.object(DerivBroker, '_send_json_request', side_effect=send_request_side_effect) as mock_deriv_send:
            config = {"app_id": 1089, "api_key": "testtoken"}
            broker = broker_factory.get_broker("deriv", **config) # Using **config unpacks api_key too
            self.assertIsNotNone(broker)
            self.assertIsInstance(broker, DerivBroker)
            self.assertTrue(broker._is_connected) # connect() should set this
            mock_deriv_send.assert_any_call({"authorize": "testtoken"}, timeout=15)


    def test_get_icmarkets_broker_successful_connection(self):
        # Configure the global mock_mt5_global for this test
        mock_mt5_global.initialize.return_value = True
        mock_mt5_global.terminal_info.return_value = create_mock_mt5_terminal_info(connected=True)
        mock_mt5_global.account_info.return_value = create_mock_mt5_account_info(
            login=12345, balance=10000.0, currency="USD"
        )

        config = {"login_id": 12345, "password": "password", "server": "ICServer", "mt5_path": "path"}
        broker = broker_factory.get_broker("icmarkets", **config)

        self.assertIsNotNone(broker)
        self.assertIsInstance(broker, ICMarketsBroker)
        self.assertTrue(broker._is_connected)
        mock_mt5_global.initialize.assert_called_with(
            login=12345, password="password", server="ICServer", path="path", timeout=ANY
        )

    def test_get_xm_broker_successful_connection(self):
        mock_mt5_global.initialize.return_value = True
        mock_mt5_global.terminal_info.return_value = create_mock_mt5_terminal_info(connected=True)
        mock_mt5_global.account_info.return_value = create_mock_mt5_account_info(
            login=67890, balance=5000.0, currency="EUR"
        )

        config = {"login_id": 67890, "password": "xm_password", "server": "XMServer", "mt5_path": "xm_path"}
        broker = broker_factory.get_broker("xm", **config)

        self.assertIsNotNone(broker)
        self.assertIsInstance(broker, XMBroker) # Check it's an XMBroker instance
        self.assertTrue(broker._is_connected) # Inherited connect logic
        mock_mt5_global.initialize.assert_called_with(
            login=67890, password="xm_password", server="XMServer", path="xm_path", timeout=ANY
        )

    def test_get_exness_broker_successful_connection(self):
        mock_mt5_global.initialize.return_value = True
        mock_mt5_global.terminal_info.return_value = create_mock_mt5_terminal_info(connected=True)
        mock_mt5_global.account_info.return_value = create_mock_mt5_account_info(
            login=13579, balance=2000.0, currency="GBP"
        )

        config = {"login_id": 13579, "password": "ex_password", "server": "ExnessServer", "mt5_path": "ex_path"}
        broker = broker_factory.get_broker("exness", **config)

        self.assertIsNotNone(broker)
        self.assertIsInstance(broker, ExnessBroker) # Check it's an ExnessBroker instance
        self.assertTrue(broker._is_connected) # Inherited connect logic
        mock_mt5_global.initialize.assert_called_with(
            login=13579, password="ex_password", server="ExnessServer", path="ex_path", timeout=ANY
        )

    def test_get_unregistered_broker(self):
        broker = broker_factory.get_broker("unknown_broker", config={})
        self.assertIsNone(broker)

    def test_get_broker_connect_fails_for_mt5_subclass(self):
        # Test that if connect fails (e.g. mt5.initialize returns False), get_broker returns None
        mock_mt5_global.initialize.return_value = False
        mock_mt5_global.last_error.return_value = (12, "Test init fail") # Some error code

        config = {"login_id": 123, "password": "password", "server": "TestServer"}
        broker = broker_factory.get_broker("icmarkets", **config)
        self.assertIsNone(broker) # BrokerFactory's get_broker should return None if connect fails

    @patch.object(DerivBroker, 'connect', side_effect=ConnectionError("Test Deriv Connect Fail"))
    def test_get_broker_connect_fails_for_deriv(self, mock_deriv_connect):
        config = {"app_id": 1089, "api_key": "testtoken"}
        broker = broker_factory.get_broker("deriv", **config)
        self.assertIsNone(broker)
        mock_deriv_connect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
