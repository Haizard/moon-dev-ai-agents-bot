"""
🌙 Moon Dev's OHLCV Data Collector
Collects Open-High-Low-Close-Volume data for specified tokens using BrokerFactory.
Built with love by Moon Dev 🚀
"""

import pandas as pd
import os
from termcolor import cprint
import time # Keep time for potential delays between broker calls if needed

# Import necessary configurations and the broker factory
from src.config import (
    MONITORED_TOKENS,    # Assumed to be list of broker-agnostic symbols like "BTC/USD"
    ACTIVE_BROKERS,
    BROKER_CONFIGS,
    OHLCV_TIMEFRAME,
    OHLCV_LIMIT,
    SAVE_OHLCV_DATA      # To determine if data should be saved in 'data/' or 'temp_data/'
)
from src.brokers.broker_factory import broker_factory

def collect_all_tokens() -> Dict[str, pd.DataFrame]:
    """
    Collects OHLCV data for all monitored tokens from active brokers.
    Data is saved to CSV, namespaced by broker.
    The returned dictionary uses a "first broker wins" strategy for each token.
    """
    all_market_data: Dict[str, pd.DataFrame] = {}
    processed_tokens_for_dict: set[str] = set() # Tracks tokens added to all_market_data

    cprint("\n🔍 Moon Dev's OHLCV Collector starting market data collection via BrokerFactory...", "white", "on_blue")

    if not ACTIVE_BROKERS:
        cprint("⚠️ No active brokers configured in src/config.py (ACTIVE_BROKERS). No data will be collected.", "yellow")
        return all_market_data

    for broker_name in ACTIVE_BROKERS:
        cprint(f"\n Attempting to use broker: {broker_name}", "cyan")
        
        broker_specific_config = BROKER_CONFIGS.get(broker_name, {})
        # Note: api_key/secret are often part of broker_specific_config itself if loaded from env there.
        # get_broker can take them explicitly too. Let's assume they are within broker_specific_config for now.
        
        broker = broker_factory.get_broker(broker_name, **broker_specific_config)

        if not broker:
            cprint(f"❌ Failed to initialize broker: {broker_name}. Skipping.", "red")
            continue

        try:
            cprint(f"Connecting to {broker_name}...", "magenta")
            broker.connect() # connect() should handle its own errors and raise ConnectionError
            
            # Simple ping test after connect, though connect should ensure readiness
            if not broker.ping():
                 cprint(f"⚠️ {broker_name} connected but failed ping. May not be fully operational. Skipping.", "yellow")
                 broker.disconnect()
                 continue
            cprint(f"✅ Connected to {broker_name} successfully.", "green")

            for token_symbol in MONITORED_TOKENS:
                # TODO: Implement robust symbol mapping if MONITORED_TOKENS are not directly usable by all brokers.
                # For now, assume token_symbol is in the format expected by the broker (e.g., "BTC/USD").
                # Some brokers might require "BTCUSD". This mapping could be part of BROKER_CONFIGS or a separate utility.
                instrument_for_broker = token_symbol # Placeholder for potential mapping

                cprint(f"  Fetching data for {instrument_for_broker} from {broker_name}...", "blue")
                try:
                    df_ohlcv = broker.get_ohlcv(
                        instrument=instrument_for_broker,
                        timeframe=OHLCV_TIMEFRAME,
                        limit=OHLCV_LIMIT
                    )

                    if df_ohlcv is not None and not df_ohlcv.empty:
                        cprint(f"    📊 Received {len(df_ohlcv)} candles for {instrument_for_broker} from {broker_name}.", "green")

                        safe_token_name = instrument_for_broker.replace('/', '_').replace('\\', '_') # Make fs-safe
                        save_base_dir = "data" if SAVE_OHLCV_DATA else "temp_data"
                        # Ensure 'data' and 'temp_data' exist at the root of the project or adjust path as needed.
                        # Assuming current working directory allows this relative path.
                        save_dir_path = os.path.join(os.getcwd(), save_base_dir)
                        os.makedirs(save_dir_path, exist_ok=True)

                        filepath = os.path.join(save_dir_path, f"{broker_name}_{safe_token_name}_{OHLCV_TIMEFRAME}_latest.csv")

                        df_ohlcv.to_csv(filepath, index=False)
                        cprint(f"    💾 Data for {instrument_for_broker} from {broker_name} saved to {filepath}", "magenta")

                        if instrument_for_broker not in processed_tokens_for_dict:
                            all_market_data[instrument_for_broker] = df_ohlcv
                            processed_tokens_for_dict.add(instrument_for_broker)
                            cprint(f"    ➕ Added {instrument_for_broker} data from {broker_name} to results dictionary.", "blue")
                        else:
                            cprint(f"    ℹ️ Data for {instrument_for_broker} already collected from a prior broker. Skipping for results dictionary.", "grey")
                    else:
                        cprint(f"    ⚠️ No data returned for {instrument_for_broker} from {broker_name}.", "yellow")

                except Exception as e_ohlcv:
                    cprint(f"    ❌ Error fetching OHLCV for {instrument_for_broker} from {broker_name}: {e_ohlcv}", "red")
            
        except ConnectionError as e_connect:
            cprint(f"❌ Connection error with {broker_name}: {e_connect}", "red")
        except Exception as e_broker_general:
            cprint(f"❌ General error with broker {broker_name}: {e_broker_general}", "red")
        finally:
            if broker and broker._is_connected: # Check internal state if possible, or rely on ping
                cprint(f"  Disconnecting from {broker_name}...", "magenta")
                broker.disconnect()
            elif broker: # Ensure disconnect is called even if connect partially failed but broker object exists
                cprint(f"  Ensuring {broker_name} is disconnected (if partially connected)...", "magenta")
                broker.disconnect()


    if not all_market_data:
        cprint("\n⚠️ No market data was successfully collected from any active broker for any monitored token.", "yellow")
    else:
        cprint(f"\n✨ Moon Dev's OHLCV Collector completed. Collected data for {len(all_market_data)} token(s) in the final dictionary.", "white", "on_green")
    
    return all_market_data

if __name__ == "__main__":
    # Ensure necessary directories exist if running standalone for testing
    if not os.path.exists("temp_data"):
        os.makedirs("temp_data")
    if SAVE_OHLCV_DATA and not os.path.exists("data"):
        os.makedirs("data")

    cprint("🚀 Running OHLCV Collector Standalone Test...", "yellow")
    collected_data = collect_all_tokens()
    for token, df in collected_data.items():
        cprint(f"\n--- Data for {token} ---", "cyan")
        print(df.head())
    cprint("\n✅ Standalone test finished.", "green")