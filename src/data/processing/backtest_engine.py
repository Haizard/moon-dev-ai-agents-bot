"""
🌙 Moon Dev's Backtest Engine
High-fidelity market simulation using MongoDB tick/depth data
Built with love by Moon Dev 🚀
"""

import asyncio
import pandas as pd
from termcolor import cprint
from datetime import datetime
from src.data.storage.mongo_db import MongoStorage

class BacktestEngine:
    def __init__(self, initial_capital=10000.0, commission_bps=1.0):
        self.storage = MongoStorage()
        self.initial_capital = initial_capital
        self.current_cash = initial_capital
        self.positions = {} # type: dict[str, dict[str, float]]
        self.commission_rate = float(commission_bps) / 10000.0
        self.trades_history = [] # type: list[dict]
        self.equity_curve = [] # type: list[dict]
        cprint(f"[BACKTEST] Moon Dev's Backtest Engine initialized (Capital: ${initial_capital})", "white", "on_blue")

    async def run_backtest(self, symbol, start_time, end_time=None, strategy=None):
        """Run a backtest on historical MongoDB data"""
        cprint(f"[BACKTEST] Starting simulation for {symbol}...", "white", "on_blue")
        
        try:
            await self.storage.connect()
            collection = self.storage.db["market_data"]
            
            # 1. Fetch data cursor (trades and depth)
            query = {
                "symbol": symbol.upper(),
                "timestamp": {"$gte": start_time}
            }
            if end_time:
                query["timestamp"]["$lte"] = end_time
                
            cursor = collection.find(query).sort("timestamp", 1)
            
            # State for spread modeling
            last_depth = None
            
            async for doc in cursor:
                data_type = doc["type"]
                payload = doc["data"]
                timestamp = doc["timestamp"]
                
                if data_type == "depth":
                    last_depth = payload
                    continue
                
                if data_type == "trade":
                    price = float(payload["price"])
                    # Use last_depth if available to calculate spread-adjusted prices
                    bid, ask = self._get_best_bid_ask(price, last_depth)
                    
                    # Update equity curve
                    self._record_equity(timestamp, price)
                    
                    # 2. Strategy evaluation
                    if strategy:
                        # Pass context to strategy
                        decision = await strategy.evaluate(symbol, price, last_depth)
                        if decision:
                            side = decision["side"]
                            amount_usd = decision["amount_usd"]
                            # Use bid/ask for execution
                            exec_price = ask if side == "BUY" else bid
                            self.place_order(symbol, side, exec_price, amount_usd, timestamp, last_depth)

            cprint(f"[SUCCESS] Backtest complete for {symbol}", "white", "on_green")
            return self.get_summary()
            
        except Exception as e:
            cprint(f"[ERROR] Backtest failed: {str(e)}", "white", "on_red")
            return None
        finally:
            await self.storage.close()

    def _get_best_bid_ask(self, last_price, depth_payload):
        """Model spread based on depth if available, otherwise fallback to last_price"""
        if not depth_payload or 'b' not in depth_payload or 'a' not in depth_payload:
            return last_price * 0.9995, last_price * 1.0005 # Default 10bps spread fallback
            
        bids = depth_payload.get('b', [])
        asks = depth_payload.get('a', [])
        
        if not bids or not asks:
            return last_price * 0.9995, last_price * 1.0005
            
        return float(bids[0][0]), float(asks[0][0])

    def place_order(self, symbol, side, price, amount_usd, timestamp, depth=None):
        """Virtual order execution with slippage and commission"""
        side = side.upper()
        
        # 1. Model Slippage based on depth
        slippage = self._calculate_slippage(amount_usd, price, side, depth)
        exec_price = price * (1 + slippage) if side == "BUY" else price * (1 - slippage)
        
        # 2. Calculate Commission
        commission = amount_usd * self.commission_rate
        net_amount = amount_usd - commission
        
        qty = net_amount / exec_price
        
        if side == "BUY":
            if amount_usd > self.current_cash:
                return False
            self.current_cash -= float(amount_usd)
            if symbol not in self.positions:
                self.positions[symbol] = {"qty": 0.0, "avg_price": 0.0}
            
            # Simple average price update
            pos = self.positions[symbol]
            old_qty = float(pos["qty"])
            old_price = float(pos["avg_price"])
            new_qty = old_qty + float(qty)
            pos["avg_price"] = ((old_price * old_qty) + (float(exec_price) * float(qty))) / new_qty
            pos["qty"] = new_qty
            
        elif side == "SELL":
            if symbol not in self.positions:
                return False
            pos = self.positions[symbol]
            if float(pos["qty"]) < (float(qty) * 0.9999): # Float tolerance
                qty = pos["qty"]
            
            if float(qty) <= 0: return False
            
            self.current_cash += (float(qty) * float(exec_price)) - (float(qty) * float(exec_price) * self.commission_rate)
            pos["qty"] -= float(qty)
            
        self.trades_history.append({
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else timestamp,
            "side": side,
            "price": exec_price,
            "slippage": slippage,
            "qty": qty,
            "amount_usd": amount_usd,
            "commission": commission
        })
        return True

    def _calculate_slippage(self, amount_usd, price, side, depth):
        """Model slippage based on order size vs available top-level liquidity"""
        if not depth:
            return 0.0001 # 1bp default slippage
            
        # Get liquidity at first 3 levels
        levels = depth.get('b' if side == 'SELL' else 'a', [])
        if not levels:
            return 0.0002
            
        top_liquidity_usd = sum([float(l[0]) * float(l[1]) for l in levels[:3]])
        
        # If order is more than 10% of top liquidity, add 1bp slippage for every 10%
        imbalance_ratio = amount_usd / top_liquidity_usd if top_liquidity_usd > 0 else 1.0
        slippage = max(0.0001, (imbalance_ratio // 0.1) * 0.0001)
        
        return min(slippage, 0.01) # Cap at 1% slippage

    def _record_equity(self, timestamp, current_price):
        """Record current total portfolio value"""
        total_value = self.current_cash
        for symbol, pos in self.positions.items():
            total_value += pos["qty"] * current_price # Simplified for single symbol backtest
            
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": total_value
        })

    def get_summary(self):
        """Calculate backtest performance metrics"""
        if not self.equity_curve:
            return {}
            
        final_equity = self.equity_curve[-1]["equity"]
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        df = pd.DataFrame(self.equity_curve)
        df['drawdown'] = (df['equity'].cummax() - df['equity']) / df['equity'].cummax()
        max_drawdown = df['drawdown'].max()
        
        return {
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_return_pct": total_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "trade_count": len(self.trades_history)
        }

if __name__ == "__main__":
    # Test stub
    engine = BacktestEngine()
    import datetime
    start = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    asyncio.run(engine.run_backtest("BTCUSDT", start))
