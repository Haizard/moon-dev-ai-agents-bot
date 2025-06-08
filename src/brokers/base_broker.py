"""
🌙 Moon Dev's Base Broker Interface
Built with love by Moon Dev 🚀

This module defines the abstract base class for all broker integrations.
"""

import abc
from typing import Dict, List, Optional, Any
import pandas as pd

class BaseBroker(abc.ABC):
    """
    Abstract base class for broker integrations.
    Defines a common interface for interacting with different brokers.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the BaseBroker.

        Args:
            api_key (Optional[str]): The API key for the broker.
            api_secret (Optional[str]): The API secret for the broker.
            config (Optional[Dict[str, Any]]): A dictionary containing other broker-specific configurations.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.config = config if config else {}
        self.client: Optional[Any] = None # To be initialized by subclasses in connect()

    @abc.abstractmethod
    def connect(self) -> None:
        """
        Establishes a connection to the broker.
        Implementations should set up the broker client and authenticate.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self) -> None:
        """
        Closes the connection to the broker.
        Implementations should clean up any resources or connections.
        """
        raise NotImplementedError

    def ping(self) -> bool:
        """
        Checks the connectivity to the broker.
        Optional to implement; base implementation returns True if client is not None.
        Subclasses should provide a more specific check if possible.

        Returns:
            bool: True if connected or client seems available, False otherwise.
        """
        return self.client is not None

    @abc.abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """
        Retrieves the account balance from the broker.

        Returns:
            Dict[str, float]: A dictionary where keys are asset symbols (e.g., 'USD', 'BTC')
                              and values are the corresponding balances (as floats).
                              Example: {'USD': 10000.50, 'BTC': 0.5}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_ohlcv(self, instrument: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Fetches OHLCV (Open, High, Low, Close, Volume) data for a given instrument.

        Args:
            instrument (str): The trading instrument symbol (e.g., 'BTC/USD', 'ETH/USDT').
            timeframe (str): The timeframe for the candles (e.g., '1m', '5m', '1h', '1d').
            since (Optional[int]): The starting timestamp in milliseconds for fetching data.
                                   If None, fetches the most recent data.
            limit (Optional[int]): The maximum number of candles to fetch.
                                   Broker-specific limits may apply.

        Returns:
            pd.DataFrame: A Pandas DataFrame with columns:
                          ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
                          'timestamp' should be in milliseconds.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def place_market_order(self, instrument: str, side: str, qty: float, **kwargs) -> Dict[str, Any]:
        """
        Places a market order.

        Args:
            instrument (str): The trading instrument symbol.
            side (str): The order side ('buy' or 'sell').
            qty (float): The quantity of the instrument to trade.
            **kwargs: Additional broker-specific parameters.

        Returns:
            Dict[str, Any]: A dictionary containing details of the placed order,
                            including at least an 'order_id'.
                            Example: {'order_id': '12345', 'status': 'filled', ...}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def place_limit_order(self, instrument: str, side: str, qty: float, price: float, **kwargs) -> Dict[str, Any]:
        """
        Places a limit order.

        Args:
            instrument (str): The trading instrument symbol.
            side (str): The order side ('buy' or 'sell').
            qty (float): The quantity of the instrument to trade.
            price (float): The price at which to place the limit order.
            **kwargs: Additional broker-specific parameters.

        Returns:
            Dict[str, Any]: A dictionary containing details of the placed order,
                            including at least an 'order_id'.
                            Example: {'order_id': '67890', 'status': 'open', ...}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Fetches the status of a specific order by its ID.

        Args:
            order_id (str): The unique identifier of the order.

        Returns:
            Dict[str, Any]: A dictionary containing the order status details,
                            e.g., 'status', 'filled_qty', 'avg_price'.
                            Example: {'order_id': '12345', 'status': 'closed', 'filled_qty': 0.1, ...}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all open positions.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                  represents an open position.
            Example: [
                {'instrument': 'BTC/USD', 'qty': 0.1, 'entry_price': 50000.0, 'side': 'long'},
                {'instrument': 'ETH/USD', 'qty': 2.5, 'entry_price': 3000.0, 'side': 'long'}
            ]
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_instrument_details(self, instrument: str) -> Dict[str, Any]:
        """
        Fetches details about a specific trading instrument.

        Args:
            instrument (str): The trading instrument symbol.

        Returns:
            Dict[str, Any]: A dictionary containing instrument-specific details,
                            such as minimum order size, price precision, quantity precision, etc.
            Example: {'min_order_size': 0.001, 'tick_size': 0.01, 'quote_asset': 'USD', ...}
        """
        raise NotImplementedError

# Example of potential future dataclasses (not strictly required by the task yet)
# from dataclasses import dataclass

# @dataclass
# class Balance:
#     asset: str
#     free: float
#     locked: float
#     total: float

# @dataclass
# class Order:
#     order_id: str
#     instrument: str
#     side: str
#     type: str # 'market', 'limit'
#     status: str
#     qty: float
#     filled_qty: float
#     avg_price: Optional[float] = None
#     limit_price: Optional[float] = None
#     timestamp: int # Creation timestamp in ms

# @dataclass
# class Position:
#     instrument: str
#     qty: float
#     entry_price: float
#     side: str # 'long', 'short'
#     unrealized_pnl: Optional[float] = None
#     liquidation_price: Optional[float] = None
#     # Add other relevant fields
