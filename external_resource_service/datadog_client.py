import os
import logging
import asyncio
import datetime
from typing import Dict, Any
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.events_api import EventsApi
from datadog_api_client.exceptions import NotFoundException
from datadog_api_client.v2.model.v2_event_response import V2EventResponse

logger = logging.getLogger(__name__)

class DatadogClientManager:
    """Manager for Datadog API client with connection reuse"""
    
    def __init__(self):
        self._client: ApiClient | None = None
        self._config: Configuration | None = None
    
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

    async def get_runtime_event(self, event_id: int) -> Dict[str, Any]:
        """Retrieve runtime event details from Datadog"""
        try:
            client = self.get_client()
            events_api = EventsApi(client)
            event_response: V2EventResponse = events_api.get_event(event_id=str(event_id))
            
            return {
                "event_id": event_id,
                "title": event_response.data.attributes.attributes.title,
                "message": event_response.data.attributes.message,
                "timestamp": event_response.data.attributes.timestamp,
                "tags": event_response.data.attributes.tags or []
            }
        except NotFoundException:
            logger.warning(f"Event {event_id} not found in Datadog")
            return {
                "event_id": event_id,
                "title": "Event not found",
                "message": "This event could not be retrieved from Datadog",
                "timestamp": datetime.datetime.now(),
                "tags": []
            }

# Global instance
datadog_manager = DatadogClientManager()