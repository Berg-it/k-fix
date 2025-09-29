import os
import logging
from time import sleep
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.exceptions import NotFoundException
from context.k8s import get_k8s_context
import json, datetime
from datadog_api_client.v2.api.events_api import EventsApi

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG if os.getenv("ENVIRONMENT", "local") == "local" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load .env.dev only in local environment
if os.getenv("ENVIRONMENT", "local") == "local":
    logger.info("⚙️ Loading .env.dev for local development")
    load_dotenv(dotenv_path=".env.dev")

app = FastAPI(
    title="K-Fix Datadog Webhook",
    description="Service to enrich Datadog alerts with Kubernetes context",
    version="1.0.0"
)

def _get_datadog_config() -> Configuration:
    """Returns Datadog configuration with validation"""
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    
    if not api_key or not app_key:
        raise ValueError("DD_API_KEY and DD_APP_KEY must be defined")
    
    return Configuration(
        api_key={
            "apiKeyAuth": api_key,
            "appKeyAuth": app_key,
        },
        server_variables={
            "site": os.getenv("DD_SITE", "datadoghq.eu"),
        },
    )

def _get_runtime_event(event_id: int) -> Dict[str, Any]:
    """Retrieves event details from Datadog"""
    if not event_id:
        logger.warning("Event ID not provided")
        return {}
        
    try:
        with ApiClient(_get_datadog_config()) as api_client:
            # TODO: Find a way to avoid the sleep (queue the request)
            sleep(62)
            events_api = EventsApi(api_client)
            evt = events_api.get_event(str(event_id))

            return {
                "id": evt.data.id,
                "date_happened": evt.data.attributes.timestamp,
                "alert_type": evt.data.attributes.attributes.get("alert_type"),
                "text": evt.data.attributes.message,
                "tags": evt.data.attributes.tags or []
            }
    except NotFoundException:
        logger.error(f"Event {event_id} not found")
        return {}
    except Exception as e:
        logger.error(f"Error retrieving event {event_id}: {e}")
        return {}

def _extract_k8s_info_from_tags(tags: list) -> tuple[str, Optional[str], Optional[str]]:
    """Extracts Kubernetes information from tags"""
    namespace = "default"
    pod_name = None
    deployment_name = None
    
    for tag in tags:
        if tag.startswith("pod_name:"):
            pod_name = tag.split(":", 1)[1]
        elif tag.startswith("kube_namespace:"):
            namespace = tag.split(":", 1)[1]
        elif tag.startswith("kube_deployment:"):
            deployment_name = tag.split(":", 1)[1]
    
    return namespace, pod_name, deployment_name

def _validate_payload(payload: Dict[str, Any]) -> None:
    """Validates Datadog payload"""
    required_fields = ["alert_id"]
    missing_fields = [field for field in required_fields if not payload.get(field)]
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing fields: {', '.join(missing_fields)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "local"),
        "version": "1.0.0"
    }

@app.post("/datadog-webhook")
async def datadog_webhook(request: Request):
    """Main endpoint to receive Datadog webhooks"""
    try:
        payload = await request.json()
        logger.info(f"🚨 Alert received from Datadog: {payload.get('title', 'No title')}")
        logger.debug(f"Complete payload: {payload}")

        # Payload validation
        _validate_payload(payload)
        
        alert_id = payload.get("alert_id")
        event_id = payload.get("event_id")

        # Runtime event retrieval
        runtime_event = _get_runtime_event(int(event_id))
        
        # K8s information extraction
        namespace, pod_name, deployment_name = _extract_k8s_info_from_tags(
            runtime_event.get("tags", [])
        )
        
        logger.info(f"K8s info extracted - Namespace: {namespace}, Pod: {pod_name}, Deployment: {deployment_name}")

        # K8s context retrieval if necessary
        k8s_context = {}
        if pod_name or deployment_name:
            try:
                k8s_context = get_k8s_context(namespace, pod_name, deployment_name)
                logger.info("K8s context retrieved successfully")
            except Exception as e:
                logger.error(f"Error retrieving K8s context: {e}")
                k8s_context = {"error": str(e)}

        # Context bundle construction
        context_bundle = {
            "alert": {
                "id": alert_id,
                "event_id": event_id,
                "event_type": payload.get("event_type"),
                "title": payload.get("title"),
                "date": payload.get("date"),
                "body_raw": payload.get("body"),
            },
            "runtime_event": runtime_event,
            "k8s_context": k8s_context,
            "logs": [],
            "metrics": {},
            "processed_at": datetime.datetime.utcnow().isoformat()
        }

        logger.info(f"📡 Enriched alert created for {alert_id}")
        logger.info(f"Complete bundle: {json.dumps(context_bundle, indent=2, default=str)}")

        return JSONResponse(content={"status": "ok", "alert_id": alert_id}, status_code=200)

    except HTTPException:
        raise  # Re-raise HTTPExceptions
    except NotFoundException:
        logger.error(f"Monitor {alert_id} not found")
        return JSONResponse(
            content={"status": "monitor_not_found", "alert_id": alert_id},
            status_code=404
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)