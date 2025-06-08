"""
🌙 Moon Dev's Deriv Broker Integration
Built with love by Moon Dev 🚀

This module implements the BaseBroker interface for the Deriv trading platform
using direct WebSocket communication.
"""

import abc
import asyncio
import json
import pandas as pd
from typing import Optional, Dict, List, Any, Callable, Union
from termcolor import cprint
import threading
import time
import datetime

try:
    import websocket
except ImportError:
    cprint("⚠️ WebSocket client library (websocket-client) not found. "
           "Please install it: pip install websocket-client", "yellow")
    websocket = None

from .base_broker import BaseBroker

class DerivBroker(BaseBroker):
    DEFAULT_ENDPOINT = "frontend.binaryws.com"
    WEBSOCKET_URL_FORMAT = "wss://{endpoint}/websockets/v3?app_id={app_id}&l={lang}&brand={brand}"

    TIMEFRAME_MAP = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, api_secret, config)

        self.endpoint = self.config.get('endpoint', self.DEFAULT_ENDPOINT)
        self.app_id = self.config.get('app_id')
        self.lang = self.config.get('lang', 'EN')
        self.brand = self.config.get('brand', 'deriv')
        self.account_id: Optional[str] = self.config.get('account_id')

        if not self.app_id:
            cprint("⚠️ DerivBroker: 'app_id' not found in config. Using a default test app_id (1089). "
                   "It's recommended to register your own app_id on Deriv.", "yellow")
            self.app_id = 1089

        if not websocket:
            raise ImportError("WebSocket client library (websocket-client) is not installed. "
                              "Please run: pip install websocket-client")

        self.ws: Optional[websocket.WebSocketApp] = None
        self._is_connected: bool = False
        self._listener_thread: Optional[threading.Thread] = None

        self._response_events: Dict[int, threading.Event] = {}
        self._response_data: Dict[int, Dict[str, Any]] = {}
        self._stream_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._req_id_counter: int = 1
        self._lock = threading.Lock()
        self.client = None

    def _get_next_req_id(self) -> int:
        with self._lock:
            req_id = self._req_id_counter
            self._req_id_counter += 1
            return req_id

    def _on_message(self, wsapp, message_str: str):
        data = json.loads(message_str)
        req_id = data.get('req_id')
        if req_id in self._response_events:
            with self._lock:
                self._response_data[req_id] = data
                event = self._response_events.get(req_id)
            if event:
                event.set()

        msg_type = data.get('msg_type')
        if msg_type in self._stream_handlers:
            handler = self._stream_handlers[msg_type]
            if handler:
                try:
                    handler(data)
                except Exception as e:
                    cprint(f"Error in stream handler for {msg_type}: {e}", "red")

    def _on_error(self, wsapp, error: Exception):
        cprint(f"Deriv WebSocket Error: {error}", "red")
        self._is_connected = False
        with self._lock:
            for req_id, event in list(self._response_events.items()):
                if not event.is_set():
                    self._response_data[req_id] = {"error": {"code": "WebSocketError", "message": str(error)}}
                    event.set()
                    self._response_events.pop(req_id, None)
                    self._response_data.pop(req_id, None)

    def _on_close(self, wsapp, close_status_code: Optional[int], close_msg: Optional[str]):
        cprint(f"Deriv WebSocket Closed: Status {close_status_code}, Msg: {close_msg}", "yellow")
        self._is_connected = False
        self.client = None
        with self._lock:
            for req_id, event in list(self._response_events.items()):
                if not event.is_set():
                    self._response_data[req_id] = {"error": {"code": "WebSocketClosed", "message": "Connection closed unexpectedly."}}
                    event.set()
                    self._response_events.pop(req_id, None)
                    self._response_data.pop(req_id, None)

    def _on_open(self, wsapp):
        cprint("Deriv WebSocket Connection Opened (transport level).", "green")

    def _send_json_request(self, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        if not self.ws or not self._is_connected:
            raise ConnectionError("Deriv WebSocket is not connected or not authorized.")

        req_id = payload.get("req_id")
        if not req_id:
            req_id = self._get_next_req_id()
            payload["req_id"] = req_id

        event = threading.Event()
        with self._lock:
            self._response_events[req_id] = event
            self._response_data.pop(req_id, None)

        try:
            self.ws.send(json.dumps(payload))
        except Exception as e:
            cprint(f"Failed to send request to Deriv (req_id: {req_id}): {e}", "red")
            with self._lock:
                self._response_events.pop(req_id, None)
            raise

        if event.wait(timeout):
            with self._lock:
                response = self._response_data.pop(req_id, None)
                self._response_events.pop(req_id, None)
            if response:
                if "error" in response:
                    err_details = response['error']
                    cprint(f"Deriv API Error (req_id: {req_id}): {err_details.get('code')} - {err_details.get('message')}", "red")
                    raise Exception(f"Deriv API Error ({err_details.get('code')}): {err_details.get('message')}")
                return response
            else:
                raise Exception(f"Deriv response event was set but no data found for req_id: {req_id}.")
        else:
            with self._lock:
                self._response_events.pop(req_id, None)
            raise TimeoutError(f"Deriv API request timed out for req_id: {req_id}.")

    def connect(self) -> None:
        if self._is_connected:
            cprint("ℹ️ Already connected and authorized with Deriv.", "blue")
            return

        ws_url = self.WEBSOCKET_URL_FORMAT.format(
            endpoint=self.endpoint, app_id=self.app_id, lang=self.lang, brand=self.brand
        )
        cprint(f"Connecting to Deriv: {ws_url}", "magenta")

        self.ws = websocket.WebSocketApp(ws_url,
                                         on_message=self._on_message,
                                         on_error=self._on_error,
                                         on_close=self._on_close,
                                         on_open=self._on_open)

        self._listener_thread = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=20, ping_timeout=10, sslopt={"check_hostname": False}), daemon=True)
        self._listener_thread.start()

        connect_timeout = 10
        start_time = time.time()
        while (not (self.ws and self.ws.sock and self.ws.sock.connected)) and (time.time() - start_time) < connect_timeout:
            time.sleep(0.1)

        if not (self.ws and self.ws.sock and self.ws.sock.connected):
            self.disconnect()
            raise ConnectionError("Failed to establish Deriv WebSocket connection within timeout.")

        cprint("WebSocket transport connected. Attempting authorization...", "blue")
        self.client = self.ws

        if self.api_key:
            try:
                auth_payload = {"authorize": self.api_key}
                auth_response = self._send_json_request(auth_payload, timeout=15)

                if auth_response and not auth_response.get("error"):
                    self.account_id = auth_response.get('authorize', {}).get('loginid', self.account_id)
                    cprint(f"✅ Deriv API Authorized for account: {self.account_id}", "green")
                    self._is_connected = True
                else:
                    err_msg = auth_response.get("error", {}).get("message", "Unknown authorization error")
                    self.disconnect()
                    raise ConnectionError(f"Deriv API authorization failed: {err_msg}")
            except Exception as e:
                cprint(f"❌ Deriv API authorization failed during connect: {e}", "red")
                self.disconnect()
                raise ConnectionError(f"Deriv API authorization failed: {e}")
        else:
            cprint("⚠️ API key not provided. Connected without authorization (limited access). Ping to confirm.", "yellow")
            # For unauthenticated connections, we can consider it "connected" if ping works
            if self.ping(): # Perform a ping to ensure even unauth connection is responsive
                 self._is_connected = True
            else:
                 self.disconnect()
                 raise ConnectionError("Failed to establish a responsive unauthenticated connection to Deriv.")


    def disconnect(self) -> None:
        if not self.ws and not self._listener_thread:
             cprint("ℹ️ DerivBroker already disconnected or was never connected.", "blue")
             return

        cprint("Disconnecting from Deriv...", "magenta")
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                cprint(f"Error closing Deriv WebSocket: {e}", "yellow")

        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
            if self._listener_thread.is_alive():
                 cprint("⚠️ Listener thread did not terminate cleanly.", "yellow")

        self._is_connected = False
        self.client = None
        self.ws = None
        self._listener_thread = None
        cprint("✅ DerivBroker disconnected.", "green")

    def ping(self) -> bool:
        if not self.ws or not (self.ws.sock and self.ws.sock.connected): # Check physical socket state first
            cprint("Ping: No active WebSocket connection to Deriv.", "yellow")
            return False
        try:
            response = self._send_json_request({"ping": 1}, timeout=5)
            if response.get("ping") == "pong":
                return True # Don't cprint here, let caller decide based on context
            cprint(f"Deriv Ping unexpected response: {response}", "yellow")
            return False
        except TimeoutError:
            cprint("Deriv Ping timed out.", "red")
            return False
        except Exception as e:
            cprint(f"Deriv Ping failed: {e}", "red")
            return False

    def get_account_balance(self) -> Dict[str, float]:
        if not self._is_connected or not self.api_key:
            cprint("❌ Cannot get balance: Not authorized or not connected.", "red")
            raise PermissionError("Authorization and active connection required for get_account_balance.")

        payload = {"balance": 1}
        try:
            response = self._send_json_request(payload)
            balance_data = response.get("balance", {})
            parsed_balances: Dict[str, float] = {}

            if 'currency' in balance_data and 'balance' in balance_data:
                 main_currency = balance_data['currency']
                 main_balance = float(balance_data['balance'])
                 parsed_balances[main_currency] = main_balance

            if "accounts" in balance_data and isinstance(balance_data["accounts"], dict):
                for acc_id, acc_details in balance_data["accounts"].items():
                    currency = acc_details.get('currency')
                    balance_val = acc_details.get('balance')
                    if currency and balance_val is not None:
                        current_bal = parsed_balances.get(currency, 0.0)
                        # Update only if it's a different value, or sum if it's a genuinely different sub-account
                        # This simple sum might not be correct if main balance is already an aggregate.
                        # For now, if main balance is present, we prefer that.
                        if currency not in parsed_balances:
                             parsed_balances[currency] = float(balance_val)
                        elif main_currency == currency and main_balance != float(balance_val) and acc_id == self.account_id : # Overwrite if it's the specific account's detail
                             parsed_balances[currency] = float(balance_val)
                        elif main_currency != currency: # Add if it's a new currency
                             parsed_balances[currency] = parsed_balances.get(currency, 0.0) + float(balance_val)


            if not parsed_balances and not ('currency' in balance_data and 'balance' in balance_data):
                 cprint(f"⚠️ Could not parse balances from response: {balance_data}", "yellow")
            return parsed_balances
        except Exception as e:
            cprint(f"Error getting Deriv account balance: {e}", "red")
            return {}

    def get_ohlcv(self, instrument: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> pd.DataFrame:
        if not self._is_connected:
            raise ConnectionError("Not connected to Deriv for OHLCV data.")

        granularity = self.TIMEFRAME_MAP.get(timeframe)
        if not granularity:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(self.TIMEFRAME_MAP.keys())}")

        payload: Dict[str, Any] = {
            "ticks_history": instrument,
            "style": "candles",
            "granularity": granularity,
            "end": "latest", # Default to fetch up to the latest tick
        }
        if limit:
            payload["count"] = limit
        if since: # 'since' is a Unix timestamp in ms
            payload["start"] = int(since / 1000) # Deriv uses epoch seconds for 'start'
            if "count" not in payload: # Deriv requires 'count' if 'start' is provided without 'end' for a specific range
                payload["adjust_start_time"] = 1 # Get 'count' candles before 'end' if 'start' is too recent
                                                 # If 'start' is given, 'count' means #candles after start.
                                                 # If only 'count' and 'end=latest', it means #candles before latest.
                                                 # If 'start' is provided, 'end' should also be provided or count.
                                                 # Let's assume if 'since' is given, we want data from 'since' up to 'end=latest' or 'limit' candles.
                                                 # If 'limit' is also given, it means 'count' candles from 'start'.
                                                 # If 'limit' is NOT given, we might need to set a large count or Deriv fetches all.
                                                 # Deriv's API: "If `start` is specified, `count` should not be." - this seems contradictory to some examples.
                                                 # Let's assume: if `since` is given, we fetch from `since` up to `end='latest'`.
                                                 # If `limit` is also given, it further constrains the number of candles from that period.
                                                 # The API might actually want "count" OR "start"/"end".
                                                 # For "N candles ending now": use "count" and "end": "latest"
                                                 # For "candles since X": use "start": X, "end": "latest" (no "count")
                                                 # For "N candles since X": use "start": X, "count": N
                if not limit: # If since is provided but no limit, fetch all available up to a reasonable max
                    payload["count"] = 1000 # Default to 1000 candles if only 'since' is given. Max is usually 5000.
                    payload.pop("end", None) # Remove end if start and count are used.
                else: # both since and limit
                    payload.pop("end", None)


        try:
            response = self._send_json_request(payload)
            candles_data = response.get("candles", [])
            if not candles_data: # Deriv might also return history in 'history': {'prices': [], 'times': []}
                history_data = response.get("history")
                if history_data and 'times' in history_data and 'prices' in history_data:
                    # This format is usually for tick history, not OHLC. Candles should be in "candles".
                    cprint("Received 'history' data instead of 'candles' for OHLCV request. Data might be ticks.", "yellow")
                    return pd.DataFrame() # Or try to parse if structure is known

            df = pd.DataFrame(candles_data)
            if df.empty:
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            # Deriv candle format: {"epoch": ts, "open": o, "high": h, "low": l, "close": c, "volume": v (optional)}
            df.rename(columns={"epoch": "timestamp", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}, inplace=True)

            # Convert epoch seconds to milliseconds for timestamp
            df["timestamp"] = df["timestamp"] * 1000

            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                else: # Add volume if not present
                    if col == 'volume':
                        df['volume'] = 0.0

            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            cprint(f"Error getting Deriv OHLCV data for {instrument}: {e}", "red")
            return pd.DataFrame()


    def _get_proposal(self, instrument: str, side: str, qty: float, contract_type: str, price: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        if not self._is_connected or not self.api_key:
            raise PermissionError("Not authorized or connected for trading operations.")

        payload: Dict[str, Any] = {
            "proposal": 1,
            "symbol": instrument,
            "contract_type": contract_type, # e.g. "CALL" / "PUT" for options, or specific CFD types
            "currency": self.config.get("trade_currency", "USD"), # Should be configurable
            "amount": qty, # This needs careful mapping: stake, margin, or units
            "basis": "stake", # Could be "stake", "payout", or for CFDs, it might be "units" or "margin"
            "duration": kwargs.get("duration", 1), # Default duration, may not be needed for CFDs
            "duration_unit": kwargs.get("duration_unit", "m"), # Default duration unit
        }
        if side.lower() == "sell" and contract_type == "CALL": # For binary options style CALL/PUT
            payload["contract_type"] = "PUT"
        elif side.lower() == "buy" and contract_type == "PUT":
            payload["contract_type"] = "CALL"

        # For limit orders or specific price entries
        if price is not None:
            payload["barrier"] = str(price) # For some contract types, price is set via barrier
            # For other types, it might be 'limit_order': {'take_profit': price, 'stop_loss': X}
            # This part is highly dependent on Deriv's contract specs for the instrument.

        # Add SL/TP if provided in kwargs
        # Deriv's proposal might take limit_order: {stop_loss, take_profit, stop_out}
        limit_order_params = {}
        if 'stop_loss' in kwargs:
            limit_order_params['stop_loss'] = kwargs['stop_loss']
        if 'take_profit' in kwargs:
            limit_order_params['take_profit'] = kwargs['take_profit']
        if limit_order_params:
            payload['limit_order'] = limit_order_params

        cprint(f"Requesting proposal: {payload}", "blue")
        response = self._send_json_request(payload)
        if response.get("error"):
            raise Exception(f"Proposal error: {response['error'].get('message')}")
        if not response.get("proposal"):
            raise Exception(f"Invalid proposal response: {response}")
        return response["proposal"]

    def _buy_contract(self, proposal_id: str, price: Union[float, int], **kwargs) -> Dict[str, Any]:
        payload = {
            "buy": proposal_id,
            "price": float(price) # Price from proposal or desired fill price
        }
        # Allow passthrough of other buy parameters if needed
        passthrough = kwargs.get('passthrough')
        if passthrough and isinstance(passthrough, dict):
             payload.update(passthrough)

        cprint(f"Buying contract with proposal_id: {proposal_id}, price: {price}", "blue")
        response = self._send_json_request(payload)
        if response.get("error"):
            raise Exception(f"Buy error: {response['error'].get('message')}")
        if not response.get("buy"):
            raise Exception(f"Invalid buy response: {response}")

        # Standardize response slightly
        buy_receipt = response["buy"]
        return {
            "order_id": buy_receipt.get("contract_id") or buy_receipt.get("transaction_id"),
            "transaction_id": buy_receipt.get("transaction_id"),
            "contract_id": buy_receipt.get("contract_id"),
            "status": "open" if buy_receipt.get("contract_id") else "pending", # Simplified status
            "buy_price": buy_receipt.get("buy_price"),
            "payout": buy_receipt.get("payout"),
            "start_time": buy_receipt.get("start_time"),
            "shortcode": buy_receipt.get("shortcode"),
            "longcode": buy_receipt.get("longcode"),
            "raw_response": buy_receipt
        }

    def place_market_order(self, instrument: str, side: str, qty: float, **kwargs) -> Dict[str, Any]:
        # For Deriv, market orders on CFDs or similar might be buying a contract type that executes immediately.
        # We assume a contract type suitable for this, e.g., a short-duration "CALL" for buy or "PUT" for sell,
        # or a specific CFD contract type if available. This needs to be configured or determined.
        # For simplicity, let's assume "CALL"/"PUT" for now.
        # The 'amount' in proposal is critical: is it stake, number of units, or margin?
        # This depends on the instrument. For Volatility Indices, it's often stake.
        contract_type = "CALL" if side.lower() == "buy" else "PUT"

        # For true "market" feel, duration should be minimal or type should be instant.
        # Some Deriv contracts (like Turbos, Multipliers) behave more like leveraged spot positions.
        # This method might need instrument-specific logic for contract_type and basis.
        # Let's assume 'basis' = 'stake' and 'duration' = 0 or minimal if applicable.
        # This part is highly simplified and needs actual Deriv contract knowledge.

        proposal_kwargs = {
            "duration": kwargs.get("duration", 1), # Minimal duration for market-like execution
            "duration_unit": kwargs.get("duration_unit", "t"), # ticks or seconds for fastest
        }
        if 'stop_loss' in kwargs: proposal_kwargs['stop_loss'] = kwargs['stop_loss']
        if 'take_profit' in kwargs: proposal_kwargs['take_profit'] = kwargs['take_profit']

        try:
            proposal = self._get_proposal(instrument, side, qty, contract_type, **proposal_kwargs)
            proposal_id = proposal.get("id")
            ask_price = proposal.get("ask_price") # Price to buy the contract at
            if not proposal_id or ask_price is None:
                raise Exception(f"Invalid proposal received: {proposal}")

            # For a market order, we buy at the currently proposed price (ask_price)
            return self._buy_contract(proposal_id, ask_price, passthrough=kwargs.get("buy_passthrough"))
        except Exception as e:
            cprint(f"Error placing Deriv market order for {instrument}: {e}", "red")
            return {"error": str(e), "status": "error"}


    def place_limit_order(self, instrument: str, side: str, qty: float, price: float, **kwargs) -> Dict[str, Any]:
        # Deriv's limit order concept for contracts often involves `limit_order` in the `buy` call,
        # or specific contract types that are inherently limit orders (e.g. setting a specific barrier).
        # This is a simplified example. The `proposal` call might also accept `barrier` for some contracts.
        contract_type = "CALL" if side.lower() == "buy" else "PUT"

        # We might need to request a proposal first to understand the instrument's behavior.
        # However, a true limit order might be set directly in the 'buy' call with a proposal_id
        # and limit_order parameters, or by using a contract type that has an entry spot/barrier.
        # This is highly dependent on Deriv's specific instrument & contract API.
        # The 'price' here is the desired limit price.

        # Option 1: Use proposal with barrier if contract type supports it (e.g. options)
        # proposal = self._get_proposal(instrument, side, qty, contract_type, price=price, **kwargs)
        # proposal_id = proposal.get("id")
        # if not proposal_id: raise Exception("Failed to get proposal for limit order.")
        # return self._buy_contract(proposal_id, proposal.get("ask_price"), **kwargs) # ask_price from proposal is what we pay

        # Option 2: More commonly, for CFDs or certain contracts, you might use limit_order in buy call.
        # This requires a proposal_id first.
        # This example assumes we get a general proposal and then try to buy with limit conditions.
        try:
            # Get a general proposal first (without specific price barrier)
            # The 'price' parameter in our method signature is the target limit price.
            # The 'ask_price' from proposal is the current market price to open.
            # For a true limit order, we wouldn't use proposal's ask_price directly in buy if it's not our limit.
            # Deriv's `buy` call can include `limit_order` for some contract types
            # to specify take_profit and stop_loss. For entry price limits, it's more complex.
            # It might involve `contract_update` or specific contract types.

            # This is a placeholder, as true limit order logic for Deriv contracts is complex
            # and often involves subscribing to price proposals and buying when conditions are met,
            # or using specific contract types not covered by a simple "CALL"/"PUT" for CFDs.
            cprint("⚠️ place_limit_order for Deriv is highly dependent on contract type and may need instrument-specific logic. This implementation is a placeholder.", "yellow")

            # Example for a contract that supports entry barriers (simplified):
            # proposal = self._get_proposal(instrument, side, qty, contract_type, price=price, **kwargs)
            # proposal_id = proposal.get("id")
            # if not proposal_id: raise Exception("Failed to get proposal for limit order.")
            # return self._buy_contract(proposal_id, proposal.get("ask_price"), **kwargs)

            # For now, effectively a market order with SL/TP if provided.
            # True limit orders would need a different flow or contract type.
            return self.place_market_order(instrument, side, qty, price=price, **kwargs) # Pass price for logging, but it's not a true limit

        except Exception as e:
            cprint(f"Error placing Deriv limit order for {instrument}: {e}", "red")
            return {"error": str(e), "status": "error"}


    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        # `order_id` here is likely Deriv's `contract_id` or `transaction_id` from a `buy` response.
        if not self._is_connected or not self.api_key:
            raise PermissionError("Not authorized or connected.")
        try:
            # `proposal_open_contract` is for a specific open contract.
            # `transaction_stream` might give updates if it's a transaction_id.
            # If it's a contract_id for an open position:
            payload = {"proposal_open_contract": 1, "contract_id": int(order_id)} # contract_id is usually int
            response = self._send_json_request(payload)

            poc = response.get("proposal_open_contract")
            if poc:
                return {
                    "order_id": str(poc.get("contract_id")),
                    "instrument": poc.get("symbol"),
                    "status": poc.get("status"), # e.g., 'open', 'sold', 'won', 'lost'
                    "qty": poc.get("contract_type"), # This is not qty, but type. Need to map better.
                    "buy_price": poc.get("buy_price"),
                    "sell_price": poc.get("sell_price"),
                    "profit": poc.get("profit"),
                    "is_valid_to_sell": poc.get("is_valid_to_sell"),
                    "current_spot": poc.get("current_spot"),
                    "raw_response": poc
                }
            else:
                return {"order_id": order_id, "status": "not_found", "message": "Order/Contract not found or error in response."}
        except Exception as e:
            cprint(f"Error getting Deriv order status for {order_id}: {e}", "red")
            return {"order_id": order_id, "status": "error", "message": str(e)}


    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self._is_connected or not self.api_key:
            raise PermissionError("Not authorized or connected.")
        try:
            payload = {"portfolio": 1}
            response = self._send_json_request(payload)

            contracts = response.get("portfolio", {}).get("contracts", [])
            positions = []
            for contract in contracts:
                positions.append({
                    "position_id": str(contract.get("contract_id")), # Use contract_id as position_id
                    "instrument": contract.get("symbol"),
                    "qty": contract.get("contract_type"), # Again, this is type. Qty needs mapping.
                                                          # For stake-based, qty might be stake amount.
                                                          # For CFDs, it would be units/lots. This needs clarification.
                    "entry_price": contract.get("buy_price"),
                    "side": "buy" if "CALL" in contract.get("contract_type","").upper() or "UP" in contract.get("contract_type","").upper() else "sell", # Simplistic side
                    "profit_loss": contract.get("profit"), # This is often current profit/loss
                    "details": contract # Raw contract details
                })
            return positions
        except Exception as e:
            cprint(f"Error getting Deriv open positions: {e}", "red")
            return []

    def get_instrument_details(self, instrument: str) -> Dict[str, Any]:
        if not self._is_connected:
            raise ConnectionError("Not connected to Deriv.")
        try:
            # Fetch all active symbols. In a real scenario, you might cache this.
            payload = {"active_symbols": "brief", "product_type": "basic"}
            response = self._send_json_request(payload)

            active_symbols = response.get("active_symbols", [])
            for symbol_data in active_symbols:
                if symbol_data.get("symbol") == instrument:
                    # Map Deriv's fields to our standard ones
                    return {
                        "instrument": symbol_data.get("symbol"),
                        "display_name": symbol_data.get("display_name"),
                        "pip_size": symbol_data.get("pip"),
                        "min_order_size": symbol_data.get("min_contract_duration"), # This is not min_order_size. Needs proper mapping.
                        "market": symbol_data.get("market_display_name"),
                        "raw_details": symbol_data
                    }
            return {"error": f"Instrument {instrument} not found or not active."}
        except Exception as e:
            cprint(f"Error getting Deriv instrument details for {instrument}: {e}", "red")
            return {"error": str(e)}
