"""
🌙 Moon Dev's Configuration File
Built with love by Moon Dev 🚀
"""

# 💰 Trading Configuration
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Never trade or close
SOL_ADDRESS = "So11111111111111111111111111111111111111111"   # Never trade or close

# Create a list of addresses to exclude from trading/closing
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS] # These are Solana specific, review if needed for CEX context

# Token List for Monitoring and Trading 📋
# IMPORTANT: These should be generic, human-readable symbols (e.g., "BTC/USD", "EUR/USD")
# or specific symbols recognized by your chosen ACTIVE_BROKER(S) (e.g., "R_100" for Deriv Volatility 100 Index).
# The old list of Solana addresses has been replaced. Ensure these symbols are supported by your active broker(s).
MONITORED_TOKENS = [
    "BTC/USD",
    "ETH/USD",
    "EUR/USD",        # Example Forex pair for MT5 brokers
    "R_100",          # Example Deriv Volatility Index (if Deriv is an active broker)
    # "XAU/USD",      # Example Gold (typically available on MT5 brokers)
    # Add other symbols relevant to your chosen broker(s) and trading interests.
]

# Moon Dev's Token Trading List 🚀
# This list is used by some agents to decide which tokens from MONITORED_TOKENS they might trade.
tokens_to_trade = MONITORED_TOKENS  # Using the same list for trading for now.

# Token and wallet settings (These seem Solana specific, review if keeping)
symbol = '9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump'
address = '4wgfCBf2WwLSRKLef9iW7JXZ2AfkxUxGM4XcKpHm3Sin' # YOUR WALLET ADDRESS HERE

# Position sizing 🎯
usd_size = 25  # Size of position to hold
max_usd_order_size = 3  # Max order size
tx_sleep = 30  # Sleep between transactions
slippage = 199  # Slippage settings

# Risk Management Settings 🛡️
CASH_PERCENTAGE = 20  # Minimum % to keep in USDC as safety buffer (0-100)
MAX_POSITION_PERCENTAGE = 30  # Maximum % allocation per position (0-100)
STOPLOSS_PRICE = 1 # NOT USED YET 1/5/25    
BREAKOUT_PRICE = .0001 # NOT USED YET 1/5/25
SLEEP_AFTER_CLOSE = 600  # Prevent overtrading

MAX_LOSS_GAIN_CHECK_HOURS = 12  # How far back to check for max loss/gain limits (in hours)
SLEEP_BETWEEN_RUNS_MINUTES = 15  # How long to sleep between agent runs 🕒


# Max Loss/Gain Settings FOR RISK AGENT 1/5/25
USE_PERCENTAGE = False  # If True, use percentage-based limits. If False, use USD-based limits

# USD-based limits (used if USE_PERCENTAGE is False)
MAX_LOSS_USD = 25  # Maximum loss in USD before stopping trading
MAX_GAIN_USD = 25 # Maximum gain in USD before stopping trading

# USD MINIMUM BALANCE RISK CONTROL
MINIMUM_BALANCE_USD = 50  # If balance falls below this, risk agent will consider closing all positions
USE_AI_CONFIRMATION = True  # If True, consult AI before closing positions. If False, close immediately on breach

# Percentage-based limits (used if USE_PERCENTAGE is True)
MAX_LOSS_PERCENT = 5  # Maximum loss as percentage (e.g., 20 = 20% loss)
MAX_GAIN_PERCENT = 5  # Maximum gain as percentage (e.g., 50 = 50% gain)

# Transaction settings ⚡
slippage = 199  # 500 = 5% and 50 = .5% slippage
PRIORITY_FEE = 100000  # ~0.02 USD at current SOL prices
orders_per_open = 3  # Multiple orders for better fill rates

# Market maker settings 📊
buy_under = .0946
sell_over = 1

# Data collection settings 📈
DAYSBACK_4_DATA = 3
DATA_TIMEFRAME = '1H'  # 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
SAVE_OHLCV_DATA = False  # 🌙 Set to True to save data permanently, False will only use temp data during run

# AI Model Settings 🤖
AI_MODEL = "claude-3-haiku-20240307"  # Model Options:
                                     # - claude-3-haiku-20240307 (Fast, efficient Claude model)
                                     # - claude-3-sonnet-20240229 (Balanced Claude model)
                                     # - claude-3-opus-20240229 (Most powerful Claude model)
AI_MAX_TOKENS = 1024  # Max tokens for response
AI_TEMPERATURE = 0.7  # Creativity vs precision (0-1)

# Core AI Model Configuration - Used by ModelFactory to select the primary model
CORE_AI_MODEL_TYPE = "groq"  # Options: "claude", "groq", "openai", "gemini", "deepseek"
CORE_AI_MODEL_NAME = "llama3-8b-8192"  # Specific model name, e.g., "claude-3-haiku-20240307", "mixtral-8x7b-32768", "gpt-4o", "gemini-pro". Leave empty to use default for the type.

# Trading Strategy Agent Settings - MAY NOT BE USED YET 1/5/25
ENABLE_STRATEGIES = True  # Set this to True to use strategies
STRATEGY_MIN_CONFIDENCE = 0.7  # Minimum confidence to act on strategy signals

# Sleep time between main agent runs
SLEEP_BETWEEN_RUNS_MINUTES = 15  # How long to sleep between agent runs 🕒


# Broker Configurations
# =============================================================================
# IMPORTANT SECURITY NOTE:
# Never hardcode API keys, secrets, or passwords directly in this file for production.
# Use environment variables (e.g., os.getenv("MY_API_KEY", "default_value_if_not_set"))
# or a secure secrets management system. The placeholders below demonstrate loading
# from environment variables, assuming you have a .env file or have set them in your system.

import os # For loading environment variables

# --- Active Brokers for Data Collection (used by ohlcv_collector.py) ---
# List of broker names (these must match keys in BROKER_CONFIGS) that the
# OHLCV collector should attempt to use for fetching market data.
# The collector will iterate through these and use data from the first successful source
# for each token in the main returned dictionary (though it saves data for all).
# Example: ACTIVE_BROKERS = ["deriv", "icmarkets"]
ACTIVE_BROKERS: List[str] = ["deriv"]

# --- Configuration for Each Broker ---
# Each key is a unique broker_name (string) and the value is a dictionary
# containing all necessary parameters for that broker's client to connect.
BROKER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "deriv": {
        # Register an application on the Deriv API website to get your app_id.
        # For basic testing without registration, app_id 1089 (Deriv's sample) can often be used.
        "app_id": int(os.getenv("DERIV_APP_ID", "1089")),

        # Create an API token from your Deriv account: Security & Limits -> API Token.
        # Required scopes typically include "read" and "trade".
        "api_key": os.getenv("DERIV_API_TOKEN", "YOUR_DERIV_API_TOKEN_PLACEHOLDER"),

        # Optional: Override the default Deriv API endpoint if needed.
        # "endpoint": "frontend.binaryws.com", (this is usually the default in the broker class)
        # Optional: Specify a particular Deriv account ID if your token has access to multiple.
        # "account_id": os.getenv("DERIV_ACCOUNT_ID", None)
    },
    "icmarkets": {
        # These are your MetaTrader 5 account credentials.
        # IMPORTANT: The MetaTrader 5 terminal for this account MUST be running on a machine
        # accessible by this script for the connection to work.
        "login_id": int(os.getenv("ICMARKETS_LOGIN_ID", "0")), # Your MT5 account number
        "password": os.getenv("ICMARKETS_PASSWORD", "YOUR_ICMARKETS_MT5_PASSWORD_PLACEHOLDER"),
        "server": os.getenv("ICMARKETS_SERVER", "ICMarketsSC-Demo"), # Check server name in your MT5 terminal login window

        # Optional: Full path to the MT5 terminal executable (terminal64.exe or terminal.exe on Windows).
        # Required if MT5 is not in the default install location or if you have multiple MT5 instances.
        "mt5_path": os.getenv("ICMARKETS_MT5_PATH", ""),
        # Example: "C:\\Program Files\\MetaTrader 5 IC Markets (SC)\\terminal64.exe"
    },
    "xm": {
        "login_id": int(os.getenv("XM_LOGIN_ID", "0")),
        "password": os.getenv("XM_PASSWORD", "YOUR_XM_MT5_PASSWORD_PLACEHOLDER"),
        "server": os.getenv("XM_SERVER", "XMGlobal-MT5"), # Example, verify your specific server name from MT5
        "mt5_path": os.getenv("XM_MT5_PATH", ""),
        # Reminder: MT5 terminal for XM must be running.
    },
    "exness": {
        "login_id": int(os.getenv("EXNESS_LOGIN_ID", "0")),
        "password": os.getenv("EXNESS_PASSWORD", "YOUR_EXNESS_MT5_PASSWORD_PLACEHOLDER"),
        "server": os.getenv("EXNESS_SERVER", "Exness-MT5Trial"), # Example, verify your specific server name from MT5
        "mt5_path": os.getenv("EXNESS_MT5_PATH", ""),
        # Reminder: MT5 terminal for Exness must be running.
    }
    # Add configurations for other brokers here as they are implemented.
    # Ensure the key (e.g., "another_broker") matches what you might put in ACTIVE_BROKERS
    # or ACTIVE_TRADING_BROKER_NAME.
}

# --- OHLCV Data Collection Settings (used by ohlcv_collector.py) ---
OHLCV_TIMEFRAME: str = "15m"  # Default timeframe (e.g., "1m", "5m", "1h", "1d") for OHLCV data.
                              # Ensure this timeframe is supported by your active broker(s).
OHLCV_LIMIT: int = 100        # Default number of candles to fetch.

# --- Active Trading Broker (used by TradeExecutor via nice_funcs.py) ---
# Specifies the broker (must be a key from BROKER_CONFIGS) to be used for all trading operations
# performed by the TradeExecutor (e.g., through ai_entry, chunk_kill in nice_funcs.py).
# Ensure this broker is properly configured in BROKER_CONFIGS with necessary trading credentials.
ACTIVE_TRADING_BROKER_NAME: str = "deriv"  # Default to "deriv". Change to "icmarkets", "xm", etc. as needed.


# Future variables (not active yet) 🔮
# import os # os is already imported at the top of the Broker Configurations section

sell_at_multiple = 3
USDC_SIZE = 1
# limit = 49 # Commented out as it might conflict with OHLCV_LIMIT. Ensure clarity if reinstated.
# timeframe = '15m' # Commented out as it might conflict with OHLCV_TIMEFRAME. Ensure clarity if reinstated.
stop_loss_perctentage = -.24
EXIT_ALL_POSITIONS = False
DO_NOT_TRADE_LIST = ['777'] # This seems Solana specific, related to EXCLUDED_TOKENS
CLOSED_POSITIONS_TXT = '777' # This seems like a placeholder for a filename, context unclear
minimum_trades_in_last_hour = 777 # This seems Solana/Birdeye specific from token_overview
