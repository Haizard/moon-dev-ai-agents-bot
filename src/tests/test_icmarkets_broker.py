import unittest
from unittest.mock import patch, MagicMock, ANY
import pandas as pd
import numpy as np # For simulating MT5 rate arrays
import datetime

# Adjust Python path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.brokers.base_broker import BaseBroker
# ICMarketsBroker itself will try to import MetaTrader5. We will mock this import.
# from src.brokers.icmarkets_broker import ICMarketsBroker # Import later after mt5 is mocked

# Mock the MetaTrader5 module BEFORE ICMarketsBroker is imported by the test runner
# This ensures that when icmarkets_broker.py does 'import MetaTrader5 as mt5', it gets our mock.
mock_mt5_module = MagicMock()
sys.modules['MetaTrader5'] = mock_mt5_module
sys.modules['MetaTrader5'].TIMEFRAME_M1 = 1
sys.modules['MetaTrader5'].TIMEFRAME_H1 = 16385
sys.modules['MetaTrader5'].ORDER_TYPE_BUY = 0
sys.modules['MetaTrader5'].ORDER_TYPE_SELL = 1
sys.modules['MetaTrader5'].ORDER_ACTION_DEAL = 1 # For market orders
sys.modules['MetaTrader5'].TRADE_ACTION_DEAL = 1 # For market orders (synonym)
sys.modules['MetaTrader5'].ORDER_TYPE_BUY_LIMIT = 2
sys.modules['MetaTrader5'].ORDER_TYPE_SELL_LIMIT = 3
sys.modules['MetaTrader5'].TRADE_ACTION_PENDING = 0 # For pending orders (like limits)
sys.modules['MetaTrader5'].TRADE_RETCODE_DONE = 10009
sys.modules['MetaTrader5'].TRADE_RETCODE_PLACED = 10008
sys.modules['MetaTrader5'].ORDER_STATE_FILLED = 5
sys.modules['MetaTrader5'].ORDER_STATE_PLACED = 1
sys.modules['MetaTrader5'].POSITION_TYPE_BUY = 0
sys.modules['MetaTrader5'].POSITION_TYPE_SELL = 1


# Now we can import ICMarketsBroker, it will see the mocked MetaTrader5
from src.brokers.icmarkets_broker import ICMarketsBroker

# --- Mocked Data Structures ---
def create_mock_account_info(login, balance, currency, equity=None, margin=None):
    info = MagicMock()
    info.login = login
    info.balance = balance
    info.currency = currency
    info.equity = equity if equity is not None else balance
    info.margin = margin if margin is not None else balance / 2
    return info

def create_mock_terminal_info(connected=True, dll_loaded=True):
    info = MagicMock()
    info.connected = connected
    info.dll_loaded = dll_loaded
    return info

def create_mock_symbol_info_tick(symbol, bid, ask):
    tick = MagicMock()
    tick.symbol = symbol
    tick.bid = bid
    tick.ask = ask
    tick.time = int(time.time())
    return tick

def create_mock_order_send_result(retcode, order_id, price=0.0, volume=0.0, comment=""):
    res = MagicMock()
    res.retcode = retcode
    res.order = order_id
    res.price = price
    res.volume = volume
    res.comment = comment
    res._asdict = MagicMock(return_value={ # Simulate _asdict() if called
        "retcode": retcode, "order": order_id, "price": price,
        "volume": volume, "comment": comment
    })
    return res


class TestICMarketsBroker(unittest.TestCase):

    def setUp(self):
        # Reset the mock_mt5_module for each test to clear call counts, etc.
        # and re-assign it to sys.modules to ensure it's picked up if any part re-imports.
        global mock_mt5_module
        mock_mt5_module = MagicMock()
        sys.modules['MetaTrader5'] = mock_mt5_module
        # Re-assign constants on the new mock object
        sys.modules['MetaTrader5'].TIMEFRAME_M1 = 1
        sys.modules['MetaTrader5'].TIMEFRAME_H1 = 16385 # Example, actual value might differ
        sys.modules['MetaTrader5'].ORDER_TYPE_BUY = 0
        sys.modules['MetaTrader5'].ORDER_TYPE_SELL = 1
        sys.modules['MetaTrader5'].ORDER_ACTION_DEAL = 1
        sys.modules['MetaTrader5'].TRADE_ACTION_DEAL = 1
        sys.modules['MetaTrader5'].ORDER_TYPE_BUY_LIMIT = 2
        sys.modules['MetaTrader5'].ORDER_TYPE_SELL_LIMIT = 3
        sys.modules['MetaTrader5'].TRADE_ACTION_PENDING = 0
        sys.modules['MetaTrader5'].TRADE_RETCODE_DONE = 10009
        sys.modules['MetaTrader5'].TRADE_RETCODE_PLACED = 10008
        sys.modules['MetaTrader5'].ORDER_STATE_FILLED = 5
        sys.modules['MetaTrader5'].ORDER_STATE_PLACED = 1
        sys.modules['MetaTrader5'].POSITION_TYPE_BUY = 0
        sys.modules['MetaTrader5'].POSITION_TYPE_SELL = 1


        self.mt5_mock = mock_mt5_module # Use this for setting return_values

        self.broker_config = {
            "login_id": 12345,
            "password": "testpassword",
            "server": "ICMarketsSC-Demo",
            "mt5_path": "/fake/path/terminal64.exe"
        }
        # Broker instance created in each test method for isolation

    def test_init_success(self):
        broker = ICMarketsBroker(config=self.broker_config)
        self.assertEqual(broker.login_id, 12345)
        self.assertEqual(broker.password, "testpassword")
        self.assertEqual(broker.server, "ICMarketsSC-Demo")
        self.assertEqual(broker.mt5_path, "/fake/path/terminal64.exe")
        self.assertFalse(broker._is_connected)

    @patch.dict(sys.modules, {'MetaTrader5': None})
    def test_init_mt5_library_not_found(self):
        # Need to re-import the broker class with the patch active
        # This is tricky because ICMarketsBroker is already imported.
        # The check `if not mt5:` in ICMarketsBroker.__init__ is the target.

        # To test the constructor's check, we can try to instantiate it
        # after ensuring the 'mt5' seen by its module is None.
        # The global mock_mt5_module is already set up. If we set it to None:
        original_mt5_in_broker_module = sys.modules['src.brokers.icmarkets_broker'].mt5
        sys.modules['src.brokers.icmarkets_broker'].mt5 = None

        with self.assertRaisesRegex(ImportError, "MetaTrader5 library is not available"):
            ICMarketsBroker(config=self.broker_config)

        # Restore
        sys.modules['src.brokers.icmarkets_broker'].mt5 = original_mt5_in_broker_module


    def test_connect_success(self):
        self.mt5_mock.initialize.return_value = True
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=True)
        self.mt5_mock.account_info.return_value = create_mock_account_info(
            login=self.broker_config["login_id"], balance=10000.0, currency="USD"
        )

        broker = ICMarketsBroker(config=self.broker_config)
        broker.connect()

        self.assertTrue(broker._is_connected)
        self.assertEqual(broker.client, self.mt5_mock)
        self.mt5_mock.initialize.assert_called_once_with(
            login=self.broker_config["login_id"],
            password=self.broker_config["password"],
            server=self.broker_config["server"],
            path=self.broker_config["mt5_path"],
            timeout=ANY
        )
        self.mt5_mock.terminal_info.assert_called_once()
        self.mt5_mock.account_info.assert_called_once()

    def test_connect_initialize_fails(self):
        self.mt5_mock.initialize.return_value = False
        self.mt5_mock.last_error.return_value = (1, "Initialization failed") # Example error

        broker = ICMarketsBroker(config=self.broker_config)
        with self.assertRaisesRegex(ConnectionError, "Failed to initialize MetaTrader 5 terminal"):
            broker.connect()
        self.assertFalse(broker._is_connected)
        self.mt5_mock.shutdown.assert_called_once() # Should be called if init fails

    def test_connect_terminal_not_connected(self):
        self.mt5_mock.initialize.return_value = True
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=False)

        broker = ICMarketsBroker(config=self.broker_config)
        with self.assertRaisesRegex(ConnectionError, "MetaTrader 5 terminal is not connected"):
            broker.connect()
        self.assertFalse(broker._is_connected)
        self.mt5_mock.shutdown.assert_called_once()

    def test_connect_account_info_mismatch(self):
        self.mt5_mock.initialize.return_value = True
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=True)
        self.mt5_mock.account_info.return_value = create_mock_account_info(login=99999, balance=1000, currency="USD") # Wrong login
        self.mt5_mock.last_error.return_value = (2, "Login failed")

        broker = ICMarketsBroker(config=self.broker_config)
        with self.assertRaisesRegex(ConnectionError, f"Failed to login to MetaTrader 5 account {self.broker_config['login_id']}"):
            broker.connect()
        self.assertFalse(broker._is_connected)
        self.mt5_mock.shutdown.assert_called_once()

    def test_disconnect(self):
        # First, simulate a connected state
        self.mt5_mock.initialize.return_value = True
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=True)
        self.mt5_mock.account_info.return_value = create_mock_account_info(login=self.broker_config["login_id"], balance=1000.0, currency="USD")
        broker = ICMarketsBroker(config=self.broker_config)
        broker.connect()
        self.assertTrue(broker._is_connected)

        broker.disconnect()
        self.assertFalse(broker._is_connected)
        self.assertIsNone(broker.client)
        self.mt5_mock.shutdown.assert_called_once() # Shutdown called once during disconnect

    def test_ping_connected(self):
        broker = ICMarketsBroker(config=self.broker_config)
        # Simulate connected state by setting internal flags and mocks
        broker._is_connected = True
        broker.client = self.mt5_mock # Point client to the mock module
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=True)
        self.mt5_mock.account_info.return_value = create_mock_account_info(login=self.broker_config["login_id"], balance=1.0, currency="USD")

        self.assertTrue(broker.ping())

    def test_ping_not_connected_state(self):
        broker = ICMarketsBroker(config=self.broker_config)
        broker._is_connected = False # Explicitly set as not connected
        self.assertFalse(broker.ping())

    def test_ping_terminal_disconnected(self):
        broker = ICMarketsBroker(config=self.broker_config)
        broker._is_connected = True # Was connected
        broker.client = self.mt5_mock
        self.mt5_mock.terminal_info.return_value = create_mock_terminal_info(connected=False)

        self.assertFalse(broker.ping())
        self.assertFalse(broker._is_connected) # Ping should update this state

    def test_get_account_balance_success(self):
        broker = ICMarketsBroker(config=self.broker_config)
        broker._is_connected = True
        broker.client = self.mt5_mock
        mock_acc_info = create_mock_account_info(login=self.broker_config["login_id"], balance=12345.67, currency="EUR")
        self.mt5_mock.account_info.return_value = mock_acc_info

        balance = broker.get_account_balance()
        self.assertEqual(balance, {"EUR": 12345.67})
        self.mt5_mock.account_info.assert_called_once()

    def test_get_account_balance_not_connected(self):
        broker = ICMarketsBroker(config=self.broker_config)
        with self.assertRaises(ConnectionError):
            broker.get_account_balance()

    def test_get_account_balance_api_error(self):
        broker = ICMarketsBroker(config=self.broker_config)
        broker._is_connected = True
        broker.client = self.mt5_mock
        self.mt5_mock.account_info.return_value = None # Simulate API error
        self.mt5_mock.last_error.return_value = (99, "Generic error")

        balance = broker.get_account_balance()
        self.assertEqual(balance, {})


    # TODO: Add more tests for get_ohlcv, place_market_order, place_limit_order,
    # get_order_status, get_open_positions, get_instrument_details

if __name__ == '__main__':
    unittest.main()
