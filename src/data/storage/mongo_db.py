"""
🌙 Moon Dev's MongoDB Storage Layer
Efficient time-series storage for market data
Built with love by Moon Dev 🚀
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from termcolor import colored, cprint
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MongoStorage:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGO_DB_NAME", "moon_dev_trading")
        self.client = None
        self.db = None
        cprint("[STORAGE] Moon Dev's MongoDB Storage Layer initialized", "white", "on_blue")

    async def connect(self):
        """Establish connection to MongoDB"""
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            # Test connection
            await self.client.admin.command('ping')
            cprint("[SUCCESS] Successfully connected to MongoDB", "white", "on_green")
        except Exception as e:
            cprint(f"[ERROR] Failed to connect to MongoDB: {str(e)}", "white", "on_red")
            raise

    async def save_market_data(self, symbol, data_type, payload):
        """Save raw market data to the database"""
        if self.db is None or self.client is None:
            await self.connect()
            
        if self.db is not None:
            collection = self.db["market_data"]
            document = {
                "symbol": symbol.upper(),
                "type": data_type,
                "timestamp": datetime.utcnow(),
                "data": payload
            }
            
            try:
                await collection.insert_one(document)
            except Exception as e:
                cprint(f"[ERROR] Error saving market data: {str(e)}", "white", "on_red")

    async def close(self):
        """Close the MongoDB connection"""
        if self.client:
            self.client.close()
            cprint("[CLOSED] MongoDB connection closed", "white", "on_blue")
