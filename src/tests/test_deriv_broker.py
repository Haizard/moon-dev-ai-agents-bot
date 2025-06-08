import unittest
from unittest.mock import patch, MagicMock, ANY
import json
import time
import pandas as pd
import threading # For checking threading.Event behavior

# Adjust Python path if necessary (similar to test_model_factory.py)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.brokers.base_broker import BaseBroker
from src.brokers.deriv_broker import DerivBroker
# Assuming websocket-client would be imported as 'websocket' in deriv_broker
# If the import is `import websocket as some_alias`, patch that alias.

# Placeholder for a valid response to an "authorize" request
AUTH_SUCCESS_RESPONSE = {
    "authorize": {
        "account_list": [
            {"account_category": "trading", "account_type": "binary", "balance": 10000.0, "currency": "USD", "is_disabled": 0, "is_virtual": 1, "landing_company_name": "virtual", "loginid": "VRTC1234567"}
        ],
        "balance": 10000.0,
        "currency": "USD",
        "email": "test@example.com",
        "fullname": "Test User",
        "is_virtual": 1,
        "landing_company_fullname": "Virtual",
        "landing_company_name": "virtual",
        "local_currencies": {"USD": {"fractional_digits": 2}},
        "loginid": "VRTC1234567",
        "scopes": ["read", "trade", "trading_information", "payments", "admin"],
        "upgradeable_landing_companies": [],
        "user_id": 12345
    },
    "echo_req": {"authorize": "test_api_key", "req_id": 1}, # req_id will vary
    "msg_type": "authorize"
}

PING_PONG_RESPONSE = {
    "ping": "pong",
    "echo_req": {"ping": 1, "req_id": 1}, # req_id will vary
    "msg_type": "ping"
}

BALANCE_RESPONSE = {
    "balance": {
        "balance": 9950.0,
        "currency": "USD",
        "id": "some_balance_id",
        "loginid": "VRTC1234567",
        "accounts": { # Example of how accounts might be structured
            "VRTC1234567": {"balance": 9950.0, "currency": "USD", "type": "trading"},
            "CR12345": {"balance": 100.0, "currency": "BTC", "type": "crypto"}
        }
    },
    "echo_req": {"balance": 1, "req_id": 1}, # req_id will vary
    "msg_type": "balance"
}


class TestDerivBroker(unittest.TestCase):

    def setUp(self):
        # Mock the websocket module itself if its import is problematic without the actual library
        self.websocket_mock = MagicMock()
        self.websocket_patcher = patch('src.brokers.deriv_broker.websocket', self.websocket_mock)
        self.mocked_websocket_module = self.websocket_patcher.start()

        # The instance of WebSocketApp that will be created by the broker
        self.mock_ws_app_instance = MagicMock()
        self.mocked_websocket_module.WebSocketApp.return_value = self.mock_ws_app_instance

        # Mock threading.Thread to control thread execution
        self.thread_patcher = patch('src.brokers.deriv_broker.threading.Thread')
        self.mock_thread_constructor = self.thread_patcher.start()
        self.mock_thread_instance = MagicMock()
        self.mock_thread_constructor.return_value = self.mock_thread_instance

        # Patch time.sleep to speed up tests
        self.sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = self.sleep_patcher.start()

        self.broker_config = {
            "app_id": 12345, # Test app_id
            # api_key will be passed to constructor directly in tests
        }
        # Instance is created per test to ensure isolation for _is_connected etc.
        # self.broker = DerivBroker(config=self.broker_config)

    def tearDown(self):
        self.websocket_patcher.stop()
        self.thread_patcher.stop()
        self.sleep_patcher.stop()
        # Ensure broker disconnects if a test connected it
        # This might be tricky if tests fail before disconnect is called.
        # if hasattr(self, 'broker') and self.broker and self.broker._is_connected:
        #     try:
        #         self.broker.disconnect()
        #     except: pass


    def test_init_success(self):
        broker = DerivBroker(config=self.broker_config, api_key="test_key")
        self.assertEqual(broker.app_id, 12345)
        self.assertEqual(broker.api_key, "test_key")
        self.assertIsNotNone(broker._lock) # Check lock is initialized

    @patch('src.brokers.deriv_broker.websocket', None) # Simulate websocket module not being importable
    def test_init_websocket_library_not_found(self):
        # Need to reload DerivBroker or test its import within a context
        # This is tricky as the module is already imported.
        # A better way is to check for the raise in __init__
        with self.assertRaises(ImportError) as context:
            # For this to work, DerivBroker module would need to be re-imported
            # with the patch active, or we test the side effect.
            # Since deriv_broker.py checks `if not websocket:` at class level,
            # this test might be more involved to set up correctly to re-trigger that check.
            # A simpler check: if websocket is None, DerivBroker constructor should fail.

            # Temporarily set the global 'websocket' (as seen by deriv_broker module) to None
            # This requires careful patching of the module where DerivBroker is defined.
            original_websocket_module = sys.modules.get('src.brokers.deriv_broker.websocket', None)
            sys.modules['src.brokers.deriv_broker.websocket'] = None # Simulate it's None when DerivBroker is defined

            # Need to re-import or reload DerivBroker for the class-level check to re-evaluate
            # This is complex. For now, let's assume the check in __init__ is primary.
            # from src.brokers.deriv_broker import DerivBroker as FreshDerivBroker # This won't work easily with existing patches

            # Let's test the __init__ check
            if hasattr(sys.modules['src.brokers.deriv_broker'], 'websocket'):
                 delattr(sys.modules['src.brokers.deriv_broker'], 'websocket') # Force it to seem unimported

            # This test setup is becoming complicated due to module-level import checks.
            # The current DerivBroker __init__ check `if not websocket:` will use the already imported one.
            # A more robust test would be to ensure DerivBroker itself fails if its 'websocket' global is None.
            # For now, let's assume the __init__ will raise the error.

            # Patch the module-level 'websocket' variable inside deriv_broker.py
            with patch.dict(sys.modules, {'src.brokers.deriv_broker.websocket': None}):
                 # This doesn't work as the module is already loaded.
                 # The check `if not websocket:` in DerivBroker refers to the `websocket` it imported.
                 # The most straightforward way is to check the instance creation:
                 if 'src.brokers.deriv_broker' in sys.modules:
                    del sys.modules['src.brokers.deriv_broker'] # Force re-import

                 # Patch the import globally before re-importing DerivBroker
                 # This is still tricky. The check is `if not websocket:` at the top of the file.
                 # The constructor also has `if not websocket: raise ImportError`. This is easier to test.

                # To test the constructor's check:
                # 1. Ensure the global `websocket` in `deriv_broker` module scope is None.
                # This requires patching it *within* that module for the duration of DerivBroker instantiation.
                # For simplicity, assume the initial check `import websocket` fails.
                # The current `DerivBroker` checks `if not websocket:` (the imported module) in `__init__`.
                pass # This test is hard to set up perfectly without deeper import manipulation.
                # The existing check in __init__ covers this if the module import itself was None.
                # Let's assume the @patch for the module works for the instance creation.

            # Simpler: Assume the global `websocket` in deriv_broker module is None.
            # This test will rely on the constructor's check.
            # We need to ensure that the 'websocket' variable *within* the scope of deriv_broker.py is None
            # when DerivBroker is instantiated.

            # This test is more about the environment than the class logic if the import itself fails.
            # The class's __init__ does have a check: `if not websocket: raise ImportError`.
            # So, if we can make the `websocket` seen by `DerivBroker` None, it should raise.

            # The initial patch `self.websocket_patcher = patch('src.brokers.deriv_broker.websocket', None)`
            # should make the `websocket` symbol within `deriv_broker` module None.
            # However, this needs to be active *before* `DerivBroker` class is defined or imported.
            # This test is fundamentally difficult with current structure.
            # We will assume the `ImportError` is raised by the `import websocket` line itself if not found.
            # The class's own check is a fallback.
            # For now, we'll test the constructor's internal check.

            # To effectively test this, we'd need to ensure the 'websocket' symbol used by
            # DerivBroker's __init__ is None.
            # Let's assume the `websocket-client` is not installed.
            # The import `import websocket` at the top of `deriv_broker.py` would fail.
            # The test for this scenario is more of an integration/environment test.
            # The class's own check: `if not websocket: raise ImportError` in __init__ is a safeguard.

            # If we could force the `websocket` variable in `deriv_broker` module to be None:
            with patch.object(sys.modules['src.brokers.deriv_broker'], 'websocket', None):
                with self.assertRaisesRegex(ImportError, "WebSocket client library .* not installed"):
                    DerivBroker(config=self.broker_config)


    def _simulate_successful_connection(self, broker_instance: DerivBroker, api_key_provided: bool = True):
        # Simulate the _on_open call which happens when ws.run_forever starts
        # and the WebSocket connection is established at the transport layer.
        broker_instance._on_open(self.mock_ws_app_instance)

        # If API key is provided, simulate the authorize response
        if api_key_provided:
            # The connect method will call _send_json_request for authorize
            # We need to ensure _send_json_request's call to ws.send works,
            # and then we manually trigger _on_message with the auth response.

            # Capture the req_id used for authorize
            # The actual send is mocked by mock_ws_app_instance.send
            # We need to find the req_id that _send_json_request will use for authorize.
            # It's easier to just prepare the response with ANY req_id that send_json_request will use.

            # When broker.connect calls _send_json_request for authorize:
            # 1. _send_json_request generates a req_id (e.g., 1)
            # 2. It stores an event for req_id=1 in _response_events
            # 3. It calls self.ws.send() (which is self.mock_ws_app_instance.send)
            # 4. It waits on the event.
            # Our test needs to:
            #    a. Let self.ws.send() be called.
            #    b. Manually form an auth success JSON string.
            #    c. Call broker_instance._on_message() with that string and the correct req_id.

            # To get the req_id, we can peek at the counter or mock _get_next_req_id
            # For simplicity, assume req_id for authorize will be 1 if it's the first call.
            # Or, make _send_json_request use the req_id from payload if present.
            # The authorize payload in connect() does not pre-set req_id, so it will be generated.

            # Let's assume the first req_id generated is 1.
            auth_response_payload = {**AUTH_SUCCESS_RESPONSE, "echo_req": {"authorize": broker_instance.api_key, "req_id": 1}}
            # Ensure the loginid in response matches what might be set from config if broker uses it
            auth_response_payload["authorize"]["loginid"] = broker_instance.account_id or AUTH_SUCCESS_RESPONSE["authorize"]["loginid"]


            # Simulate that _send_json_request is about to be called by connect's auth step
            # and then directly provide the response via _on_message
            # This is a bit of a shortcut to avoid deeply mocking the event wait/set logic inside _send_json_request for this specific call.
            # A more accurate mock would involve a custom side_effect for self.mock_ws_app_instance.send

            # Assume connect has called ws.send for authorize
            # Now, call on_message to deliver the response
            # The req_id in the response must match what _send_json_request used.
            # Let's assume _get_next_req_id returned 1 for the authorize call.
            # The actual req_id used by _send_json_request when called by connect()
            # will be broker_instance._req_id_counter -1 (if it was just incremented).
            # This is getting complex. A better mock for _send_json_request might be needed for connect.

            # Alternative: mock _send_json_request itself ONLY for the authorize call within connect.
            pass # This helper needs to be used carefully with connect's structure.

    # More tests to come for connect, disconnect, ping, get_account_balance etc.
    # The current `_simulate_successful_connection` is a placeholder for logic that will
    # correctly mock the async flow of messages during the connect and authorize sequence.

    @patch('src.brokers.deriv_broker.DerivBroker._send_json_request')
    def test_connect_success_with_api_key(self, mock_send_request):
        # Simulate a successful authorization response
        auth_response_data = AUTH_SUCCESS_RESPONSE.copy()
        # Ensure the echo_req matches what connect would send (it doesn't include req_id initially)
        auth_response_data["echo_req"] = {"authorize": "test_api_key"}
        auth_response_data["authorize"]["loginid"] = "VRTEST1" # Example loginid
        mock_send_request.return_value = auth_response_data

        broker = DerivBroker(api_key="test_api_key", config=self.broker_config)
        broker.connect() # This will call the mocked _send_json_request for authorize

        self.assertTrue(broker._is_connected)
        self.assertIsNotNone(broker.client) # client is set to ws instance
        self.assertEqual(broker.account_id, "VRTEST1")
        self.mock_ws_app_instance.run_forever.assert_called_once() # Check thread was started
        # Check that authorize was attempted
        mock_send_request.assert_called_once_with({"authorize": "test_api_key"}, timeout=15)


    def test_connect_no_api_key_pings_successfully(self):
        # Test connection without API key, relying on ping
        broker = DerivBroker(config=self.broker_config, api_key=None)

        # Mock the _send_json_request for the ping call within connect
        with patch.object(broker, '_send_json_request') as mock_send_ping_request:
            ping_response_data = PING_PONG_RESPONSE.copy()
            ping_response_data["echo_req"] = {"ping": 1, "req_id": 1} # req_id will be set by _send_json_request
            mock_send_ping_request.return_value = ping_response_data

            broker.connect()

            self.assertTrue(broker._is_connected)
            self.assertIsNotNone(broker.client)
            self.assertIsNone(broker.account_id) # No auth, no account_id from auth
            mock_send_ping_request.assert_called_once_with({"ping": 1}, timeout=5) # Check ping was called

    # Add more tests for connect failures, disconnect, ping, get_account_balance etc.

if __name__ == '__main__':
    unittest.main()
