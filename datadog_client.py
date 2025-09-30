import os
import logging
from typing import Optional
from datadog_api_client import ApiClient, Configuration

logger = logging.getLogger(__name__)

class DatadogClientManager:
    """Manager for Datadog API client with connection reuse"""
    
    def __init__(self):
        self._client: Optional[ApiClient] = None
        self._config: Optional[Configuration] = None
    
    def _get_datadog_config(self) -> Configuration:
        """Returns Datadog configuration with validation"""
        if self._config is None:
            api_key = os.getenv("DD_API_KEY")
            app_key = os.getenv("DD_APP_KEY")
            
            if not api_key or not app_key:
                raise ValueError("DD_API_KEY and DD_APP_KEY must be defined")
            
            self._config = Configuration(
                api_key={
                    "apiKeyAuth": api_key,
                    "appKeyAuth": app_key,
                },
                server_variables={
                    "site": os.getenv("DD_SITE", "datadoghq.eu"),
                },
            )
            logger.info("🔧 Datadog configuration created")
        
        return self._config
    
    def get_client(self) -> ApiClient:
        """Returns a reusable Datadog API client"""
        if self._client is None:
            self._client = ApiClient(self._get_datadog_config())
            logger.info("🔗 Datadog API client created")
        return self._client
    
    def close(self):
        """Close the Datadog API client"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("🔌 Datadog API client closed")
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._client is not None

# Global instance
datadog_manager = DatadogClientManager()