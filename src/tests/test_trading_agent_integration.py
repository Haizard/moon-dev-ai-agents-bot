import unittest
from unittest.mock import patch, MagicMock, call, ANY
import pandas as pd
import json

# Adjust Python path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Modules to test
from src.agents.trading_agent import TradingAgent
from src.models.base_model import ModelResponse
from src import config # To override config values for tests
from src.trading.execution_service import trade_executor # To mock its active_broker

# Helper to create a mock AI model
def create_mock_ai_model():
    mock_model = MagicMock()
    mock_model.generate_response = MagicMock()
    return mock_model

# Helper to create a mock BaseBroker
def create_mock_broker():
    mock_broker = MagicMock(spec=['get_ohlcv', 'place_market_order', 'get_open_positions', 'get_instrument_details', 'connect', 'disconnect', 'ping', '_is_connected'])
    mock_broker._is_connected = True # Assume connected by default after factory returns it
    mock_broker.ping.return_value = True
    mock_broker.connect.return_value = None # connect usually doesn't return anything
    mock_broker.disconnect.return_value = None
    return mock_broker

# Helper to create sample OHLCV data
def create_sample_ohlcv_df(price=50000.0):
    return pd.DataFrame({
        'timestamp': [pd.Timestamp.now().timestamp() * 1000],
        'open': [price * 0.99],
        'high': [price * 1.01],
        'low': [price * 0.98],
        'close': [price],
        'volume': [100]
    })

class TestTradingAgentIntegration(unittest.TestCase):

    def setUp(self):
        # Store original config values
        self.original_monitored_tokens = config.MONITORED_TOKENS
        self.original_active_trading_broker = config.ACTIVE_TRADING_BROKER_NAME
        self.original_usd_size = config.usd_size
        self.original_max_pos_percentage = config.MAX_POSITION_PERCENTAGE
        self.original_cash_percentage = config.CASH_PERCENTAGE
        self.original_max_usd_order_size = config.max_usd_order_size


        # Patch model_factory.get_core_model to return our mock AI model
        self.mock_ai_model_instance = create_mock_ai_model()
        self.patch_get_core_model = patch('src.models.model_factory.model_factory.get_core_model', return_value=self.mock_ai_model_instance)
        self.mock_get_core_model = self.patch_get_core_model.start()

        # Patch ohlcv_collector.collect_all_tokens
        self.patch_collect_all_tokens = patch('src.agents.trading_agent.collect_all_tokens') # Patched where it's imported
        self.mock_collect_all_tokens = self.patch_collect_all_tokens.start()

        # Mock the active_broker within the trade_executor singleton
        self.mock_broker_instance = create_mock_broker()
        self.patch_trade_executor_broker = patch.object(trade_executor, 'active_broker', self.mock_broker_instance)
        self.mock_active_broker_attr = self.patch_trade_executor_broker.start()

        # Instantiate TradingAgent *after* core mocks are set up
        self.agent = TradingAgent()
        self.agent.recommendations_df = pd.DataFrame(columns=['token', 'action', 'confidence', 'reasoning'])


    def tearDown(self):
        self.patch_get_core_model.stop()
        self.patch_collect_all_tokens.stop()
        self.patch_trade_executor_broker.stop()

        # Restore original config values
        config.MONITORED_TOKENS = self.original_monitored_tokens
        config.ACTIVE_TRADING_BROKER_NAME = self.original_active_trading_broker
        config.usd_size = self.original_usd_size
        config.MAX_POSITION_PERCENTAGE = self.original_max_pos_percentage
        config.CASH_PERCENTAGE = self.original_cash_percentage
        config.max_usd_order_size = self.original_max_usd_order_size


    def test_scenario_simple_buy_decision_and_execution(self):
        # --- Setup ---
        config.MONITORED_TOKENS = ["BTC/USD"]
        config.usd_size = 10000
        config.max_usd_order_size = 6000

        self.mock_collect_all_tokens.return_value = {
            "BTC/USD": create_sample_ohlcv_df(price=50000.0)
        }

        analysis_response_content = "BUY\nReasoning for BTC/USD buy.\nConfidence: 80%"
        self.mock_ai_model_instance.generate_response.side_effect = [
            ModelResponse(content=analysis_response_content, raw_response=None, model_name="mock_ai", usage=None),
            ModelResponse(content=json.dumps({"BTC/USD": 5000, config.USDC_ADDRESS: 5000}), raw_response=None, model_name="mock_ai", usage=None)
        ]

        self.mock_broker_instance.get_open_positions.return_value = []
        self.mock_broker_instance.get_ohlcv.return_value = create_sample_ohlcv_df(price=50000.0)
        self.mock_broker_instance.place_market_order.return_value = {"order_id": "order123", "status": "filled"}

        # --- Action ---
        self.agent.run_trading_cycle()

        # --- Assertions ---
        self.mock_ai_model_instance.generate_response.assert_any_call(
            system_prompt=ANY,
            user_content=ANY,
            temperature=config.AI_TEMPERATURE,
            max_tokens=config.AI_MAX_TOKENS
        )
        self.assertEqual(self.mock_ai_model_instance.generate_response.call_count, 2)

        self.assertFalse(self.agent.recommendations_df.empty)
        btc_reco = self.agent.recommendations_df[self.agent.recommendations_df['token'] == "BTC/USD"].iloc[0]
        self.assertEqual(btc_reco['action'], "BUY")
        self.assertEqual(btc_reco['confidence'], 80)

        expected_quantity = 5000 / 50000.0

        # Check the actual call to place_market_order
        called_args, called_kwargs = self.mock_broker_instance.place_market_order.call_args
        self.assertEqual(called_args[0], "BTC/USD")
        self.assertEqual(called_args[1], "buy")
        self.assertAlmostEqual(called_args[2], expected_quantity, places=6)

    def test_scenario_sell_decision_and_execution(self):
        # --- Setup ---
        config.MONITORED_TOKENS = ["ETH/USD"]
        test_instrument = "ETH/USD"
        initial_position_qty = 2.0
        entry_price = 2000.0

        self.mock_collect_all_tokens.return_value = {
            test_instrument: create_sample_ohlcv_df(price=2100.0)
        }

        analysis_response_content = f"SELL\nReasoning for {test_instrument} sell.\nConfidence: 70%"
        allocation_response_content = json.dumps({config.USDC_ADDRESS: config.usd_size})

        self.mock_ai_model_instance.generate_response.side_effect = [
            ModelResponse(content=analysis_response_content, raw_response=None, model_name="mock_ai", usage=None),
            ModelResponse(content=allocation_response_content, raw_response=None, model_name="mock_ai", usage=None)
        ]

        self.mock_broker_instance.get_open_positions.return_value = [
            {'instrument': test_instrument, 'qty': initial_position_qty, 'entry_price': entry_price, 'side': 'buy', 'position_id': 'eth_pos_1'}
        ]
        self.mock_broker_instance.get_ohlcv.return_value = create_sample_ohlcv_df(price=2100.0) # For chunk_kill price check
        self.mock_broker_instance.place_market_order.return_value = {"order_id": "order456", "status": "filled"}

        # Store and temporarily set max_usd_order_size for this test to ensure one sell chunk
        original_max_order_size = config.max_usd_order_size
        config.max_usd_order_size = 5000 # Current value of position is 2.0 * 2100 = 4200

        # --- Action ---
        self.agent.run_trading_cycle()

        # --- Assertions ---
        self.assertEqual(self.mock_ai_model_instance.generate_response.call_count, 2)

        self.assertFalse(self.agent.recommendations_df.empty)
        eth_reco = self.agent.recommendations_df[self.agent.recommendations_df['token'] == test_instrument].iloc[0]
        self.assertEqual(eth_reco['action'], "SELL")

        # Verify place_market_order was called to sell the initial_position_qty
        # The refactored n.chunk_kill for CEX aims to sell the asset quantity.
        called_args, called_kwargs = self.mock_broker_instance.place_market_order.call_args
        self.assertEqual(called_args[0], test_instrument)
        self.assertEqual(called_args[1], "sell")
        self.assertAlmostEqual(called_args[2], initial_position_qty, places=6)

        # Restore original config value
        config.max_usd_order_size = original_max_order_size

    def test_scenario_nothing_decision_for_existing_position(self):
        # --- Setup ---
        config.MONITORED_TOKENS = ["LINK/USD"]
        test_instrument = "LINK/USD"
        initial_position_qty = 100.0
        entry_price = 15.0

        self.mock_collect_all_tokens.return_value = {
            test_instrument: create_sample_ohlcv_df(price=16.0)
        }

        # AI Analysis for LINK/USD -> NOTHING
        analysis_response_content = f"NOTHING\nReasoning for {test_instrument} nothing.\nConfidence: 50%"
        # Allocation can be anything, as it shouldn't lead to new buys.
        # Typically, if all positions are to be maintained or exited, it would allocate to USDC.
        allocation_response_content = json.dumps({config.USDC_ADDRESS: config.usd_size})

        self.mock_ai_model_instance.generate_response.side_effect = [
            ModelResponse(content=analysis_response_content, raw_response=None, model_name="mock_ai", usage=None),
            ModelResponse(content=allocation_response_content, raw_response=None, model_name="mock_ai", usage=None)
        ]

        self.mock_broker_instance.get_open_positions.return_value = [
            {'instrument': test_instrument, 'qty': initial_position_qty, 'entry_price': entry_price, 'side': 'buy', 'position_id': 'link_pos_1'}
        ]
        self.mock_broker_instance.get_ohlcv.return_value = create_sample_ohlcv_df(price=16.0)
        self.mock_broker_instance.place_market_order.return_value = {"order_id": "order789", "status": "filled"}

        original_max_order_size = config.max_usd_order_size
        config.max_usd_order_size = (initial_position_qty * 16.0) + 100 # Ensure it can be sold in one chunk

        # --- Action ---
        self.agent.run_trading_cycle()

        # --- Assertions ---
        self.assertEqual(self.mock_ai_model_instance.generate_response.call_count, 2)

        self.assertFalse(self.agent.recommendations_df.empty)
        link_reco = self.agent.recommendations_df[self.agent.recommendations_df['token'] == test_instrument].iloc[0]
        self.assertEqual(link_reco['action'], "NOTHING")

        # Verify place_market_order was called to SELL the position,
        # as "NOTHING" on an existing position triggers an exit in current TradingAgent.handle_exits logic
        called_args, called_kwargs = self.mock_broker_instance.place_market_order.call_args
        self.assertEqual(called_args[0], test_instrument)
        self.assertEqual(called_args[1], "sell") # Should be a sell to close
        self.assertAlmostEqual(called_args[2], initial_position_qty, places=6)

        config.max_usd_order_size = original_max_order_size # Restore

    def test_scenario_allocation_constraints_and_chunking(self):
        # --- Setup ---
        # Test if ai_entry (called by execute_allocations) correctly chunks orders
        # if the allocated USD amount exceeds max_usd_order_size.
        config.MONITORED_TOKENS = ["ADA/USD"]
        test_instrument = "ADA/USD"
        config.usd_size = 20000 # Total portfolio value
        config.max_usd_order_size = 1000 # Max USD per chunk order

        current_ada_price = 0.50
        self.mock_collect_all_tokens.return_value = {
            test_instrument: create_sample_ohlcv_df(price=current_ada_price)
        }

        # AI Analysis: BUY ADA
        analysis_response_content = f"BUY\nReasoning for {test_instrument} buy.\nConfidence: 90%"
        # AI Allocation: Allocate $2500 to ADA.
        # This is 2.5x max_usd_order_size, so expecting 3 chunks.
        # (2500 / 1000 = 2.5 -> 3 chunks: 1000, 1000, 500 USD worth of ADA)
        allocated_usd_amount = 2500.0
        allocation_response_content = json.dumps({
            test_instrument: allocated_usd_amount,
            config.USDC_ADDRESS: config.usd_size - allocated_usd_amount
        })

        self.mock_ai_model_instance.generate_response.side_effect = [
            ModelResponse(content=analysis_response_content, raw_response=None, model_name="mock_ai", usage=None),
            ModelResponse(content=allocation_response_content, raw_response=None, model_name="mock_ai", usage=None)
        ]

        self.mock_broker_instance.get_open_positions.return_value = [] # No existing positions
        self.mock_broker_instance.get_ohlcv.return_value = create_sample_ohlcv_df(price=current_ada_price)
        self.mock_broker_instance.place_market_order.return_value = {"order_id": "ada_order_chunk", "status": "filled"}

        # --- Action ---
        self.agent.run_trading_cycle()

        # --- Assertions ---
        # Check if place_market_order was called multiple times (chunking)
        # Expected total quantity: $2500 / $0.50 = 5000 ADA
        # Expected chunk quantity (asset): $1000 / $0.50 = 2000 ADA
        # So, 2 chunks of 2000 ADA, and 1 chunk of 1000 ADA.

        self.assertEqual(self.mock_broker_instance.place_market_order.call_count, 3)

        total_quantity_ordered = 0
        expected_quantities_per_chunk = [
            1000 / current_ada_price, # 2000 ADA
            1000 / current_ada_price, # 2000 ADA
            500  / current_ada_price  # 1000 ADA
        ]

        for i, call_args_item in enumerate(self.mock_broker_instance.place_market_order.call_args_list):
            args, _ = call_args_item
            self.assertEqual(args[0], test_instrument)
            self.assertEqual(args[1], "buy")
            self.assertAlmostEqual(args[2], expected_quantities_per_chunk[i], places=6)
            total_quantity_ordered += args[2]

        self.assertAlmostEqual(total_quantity_ordered, allocated_usd_amount / current_ada_price, places=6)

    def test_scenario_multiple_tokens_mixed_decisions(self):
        # --- Setup ---
        config.MONITORED_TOKENS = ["BTC/USD", "ETH/USD", "LTC/USD"]
        config.usd_size = 30000
        config.max_usd_order_size = 10000 # Allow larger single orders for simplicity here

        self.mock_collect_all_tokens.return_value = {
            "BTC/USD": create_sample_ohlcv_df(price=50000.0),
            "ETH/USD": create_sample_ohlcv_df(price=2000.0),
            "LTC/USD": create_sample_ohlcv_df(price=150.0)
        }

        # AI Responses:
        # 1. BTC/USD Analysis -> BUY
        # 2. ETH/USD Analysis -> SELL
        # 3. LTC/USD Analysis -> NOTHING
        # 4. Allocation: Buy BTC, keep some USDC (ETH is sold, LTC is ignored for new buys)
        btc_buy_analysis = "BUY\nReasoning for BTC buy.\nConfidence: 80%"
        eth_sell_analysis = "SELL\nReasoning for ETH sell.\nConfidence: 75%"
        ltc_nothing_analysis = "NOTHING\nReasoning for LTC nothing.\nConfidence: 60%"

        allocation_details = {
            "BTC/USD": 5000, # Buy $5000 of BTC
            config.USDC_ADDRESS: 25000 # Remaining cash
        }
        allocation_response = json.dumps(allocation_details)

        self.mock_ai_model_instance.generate_response.side_effect = [
            ModelResponse(content=btc_buy_analysis, raw_response=None, model_name="mock_ai"), # BTC Analysis
            ModelResponse(content=eth_sell_analysis, raw_response=None, model_name="mock_ai"),# ETH Analysis
            ModelResponse(content=ltc_nothing_analysis, raw_response=None, model_name="mock_ai"),# LTC Analysis
            ModelResponse(content=allocation_response, raw_response=None, model_name="mock_ai")    # Allocation
        ]

        # Mock existing positions: holding ETH, no BTC, no LTC
        self.mock_broker_instance.get_open_positions.side_effect = lambda instrument=None, **kwargs: {
            "ETH/USD": [{'instrument': "ETH/USD", 'qty': 10.0, 'entry_price': 1900.0, 'side': 'buy'}],
            "BTC/USD": [],
            "LTC/USD": []
        }.get(instrument, []) # Return specific list if instrument is specified, else empty for general calls

        # Mock OHLCV for price lookups in ai_entry/chunk_kill
        self.mock_broker_instance.get_ohlcv.side_effect = lambda instrument, **kwargs: {
            "BTC/USD": create_sample_ohlcv_df(price=50000.0),
            "ETH/USD": create_sample_ohlcv_df(price=2000.0), # Current price for ETH
            "LTC/USD": create_sample_ohlcv_df(price=150.0)
        }.get(instrument, pd.DataFrame())

        self.mock_broker_instance.place_market_order.return_value = {"order_id": "mock_order_id", "status": "filled"}

        # --- Action ---
        self.agent.run_trading_cycle()

        # --- Assertions ---
        # AI calls: 3 analyses + 1 allocation = 4
        self.assertEqual(self.mock_ai_model_instance.generate_response.call_count, 4)

        # Recommendations DataFrame
        self.assertEqual(len(self.agent.recommendations_df), 3)
        self.assertEqual(self.agent.recommendations_df.loc[self.agent.recommendations_df['token'] == 'BTC/USD', 'action'].iloc[0], "BUY")
        self.assertEqual(self.agent.recommendations_df.loc[self.agent.recommendations_df['token'] == 'ETH/USD', 'action'].iloc[0], "SELL")
        self.assertEqual(self.agent.recommendations_df.loc[self.agent.recommendations_df['token'] == 'LTC/USD', 'action'].iloc[0], "NOTHING")

        # Trading actions (place_market_order calls)
        # Expected: 1 buy for BTC, 1 sell for ETH. No action for LTC.
        self.assertEqual(self.mock_broker_instance.place_market_order.call_count, 2)

        # Verify BTC Buy
        # Qty = $5000 / $50000/BTC = 0.1 BTC
        expected_btc_qty = 5000 / 50000.0

        # Verify ETH Sell
        # Qty = 10.0 ETH (full position)
        expected_eth_qty = 10.0

        calls = self.mock_broker_instance.place_market_order.call_args_list

        btc_call_found = False
        eth_call_found = False

        for call_item in calls:
            args, _ = call_item
            instrument, side, quantity = args[0], args[1], args[2]
            if instrument == "BTC/USD" and side == "buy":
                self.assertAlmostEqual(quantity, expected_btc_qty, places=6)
                btc_call_found = True
            elif instrument == "ETH/USD" and side == "sell":
                self.assertAlmostEqual(quantity, expected_eth_qty, places=6)
                eth_call_found = True

        self.assertTrue(btc_call_found, "BTC buy order not found or incorrect.")
        self.assertTrue(eth_call_found, "ETH sell order not found or incorrect.")


if __name__ == '__main__':
    unittest.main()
