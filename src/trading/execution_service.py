"""
🌙 Moon Dev's Trade Execution Service
Built with love by Moon Dev 🚀

This module initializes the active trading broker via BrokerFactory
and provides standardized functions for trade execution.
"""

from typing import Optional, Dict, List, Any
from termcolor import cprint

from src.brokers.broker_factory import broker_factory
from src.brokers.base_broker import BaseBroker
from src.config import ACTIVE_TRADING_BROKER_NAME, BROKER_CONFIGS

class TradeExecutor:
    """
    Handles trade execution using the configured active trading broker.
    """
    _instance: Optional['TradeExecutor'] = None

    def __new__(cls, *args, **kwargs) -> 'TradeExecutor':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        cprint(f"\n🚀 Initializing TradeExecutor with active broker: {ACTIVE_TRADING_BROKER_NAME}", "cyan")
        self.active_broker: Optional[BaseBroker] = None

        if not ACTIVE_TRADING_BROKER_NAME:
            cprint("❌ CRITICAL: ACTIVE_TRADING_BROKER_NAME is not defined in config. TradeExecutor cannot operate.", "red")
            # Optionally raise an exception here if trading is essential
            return

        broker_config = BROKER_CONFIGS.get(ACTIVE_TRADING_BROKER_NAME, {})
        if not broker_config:
            cprint(f"⚠️ Configuration for active trading broker '{ACTIVE_TRADING_BROKER_NAME}' not found in BROKER_CONFIGS.", "yellow")
            # Proceeding will likely fail when get_broker is called without full config.

        # Extract api_key and api_secret if they are top-level in broker_config,
        # otherwise get_broker handles **broker_config which might contain them.
        api_key = broker_config.get('api_key')
        api_secret = broker_config.get('api_secret')

        self.active_broker = broker_factory.get_broker(
            broker_name=ACTIVE_TRADING_BROKER_NAME,
            api_key=api_key, # Pass explicitly if directly available
            api_secret=api_secret, # Pass explicitly
            config=broker_config # Pass the whole config dict for broker-specific params
        )

        if not self.active_broker:
            cprint(f"❌ CRITICAL: Failed to initialize active trading broker '{ACTIVE_TRADING_BROKER_NAME}'. Trading will not be possible.", "red")
            # Optionally raise an exception
            return

        try:
            cprint(f"  Connecting to active trading broker: {ACTIVE_TRADING_BROKER_NAME}...", "magenta")
            self.active_broker.connect()
            if not self.active_broker.ping(): # Verify connection
                 cprint(f"⚠️ {ACTIVE_TRADING_BROKER_NAME} connected but failed ping. Broker might not be fully operational.", "yellow")
                 # Depending on strictness, could raise error here
            else:
                 cprint(f"✅ TradeExecutor successfully connected to {ACTIVE_TRADING_BROKER_NAME}.", "green")
        except Exception as e:
            cprint(f"❌ CRITICAL: Failed to connect to active trading broker '{ACTIVE_TRADING_BROKER_NAME}': {e}", "red")
            self.active_broker = None # Ensure it's None if connection failed

        self._initialized = True

    def _check_broker(self) -> None:
        if not self.active_broker:
            raise ConnectionError("No active trading broker initialized or connection failed.")
        if not self.active_broker._is_connected: # Assuming brokers have an _is_connected attribute
             cprint(f"⚠ Broker {self.active_broker.config.get('broker_name', ACTIVE_TRADING_BROKER_NAME)} is not connected. Attempting to reconnect...", "yellow")
             try:
                 self.active_broker.connect()
                 if not self.active_broker._is_connected:
                     raise ConnectionError(f"Failed to reconnect to broker {ACTIVE_TRADING_BROKER_NAME}.")
             except Exception as e:
                 raise ConnectionError(f"Failed to reconnect to broker {ACTIVE_TRADING_BROKER_NAME}: {e}")


    def execute_market_buy(self, instrument: str, quantity: float, **kwargs) -> Dict[str, Any]:
        self._check_broker()
        cprint(f"📈 Executing MARKET BUY: {quantity} of {instrument} via {ACTIVE_TRADING_BROKER_NAME}", "green")
        # TODO: Quantity conversion/normalization might be needed here based on instrument type or broker requirements
        return self.active_broker.place_market_order(instrument, "buy", quantity, **kwargs) # type: ignore

    def execute_market_sell(self, instrument: str, quantity: float, **kwargs) -> Dict[str, Any]:
        self._check_broker()
        cprint(f"📉 Executing MARKET SELL: {quantity} of {instrument} via {ACTIVE_TRADING_BROKER_NAME}", "red")
        return self.active_broker.place_market_order(instrument, "sell", quantity, **kwargs) # type: ignore

    def execute_limit_buy(self, instrument: str, quantity: float, price: float, **kwargs) -> Dict[str, Any]:
        self._check_broker()
        cprint(f"📈 Executing LIMIT BUY: {quantity} of {instrument} at {price} via {ACTIVE_TRADING_BROKER_NAME}", "green")
        return self.active_broker.place_limit_order(instrument, "buy", quantity, price, **kwargs) # type: ignore

    def execute_limit_sell(self, instrument: str, quantity: float, price: float, **kwargs) -> Dict[str, Any]:
        self._check_broker()
        cprint(f"📉 Executing LIMIT SELL: {quantity} of {instrument} at {price} via {ACTIVE_TRADING_BROKER_NAME}", "red")
        return self.active_broker.place_limit_order(instrument, "sell", quantity, price, **kwargs) # type: ignore

    def get_order_status(self, order_id: str, **kwargs) -> Dict[str, Any]:
        self._check_broker()
        return self.active_broker.get_order_status(order_id, **kwargs) # type: ignore

    def get_open_positions(self, instrument: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        self._check_broker()
        # Note: BaseBroker.get_open_positions doesn't take instrument.
        # If filtering by instrument is needed here, it would be post-fetch or broker method needs update.
        if instrument:
            cprint(f"Fetching open positions for {instrument} via {ACTIVE_TRADING_BROKER_NAME}", "blue")
            all_positions = self.active_broker.get_open_positions(**kwargs) # type: ignore
            return [p for p in all_positions if p.get('instrument') == instrument]
        else:
            cprint(f"Fetching all open positions via {ACTIVE_TRADING_BROKER_NAME}", "blue")
            return self.active_broker.get_open_positions(**kwargs) # type: ignore


    def disconnect_active_broker(self):
        if self.active_broker and hasattr(self.active_broker, '_is_connected') and self.active_broker._is_connected:
            cprint(f"🔌 Disconnecting active trading broker: {ACTIVE_TRADING_BROKER_NAME}", "magenta")
            try:
                self.active_broker.disconnect()
            except Exception as e:
                cprint(f"❌ Error disconnecting broker {ACTIVE_TRADING_BROKER_NAME}: {e}", "red")
        elif self.active_broker:
             cprint(f"ℹ️ Active broker {ACTIVE_TRADING_BROKER_NAME} was initialized but not connected.", "blue")
        else:
             cprint("ℹ️ No active broker to disconnect.", "blue")


# Global instance for easy access
trade_executor = TradeExecutor()

# Optional: Register a cleanup function for the active broker
import atexit
atexit.register(trade_executor.disconnect_active_broker)
