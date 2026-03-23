"""
🌙 Moon Dev's BirdEye Continuous Collector
Polls BirdEye API for on-chain metrics and persists to MongoDB
Built with love by Moon Dev 🚀
"""

import asyncio
import os
from datetime import datetime
from termcolor import colored, cprint
from dotenv import load_dotenv

# Import Moon Dev components
from src.data.storage.mongo_db import MongoStorage
from src.nice_funcs import token_overview, token_security_info
from src.config import MONITORED_TOKENS

load_dotenv()

class BirdEyeCollector:
    def __init__(self, interval=300): # Default 5 minutes
        self.interval = interval
        self.storage = MongoStorage()
        self.tokens = MONITORED_TOKENS
        cprint(f"[BIRDEYE] Collector initialized for {len(self.tokens)} tokens", "white", "on_blue")

    async def collect_token_data(self, token_address):
        """Fetch and store data for a single token"""
        try:
            # 1. Get Overview (Price, Vol, etc)
            overview = token_overview(token_address)
            if not overview:
                return

            # 2. Get Security Info (Only occasionally or if missing?)
            security = token_security_info(token_address)
            
            # 3. Combine and persistent
            payload = {
                "address": token_address,
                "overview": overview,
                "security": security,
                "collected_at": datetime.utcnow().isoformat()
            }
            
            # Save to 'tokens' collection
            # We use the address as a sub-key or just store the snapshot
            await self.storage.save_to_collection("tokens", token_address, payload)
            
            symbol = overview.get('symbol', 'UNKNOWN')
            price = overview.get('price', 0)
            cprint(f"[BIRDEYE] Saved data for {symbol} ({token_address[:4]}...): ${price}", "cyan")
            
        except Exception as e:
            cprint(f"[ERROR] BirdEye collection failed for {token_address}: {str(e)}", "white", "on_red")

    async def start(self):
        """Main collection loop"""
        cprint("[BIRDEYE] Starting continuous collection loop...", "white", "on_blue")
        await self.storage.connect()
        
        while True:
            tasks = [self.collect_token_data(addr) for addr in self.tokens]
            await asyncio.gather(*tasks)
            
            cprint(f"[BIRDEYE] Cycle complete. Sleeping for {self.interval}s...", "white", "on_blue")
            await asyncio.sleep(self.interval)

if __name__ == "__main__":
    collector = BirdEyeCollector()
    asyncio.run(collector.start())
