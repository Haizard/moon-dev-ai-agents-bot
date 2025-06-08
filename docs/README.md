# Project Documentation

Welcome to the documentation for the AI Agents for Trading project! This section provides more detailed information about specific aspects of the project.

**We are currently in Alpha. Documentation is actively being developed alongside the codebase.**

## 🎬 Video Documentation
The most comprehensive and up-to-date information, including live coding and explanations, can be found in Moon Dev's YouTube playlist:
- [ALL DOCUMENTATION VIDEOS & Project Updates](https://www.youtube.com/playlist?list=PLXrNVMjRZUJg4M4uz52iGd1LhXXGVbIFz)

As Anthropic mentioned in their research on building effective agents, understanding the intricacies of AI agent systems is key. Watching the detailed development videos is highly recommended for a deep dive into the code and concepts.

## 🚀 Getting Started & Main Overview
For the main project overview, setup instructions, quick start guide, and disclaimers, please refer to the main [README.md](../../README.md) in the project root.

## 核心架构

The project is built with a modular architecture to support various AI models and trading broker integrations.

### 🤖 AI Model Integration
- **Model Factory (`src/models/model_factory.py`):** Manages all supported AI models (Gemini, Groq, OpenAI, Claude, DeepSeek).
- **Configuration (`src/config.py`):**
    - `CORE_AI_MODEL_TYPE`: Set your preferred default AI model provider (e.g., "gemini", "groq").
    - `CORE_AI_MODEL_NAME`: Optionally specify a particular model from that provider.
    - API keys for each model provider must be set as environment variables (e.g., `GEMINI_KEY`, `GROQ_API_KEY`). See the main `README.md` for a full list.

### 📈 Broker Integration
- **Base Broker Interface (`src/brokers/base_broker.py`):** Defines a common structure for all broker integrations.
- **Broker Factory (`src/brokers/broker_factory.py`):** Manages and provides instances of different broker clients.
- **Supported Brokers:**
    - Deriv (`deriv`): Direct WebSocket API integration.
    - IC Markets (`icmarkets`): MetaTrader 5 based.
    - XM.com (`xm`): MetaTrader 5 based (placeholder, inherits IC Markets logic).
    - Exness (`exness`): MetaTrader 5 based (placeholder, inherits IC Markets logic).
- **Configuration (`src/config.py`):**
    - `ACTIVE_BROKERS`: List of brokers for the OHLCV data collector.
    - `ACTIVE_TRADING_BROKER_NAME`: Specifies the broker for trade execution via the `TradeExecutor`.
    - `BROKER_CONFIGS`: Dictionary to store credentials (loaded from environment variables like `DERIV_API_TOKEN`, `ICMARKETS_LOGIN_ID`, etc.) and settings for each broker.
    - **Note for MetaTrader 5 Brokers:** Requires a running MT5 terminal, logged into your account. Credentials and server details must be accurate in your `.env` file and referenced in `BROKER_CONFIGS`.

### ⚙️ Trade Execution
- **Trade Executor (`src/trading/execution_service.py`):** A centralized service that uses the `ACTIVE_TRADING_BROKER_NAME` to perform trading operations (buy/sell market/limit orders) via the configured broker.
- **Utility Functions (`src/nice_funcs.py`):** Functions like `ai_entry` and `chunk_kill` now use the `TradeExecutor` for CEX-style trading, while Solana-specific trading functions remain separate.

## 📄 Specific API Documentation
- **MoonDev Market Data API (`docs/api.md`):** Documents an API agent (`src/agents/api.py`) for fetching specialized market data (liquidations, funding rates, etc.) from an external MoonDev data source. This is distinct from the individual broker data fetching capabilities.

## 💡 Examples
- For examples and further plans on documentation structure, see [docs/examples/examplespan.md](./examples/examplespan.md).

We encourage active participation and contributions to improve both the codebase and its documentation.