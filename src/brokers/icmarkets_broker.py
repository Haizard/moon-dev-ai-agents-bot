"""
🌙 Moon Dev's IC Markets Broker Integration
Built with love by Moon Dev 🚀

This module implements the BaseBroker interface for IC Markets,
primarily by interacting with the MetaTrader 5 terminal.
"""

import pandas as pd
from typing import Optional, Dict, List, Any, Union
from termcolor import cprint
import time
import datetime

from .base_broker import BaseBroker

try:
    import MetaTrader5 as mt5
except ImportError:
    cprint("⚠️ MetaTrader5 library not found. This broker will not function. "
           "Please install it (usually on Windows) and ensure MetaTrader 5 terminal is running.", "red")
    mt5 = None
except Exception as e:
    cprint(f"⚠️ Error importing MetaTrader5 library: {e}. This broker will not function. "
           "Ensure MetaTrader 5 terminal is installed and library is compatible with your OS.", "red")
    mt5 = None

class ICMarketsBroker(BaseBroker):
    TIMEFRAME_MAP = {
        "1m": mt5.TIMEFRAME_M1 if mt5 else None,
        "5m": mt5.TIMEFRAME_M5 if mt5 else None,
        "15m": mt5.TIMEFRAME_M15 if mt5 else None,
        "30m": mt5.TIMEFRAME_M30 if mt5 else None,
        "1h": mt5.TIMEFRAME_H1 if mt5 else None,
        "4h": mt5.TIMEFRAME_H4 if mt5 else None,
        "1d": mt5.TIMEFRAME_D1 if mt5 else None,
        "1w": mt5.TIMEFRAME_W1 if mt5 else None,
        "1M": mt5.TIMEFRAME_MN1 if mt5 else None,
    }

    ORDER_TYPE_MAP = {
        "buy": mt5.ORDER_TYPE_BUY if mt5 else None,
        "sell": mt5.ORDER_TYPE_SELL if mt5 else None,
        "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT if mt5 else None,
        "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT if mt5 else None,
        # Add other types like stop orders if needed
    }

    POSITION_TYPE_MAP = {
        (mt5.POSITION_TYPE_BUY if mt5 else -1): "long",
        (mt5.POSITION_TYPE_SELL if mt5 else -1): "short",
    }

    MT5_RETCODE_MAP = {
        10004: "Requote",
        10006: "Request rejected",
        10007: "Request canceled by trader",
        10008: "Order placed",
        10009: "Request completed", # Often success for market orders
        10010: "Request completed partially",
        10011: "Request processing error",
        10012: "Request timed out",
        10013: "Invalid request",
        10014: "Invalid volume in request",
        10015: "Invalid price in request",
        10016: "Invalid stops in request",
        10017: "Trade is disabled",
        10018: "Market is closed",
        10019: "There is not enough money to complete the request",
        10020: "Prices changed",
        10021: "There are no quotes to process the request",
        10022: "Invalid order expiration date in request",
        10023: "Order state changed",
        10024: "Too frequent requests",
        10025: "No changes in request",
        10026: "Autotrading disabled by server",
        10027: "Autotrading disabled by client terminal",
        10028: "Request locked for processing",
        10029: "Order or position frozen",
        10030: "Invalid order filling type",
        10031: "No connection with the trade server",
        10032: "Operation allowed only for live accounts",
        10033: "The number of pending orders has reached the limit",
        10034: "The volume of orders and positions for the symbol has reached the limit",
        10035: "Incorrect or prohibited order type",
        10036: "Position with the specified POSITION_IDENTIFIER has already been closed",
        10038: "A close volume exceeds the current position volume",
        10039: "A close order already exists for a specified position",
        10040: "The number of open positions simultaneously present on an account can be limited by the server settings",
        10041: "The pending order activation request is rejected, the order is canceled",
        10042: "The request is rejected, because the rule \"Only position closing is allowed\" is set for the symbol",
        10043: "The request is rejected, because the rule \"Only position closing is allowed\" is set for the trading account",
        10044: "The request is rejected, because the rule \"Position closing is allowed only by FIFO rule\" is set for the trading account",
        10045: "The request is rejected, because the rule \"Opposite positions on a single symbol are disabled\" is set for the trading account"
    }


    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, api_secret, config)

        if not mt5:
            raise ImportError("MetaTrader5 library is not available. Cannot initialize ICMarketsBroker.")

        self.login_id: Optional[int] = None
        if self.config.get('login_id') is not None:
            try:
                self.login_id = int(self.config['login_id'])
            except ValueError:
                 cprint(f"⚠️ Invalid 'login_id' in config: '{self.config['login_id']}'. Must be numeric.", "yellow")
        elif api_key is not None:
            try:
                self.login_id = int(api_key)
            except ValueError:
                cprint(f"⚠️ 'api_key' ('{api_key}') is not a valid numeric login_id for MT5.", "yellow")

        self.password: Optional[str] = self.config.get('password', api_secret)
        self.server: Optional[str] = self.config.get('server')
        self.mt5_path: Optional[str] = self.config.get('mt5_path')
        self.default_slippage = self.config.get('slippage_points', 5) # Default 5 points slippage
        self.default_magic = self.config.get('magic_number', 12345)

        if not self.login_id or not self.password or not self.server:
            cprint("❌ IC Markets (MT5) login_id, password, or server not fully provided. Connection will fail.", "red")

        self.client = None
        self._is_connected: bool = False

    def connect(self) -> None:
        cprint(f"Attempting to connect to IC Markets (MetaTrader 5 Terminal) for account {self.login_id} on server {self.server}...", "magenta")
        if self._is_connected:
            cprint("ℹ️ Already connected to IC Markets (MT5).", "blue")
            return

        if not self.login_id or not self.password or not self.server:
            raise ConnectionError("IC Markets (MT5) connection failed: Login ID, password, or server is missing.")

        if not mt5:
             raise ConnectionError("MetaTrader5 library not imported. Cannot connect.")

        init_params = {
            "login": self.login_id,
            "password": self.password,
            "server": self.server,
            "timeout": self.config.get('connect_timeout_ms', 20000),
        }
        if self.mt5_path:
            init_params["path"] = self.mt5_path

        initialized = mt5.initialize(**init_params) # type: ignore

        if not initialized:
            error_code = mt5.last_error()
            mt5.shutdown()
            raise ConnectionError(f"Failed to initialize MetaTrader 5 terminal (Error code: {error_code}). "
                                  "Ensure terminal is running and credentials/path are correct.")

        terminal_info = mt5.terminal_info()
        if not terminal_info or not terminal_info.connected: # type: ignore
            mt5.shutdown()
            raise ConnectionError(f"MetaTrader 5 terminal is not connected to broker. Info: {terminal_info}")

        account_info = mt5.account_info()
        if account_info is None or account_info.login != self.login_id: # type: ignore
            error_code = mt5.last_error()
            cprint(f"❌ MetaTrader5 login failed or account mismatch. Account Info: {account_info}. Error: {error_code}", "red")
            mt5.shutdown()
            raise ConnectionError(f"Failed to login to MetaTrader 5 account {self.login_id} on server {self.server}. Error: {error_code}")

        self._is_connected = True
        self.client = mt5
        cprint(f"✅ Successfully connected and logged into IC Markets (MT5) account: {account_info.login}", "green")

    def disconnect(self) -> None:
        cprint("Disconnecting from IC Markets (MetaTrader 5 Terminal)...", "magenta")
        if mt5:
            mt5.shutdown()
        self._is_connected = False
        self.client = None
        cprint("✅ Disconnected from MetaTrader 5.", "green")

    def ping(self) -> bool:
        if not mt5 or not self._is_connected:
            return False

        terminal_info = mt5.terminal_info()
        if terminal_info and terminal_info.connected: # type: ignore
            account_info = mt5.account_info()
            if account_info and account_info.login == self.login_id: # type: ignore
                return True
            else:
                cprint(f"⚠️ Ping: MT5 account info mismatch or unavailable. Expected {self.login_id}, got {account_info}", "yellow")
                self._is_connected = False
                return False

        cprint("⚠️ Ping: MT5 terminal not connected.", "yellow")
        self._is_connected = False
        return False

    def get_account_balance(self) -> Dict[str, float]:
        if not self._is_connected or not self.client:
            raise ConnectionError("Not connected to IC Markets (MT5). Call connect() first.")
        if not mt5:
            raise RuntimeError("MetaTrader5 library not available.")

        account_info = mt5.account_info()
        if account_info:
            balance = float(account_info.balance) # type: ignore
            currency = str(account_info.currency) # type: ignore
            return {currency: balance}
        else:
            error_code = mt5.last_error()
            cprint(f"❌ Failed to retrieve account balance from MT5. Error: {error_code[1] if isinstance(error_code, tuple) else error_code}", "red")
            return {}

    def get_ohlcv(self, instrument: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> pd.DataFrame:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected to IC Markets (MT5).")

        mt5_timeframe = self.TIMEFRAME_MAP.get(timeframe)
        if mt5_timeframe is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(self.TIMEFRAME_MAP.keys())}")

        rates: Optional[Any] = None
        try:
            # Ensure symbol is selected
            if not mt5.symbol_select(instrument, True):
                cprint(f"⚠️ Could not select symbol {instrument} or it's not available. OHLCV fetch may fail.", "yellow")
                # Depending on strictness, one might raise an error here.

            if since is not None: # Prioritize 'since' if available
                start_dt = datetime.datetime.fromtimestamp(since / 1000, tz=datetime.timezone.utc)
                # If limit is also provided, use copy_rates_from with start_dt and count
                if limit:
                    rates = mt5.copy_rates_from(instrument, mt5_timeframe, start_dt, limit)
                else: # Fetch from 'since' up to now
                    rates = mt5.copy_rates_range(instrument, mt5_timeframe, start_dt, datetime.datetime.now(datetime.timezone.utc))
            elif limit is not None: # Only limit is provided, fetch latest 'limit' candles
                rates = mt5.copy_rates_from_pos(instrument, mt5_timeframe, 0, limit)
            else: # Neither provided, fetch a default number of latest candles (e.g., 100)
                rates = mt5.copy_rates_from_pos(instrument, mt5_timeframe, 0, 100) # Default to 100 candles

        except Exception as e: # Catch potential errors from MT5 calls directly
            cprint(f"❌ Error during MT5 rates call for {instrument}: {e}", "red")
            error_code = mt5.last_error()
            cprint(f"MT5 last error: {error_code[1] if isinstance(error_code, tuple) else error_code}", "red")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        if rates is None or len(rates) == 0:
            error_code = mt5.last_error()
            # Error 4806: ERR_HISTORY_TIMEOUT, often means no data for range or symbol issues
            # Error 4807: ERR_HISTORY_NOT_FOUND
            if error_code[0] != 1: # Code 1 (REQ_RET_OK) might still return empty if no data
                 cprint(f"⚠️ No OHLCV data returned for {instrument} ({timeframe}). MT5 Error: {error_code[1] if isinstance(error_code, tuple) else error_code}", "yellow")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        df = pd.DataFrame(rates)
        df.rename(columns={'time': 'timestamp', 'tick_volume': 'volume'}, inplace=True)
        # MT5 'time' is epoch seconds, convert to milliseconds
        df['timestamp'] = df['timestamp'] * 1000
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def _prepare_order_request(self, instrument: str, side: str, qty: float, order_type_key: str, price: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        if not mt5: raise RuntimeError("MetaTrader5 library not available.")

        order_type = self.ORDER_TYPE_MAP.get(order_type_key)
        if order_type is None:
            raise ValueError(f"Invalid order type key: {order_type_key}")

        request: Dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL if "market" in order_type_key else mt5.TRADE_ACTION_PENDING,
            "symbol": instrument,
            "volume": float(qty),
            "type": order_type,
            "magic": kwargs.get('magic', self.default_magic),
            "comment": kwargs.get('comment', "MoonDevTrade"),
            "deviation": kwargs.get('slippage_points', self.default_slippage) if "market" in order_type_key else 0,
        }

        if price is not None: # For limit/stop orders or market order price specification
            request["price"] = float(price)
        elif "market" in order_type_key : # For market orders, fetch current price
            tick = mt5.symbol_info_tick(instrument)
            if not tick:
                raise Exception(f"Could not get tick for {instrument} to place market order.")
            request["price"] = tick.ask if side.lower() == "buy" else tick.bid

        sl = kwargs.get('stop_loss_price') or kwargs.get('sl_price')
        tp = kwargs.get('take_profit_price') or kwargs.get('tp_price')
        if sl: request["sl"] = float(sl)
        if tp: request["tp"] = float(tp)

        # Ensure symbol is available for trading
        symbol_info = mt5.symbol_info(instrument)
        if not symbol_info:
            raise ValueError(f"Symbol {instrument} not found.")
        if not symbol_info.visible: # type: ignore
            if not mt5.symbol_select(instrument, True):
                raise Exception(f"Failed to select (enable) symbol {instrument} for trading.")
            # Re-fetch info after selection
            # symbol_info = mt5.symbol_info(instrument) # Not strictly needed if select is enough

        return request

    def _parse_order_result(self, result: Any, instrument: str, side: str, qty: float) -> Dict[str, Any]:
        if not mt5: raise RuntimeError("MetaTrader5 library not available.")
        status = "unknown"
        retcode_message = "No result object"
        order_id = None

        if result:
            retcode_message = self.MT5_RETCODE_MAP.get(result.retcode, f"Unknown retcode: {result.retcode}") # type: ignore
            order_id = str(result.order) if result.order else None # type: ignore

            if result.retcode == mt5.TRADE_RETCODE_DONE or result.retcode == mt5.TRADE_RETCODE_PLACED: # type: ignore
                status = "placed" if result.retcode == mt5.TRADE_RETCODE_PLACED else "filled" # Market orders are 'filled' (DONE)
            elif result.retcode == mt5.TRADE_RETCODE_REQUOTE or result.retcode == mt5.TRADE_RETCODE_PRICE_CHANGED : # type: ignore
                status = "requote"
            else:
                status = "error"

            return {
                "order_id": order_id,
                "instrument": instrument,
                "side": side,
                "qty": qty,
                "status_code": result.retcode, # type: ignore
                "status_message": retcode_message,
                "status": status, # Simplified status
                "comment": result.comment, # type: ignore
                "price": result.price, # type: ignore
                "volume": result.volume, # type: ignore
                "raw_result": result._asdict() if hasattr(result, '_asdict') else str(result) # type: ignore
            }
        return {
            "instrument": instrument, "side": side, "qty": qty, "status": "error",
            "status_message": retcode_message, "order_id": None
        }


    def place_market_order(self, instrument: str, side: str, qty: float, **kwargs) -> Dict[str, Any]:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected to IC Markets (MT5).")

        order_type_key = side.lower() # "buy" or "sell"
        try:
            request = self._prepare_order_request(instrument, side, qty, order_type_key, price=None, **kwargs)
            cprint(f"Sending Market Order: {request}", "blue")
            result = mt5.order_send(request) # type: ignore
            return self._parse_order_result(result, instrument, side, qty)
        except Exception as e:
            cprint(f"❌ Error placing market order for {instrument}: {e}", "red")
            return {"instrument": instrument, "side": side, "qty": qty, "status": "error", "status_message": str(e), "order_id": None}

    def place_limit_order(self, instrument: str, side: str, qty: float, price: float, **kwargs) -> Dict[str, Any]:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected to IC Markets (MT5).")

        order_type_key = f"{side.lower()}_limit" # "buy_limit" or "sell_limit"
        try:
            request = self._prepare_order_request(instrument, side, qty, order_type_key, price=price, **kwargs)
            cprint(f"Sending Limit Order: {request}", "blue")
            result = mt5.order_send(request) # type: ignore
            return self._parse_order_result(result, instrument, side, qty)
        except Exception as e:
            cprint(f"❌ Error placing limit order for {instrument}: {e}", "red")
            return {"instrument": instrument, "side": side, "qty": qty, "price": price, "status": "error", "status_message": str(e), "order_id": None}

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected.")
        try:
            ticket = int(order_id)
            order_info = mt5.orders_get(ticket=ticket) # For pending orders
            if order_info and len(order_info) > 0:
                order = order_info[0]
            else:
                order_info = mt5.history_orders_get(ticket=ticket) # For historical (filled/cancelled) orders
                if order_info and len(order_info) > 0:
                    order = order_info[0]
                else:
                    return {"order_id": order_id, "status": "not_found"}

            # Map MT5 order fields to a generic dictionary
            # MT5 order states: ORDER_STATE_STARTED, ORDER_STATE_PLACED, ORDER_STATE_CANCELED, ORDER_STATE_PARTIAL, ORDER_STATE_FILLED, ORDER_STATE_REJECTED, ORDER_STATE_EXPIRED, ORDER_STATE_REQUEST_ADD, ORDER_STATE_REQUEST_MODIFY, ORDER_STATE_REQUEST_CANCEL
            # This is a simplified mapping
            status_map = { mt5.ORDER_STATE_PLACED: "open", mt5.ORDER_STATE_FILLED: "filled", mt5.ORDER_STATE_CANCELED: "canceled", mt5.ORDER_STATE_REJECTED: "rejected", mt5.ORDER_STATE_PARTIAL: "partially_filled"}
            return {
                "order_id": str(order.ticket), # type: ignore
                "instrument": order.symbol, # type: ignore
                "status": status_map.get(order.state, "unknown"), # type: ignore
                "type": "buy" if order.type == mt5.ORDER_TYPE_BUY else "sell", # Simplified # type: ignore
                "qty_ordered": order.volume_initial, # type: ignore
                "qty_filled": order.volume_current, # type: ignore
                "price_ordered": order.price_open, # type: ignore
                "price_filled": order.price_current if order.state == mt5.ORDER_STATE_FILLED else None, # This isn't avg fill price always # type: ignore
                "raw_order": order._asdict() if hasattr(order, '_asdict') else str(order) # type: ignore
            }

        except ValueError: # If order_id is not int
             cprint(f"Invalid order_id format: {order_id}. Must be an integer.", "red")
             return {"order_id": order_id, "status": "error", "message": "Invalid order_id format."}
        except Exception as e:
            cprint(f"❌ Error getting order status for {order_id}: {e}", "red")
            return {"order_id": order_id, "status": "error", "message": str(e)}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected.")
        positions_data = mt5.positions_get() # type: ignore
        if positions_data is None:
            error_code = mt5.last_error()
            cprint(f"Failed to get open positions. Error: {error_code[1] if isinstance(error_code, tuple) else error_code}", "red")
            return []

        open_positions = []
        for pos in positions_data:
            open_positions.append({
                "position_id": str(pos.ticket),
                "instrument": pos.symbol,
                "qty": pos.volume,
                "entry_price": pos.price_open,
                "side": self.POSITION_TYPE_MAP.get(pos.type, "unknown"),
                "profit_loss": pos.profit,
                "swap": pos.swap,
                "price_current": pos.price_current,
                "raw_position": pos._asdict() if hasattr(pos, '_asdict') else str(pos)
            })
        return open_positions

    def get_instrument_details(self, instrument: str) -> Dict[str, Any]:
        if not self._is_connected or not mt5: raise ConnectionError("Not connected.")

        info = mt5.symbol_info(instrument) # type: ignore
        if info:
            return {
                "instrument": info.name,
                "description": info.description,
                "digits": info.digits,
                "spread": info.spread,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
                "trade_tick_size": info.trade_tick_size,
                "trade_tick_value": info.trade_tick_value,
                "trade_contract_size": info.trade_contract_size,
                "currency_margin": info.currency_margin,
                "currency_profit": info.currency_profit,
                "raw_details": info._asdict() if hasattr(info, '_asdict') else str(info)
            }
        else:
            error_code = mt5.last_error()
            cprint(f"Failed to get instrument details for {instrument}. Error: {error_code[1] if isinstance(error_code, tuple) else error_code}", "red")
            return {"error": f"Instrument {instrument} not found or error.", "message": str(error_code)}
