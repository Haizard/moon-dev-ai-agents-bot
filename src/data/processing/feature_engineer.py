"""
🌙 Moon Dev's Feature Engineering Agent
Transforms raw market data into institutional-grade features
Built with love by Moon Dev 🚀
"""

import pandas as pd
import pandas_ta as ta
from datetime import datetime
from termcolor import colored, cprint

from src.data.storage.mongo_db import MongoStorage

class FeatureEngineer:
    def __init__(self):
        self.storage = MongoStorage()
        cprint("[FEATURE ENGINE] Moon Dev's Feature Engineering Agent initialized", "white", "on_blue")

    async def generate_features_from_db(self, symbol, lookback_trades=100):
        """Fetch trades from DB and generate features"""
        try:
            await self.storage.connect()
            collection = self.storage.db["trades"]
            
            # Fetch last N trades
            cursor = collection.find({"symbol": symbol.upper()}).sort("timestamp", -1).limit(lookback_trades)
            trades = await cursor.to_list(length=lookback_trades)
            
            if not trades:
                return None
                
            # Convert to DataFrame style list for existing logic
            trade_list = [t["data"] for t in trades]
            
            # 1. Calculate Microstructure
            features = self.calculate_microstructure_features(trade_list)
            
            # 2. Add metadata
            payload = {
                "symbol": symbol.upper(),
                "timestamp": datetime.utcnow(),
                "features": features
            }
            
            # 3. Save to features_dataset
            await self.storage.save_to_collection("features_dataset", symbol, payload)
            cprint(f"[FEATURE ENGINE] Persisted {len(features)} features for {symbol}", "white", "on_green")
            
            return features
        except Exception as e:
            cprint(f"[ERROR] generate_features_from_db failed: {str(e)}", "white", "on_red")
            return None

    def calculate_basic_indicators(self, df):
        """Calculate standard technical indicators using pandas_ta"""
        try:
            # Momentum
            df['RSI'] = ta.rsi(df['Close'], length=14)
            
            # Volatility
            bbands = ta.bbands(df['Close'], length=20, std=2)
            df = pd.concat([df, bbands], axis=1)
            
            # Trend
            df['EMA_20'] = ta.ema(df['Close'], length=20)
            df['EMA_50'] = ta.ema(df['Close'], length=50)
            
            # Volume
            df['OBV'] = ta.obv(df['Close'], df['Volume'])
            
            cprint("[FEATURE ENGINE] Successfully engineered basic technical features", "white", "on_green")
            return df
        except Exception as e:
            cprint(f"❌ Error calculating basic indicators: {str(e)}", "white", "on_red")
            return df

    def calculate_microstructure_features(self, trade_data):
        """Calculate features from tick/trade level data"""
        try:
            if not trade_data:
                return {}
                
            df = pd.DataFrame(trade_data)
            if df.empty:
                return {}

            # Calculate metrics
            total_volume = df['quantity'].sum()
            buy_volume = df[df['is_buyer_maker'] == False]['quantity'].sum()
            sell_volume = df[df['is_buyer_maker'] == True]['quantity'].sum()
            
            # Volume Imbalance (positive = buyer pressure, negative = seller pressure)
            imbalance = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0
            
            # Average trade size
            avg_trade_size = df['quantity'].mean()
            
            # Trade count
            trade_count = len(df)
            
            cprint(f"[FEATURE ENGINE] Engineered microstructure: {imbalance:.2f} imbalance over {trade_count} trades", "white", "on_green")
            
            return {
                "volume_imbalance": imbalance,
                "buy_v_sell_ratio": buy_volume / sell_volume if sell_volume > 0 else float('inf'),
                "avg_trade_size": avg_trade_size,
                "trade_count": trade_count
            }
        except Exception as e:
            cprint(f"❌ Error calculating microstructure features: {str(e)}", "white", "on_red")
            return {}

    def calculate_liquidity_features(self, depth_data):
        """Calculate features from order book depth data"""
        try:
            if not depth_data or 'data' not in depth_data:
                return {}
            
            # Extract bids and asks from the partial book depth
            # Binance partial depth format: {'bids': [['price', 'qty'], ...], 'asks': ...}
            raw_depth = depth_data['data']
            bids = raw_depth.get('b', [])
            asks = raw_depth.get('a', [])
            
            if not bids or not asks:
                return {}
                
            # Best bid/ask
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            
            # Spread
            spread = (best_ask - best_bid) / best_bid if best_bid > 0 else 0
            
            # Simple Liquidity Depth (sum of top 5 levels)
            bid_depth = sum([float(b[1]) for b in bids[:5]])
            ask_depth = sum([float(a[1]) for a in asks[:5]])
            
            # Depth Imbalance
            depth_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0
            
            return {
                "spread_bps": spread * 10000,
                "bid_depth_top5": bid_depth,
                "ask_depth_top5": ask_depth,
                "depth_imbalance": depth_imbalance
            }
        except Exception as e:
            cprint(f"❌ Error calculating liquidity features: {str(e)}", "white", "on_red")
            return {}
