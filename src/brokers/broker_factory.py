"""
🌙 Moon Dev's Broker Factory
Built with love by Moon Dev 🚀

This module manages all available broker integrations and provides access to them.
"""

from typing import Dict, List, Optional, Type, Any
from termcolor import cprint

from .base_broker import BaseBroker
# Import specific broker implementations here as they are created
from .deriv_broker import DerivBroker
from .icmarkets_broker import ICMarketsBroker
from .xm_broker import XMBroker
from .exness_broker import ExnessBroker

class BrokerFactory:
    """
    Factory for creating and managing broker instances.
    Provides a unified way to access different broker integrations.
    """

    # BROKER_IMPLEMENTATIONS will be populated as new brokers are implemented.
    # Keys are broker names (e.g., "deriv", "icmarkets")
    # Values are the broker implementation classes.
    BROKER_IMPLEMENTATIONS: Dict[str, Type[BaseBroker]] = {
        "deriv": DerivBroker,
        "icmarkets": ICMarketsBroker,
        "xm": XMBroker,
        "exness": ExnessBroker,
    }

    _instance: Optional['BrokerFactory'] = None

    def __new__(cls, *args, **kwargs) -> 'BrokerFactory':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initializes the BrokerFactory.
        This is called only once due to the singleton pattern.
        """
        # Ensure __init__ is idempotent for the singleton
        if hasattr(self, '_initialized') and self._initialized:
            return

        cprint("\n🏗️ Creating new BrokerFactory instance (singleton)...", "cyan")
        # In the future, this could load broker configurations, e.g.,
        # from src/config.py, to determine enabled brokers or specific API key names.
        self._initialized = True
        cprint("🏭 BrokerFactory initialized.", "green")


    def get_broker(self, broker_name: str, api_key: Optional[str] = None,
                   api_secret: Optional[str] = None, **kwargs: Any) -> Optional[BaseBroker]:
        """
        Retrieves, instantiates, and connects to a specific broker.

        Args:
            broker_name (str): The name of the broker to retrieve (e.g., "deriv").
            api_key (Optional[str]): The API key for the broker.
            api_secret (Optional[str]): The API secret for the broker.
            **kwargs (Any): Additional configuration parameters specific to the broker
                            (e.g., account_id, environment='demo'/'live').

        Returns:
            Optional[BaseBroker]: An instance of the requested broker if successful,
                                  otherwise None.
        """
        cprint(f"\n🔍 Requesting broker: '{broker_name}'", "cyan")

        broker_class = self.BROKER_IMPLEMENTATIONS.get(broker_name.lower())

        if not broker_class:
            cprint(f"❌ Broker type '{broker_name}' not found in BROKER_IMPLEMENTATIONS.", "red")
            cprint(f"  Available brokers: {self.get_available_brokers() or 'None'}", "yellow")
            return None

        try:
            cprint(f"  Instantiating broker: {broker_class.__name__}...", "magenta")
            # Prepare config for the broker, merging kwargs
            broker_config = kwargs
            broker_instance = broker_class(api_key=api_key, api_secret=api_secret, config=broker_config)

            cprint(f"  Attempting to connect to {broker_name}...", "magenta")
            broker_instance.connect()  # This method should handle its own success/failure logging

            # Verify connection, e.g., using ping or checking a client attribute
            if broker_instance.ping(): # Assuming ping() indicates successful connection
                cprint(f"✅ Successfully connected to broker: {broker_name}", "green")
                return broker_instance
            else:
                cprint(f"⚠️ Connection to {broker_name} established, but ping failed. Broker might not be fully ready.", "yellow")
                # Depending on strictness, you might return None or the instance
                # For now, let's assume if connect() didn't raise and ping is problematic, it's a partial success.
                # A more robust ping in BaseBroker or specific implementations is needed.
                # If connect() is expected to set up everything for ping to pass, this indicates an issue.
                # Consider returning None if strict connectivity is required post-connect via ping.
                # For this initial factory, let's return the instance if connect() passes.
                # The ping() method itself in BaseBroker returns self.client is not None.
                # If connect() sets self.client, ping() should pass.
                return broker_instance

        except NotImplementedError as nie:
            cprint(f"❌ Critical error: Broker '{broker_name}' ({broker_class.__name__}) has not fully implemented the BaseBroker interface.", "red")
            cprint(f"  Details: {nie}", "red")
            return None
        except Exception as e:
            cprint(f"❌ Failed to instantiate or connect to broker '{broker_name}': {e}", "red")
            # Attempt to disconnect if instance was created but connection failed partially
            if 'broker_instance' in locals() and broker_instance:
                try:
                    broker_instance.disconnect()
                except Exception as disconnect_e:
                    cprint(f"  Failed to clean up/disconnect broker instance: {disconnect_e}", "red")
            return None

    def get_available_brokers(self) -> List[str]:
        """
        Returns a list of names of all registered broker implementations.

        Returns:
            List[str]: A list of broker names.
        """
        return list(self.BROKER_IMPLEMENTATIONS.keys())

# Create a singleton instance of the factory
broker_factory = BrokerFactory()
