import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datadog_api_client.exceptions import NotFoundException
from context.k8s import get_k8s_context
import datetime
from datadog_api_client.v2.api.events_api import EventsApi
import asyncio
import hashlib
import time
from contextlib import asynccontextmanager

# Import our custom modules
from datadog_client import datadog_manager
from database import AlertDatabase, AlertStatus

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG if os.getenv("ENVIRONMENT", "local") == "local" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database instance
db: Optional[AlertDatabase] = None

# Load .env.dev only in local environment
if os.getenv("ENVIRONMENT", "local") == "local":
    logger.info("⚙️ Loading .env.dev for local development")
    load_dotenv(dotenv_path=".env.dev")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global db
    
    # Startup
    db = AlertDatabase()
    await db.initialize()
    
    asyncio.create_task(_alert_worker())
    logger.info("🚀 Alert worker started")
    
    # Initialize Datadog client
    datadog_manager.get_client()
    logger.info("🔗 Datadog client initialized")
    
    yield
    
    # Shutdown
    await db.close()
    datadog_manager.close()
    logger.info("🛑 Application shutdown complete")

app = FastAPI(
    title="K-Fix Datadog Webhook",
    description="Service to enrich Datadog alerts with Kubernetes context",
    version="1.0.0",
    lifespan=lifespan
)

async def _get_runtime_event(event_id: int) -> Dict[str, Any]:
    """Retrieve runtime event details from Datadog"""
    try:
        client = datadog_manager.get_client()
        events_api = EventsApi(client)
        
        # Simulate processing time
        await asyncio.sleep(62)
        
        response = events_api.get_event(event_id=str(event_id))
        
        return {
            "event_id": event_id,
            "title": response.data.attributes.title,
            "message": response.data.attributes.message,
            "timestamp": response.data.attributes.timestamp,
            "tags": response.data.attributes.tags or []
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

def _extract_k8s_info_from_tags(tags: list) -> tuple[str, Optional[str], Optional[str]]:
    """Extract Kubernetes information from Datadog tags"""
    namespace = None
    pod_name = None
    cluster_name = "default"
    
    for tag in tags:
        if tag.startswith("kube_namespace:"):
            namespace = tag.split(":", 1)[1]
        elif tag.startswith("pod_name:"):
            pod_name = tag.split(":", 1)[1]
        elif tag.startswith("kube_cluster_name:"):
            cluster_name = tag.split(":", 1)[1]
    
    return cluster_name, namespace, pod_name

def _validate_payload(payload: Dict[str, Any]) -> None:
    """Validate the incoming webhook payload"""
    required_fields = ["eventType", "id"]
    for field in required_fields:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = "healthy" if db and db.is_connected else "disconnected"
    
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "database": db_status
    }

def _generate_alert_hash(payload: Dict[str, Any]) -> str:
    """Generate a unique hash for the alert"""
    alert_data = f"{payload.get('id', '')}-{payload.get('eventType', '')}"
    return hashlib.md5(alert_data.encode()).hexdigest()

async def _process_alert_async(payload: Dict[str, Any], alert_hash: str):
    """Process alert asynchronously with enrichment"""
    try:
        # Update status to processing
        await db.update_alert_status(alert_hash, AlertStatus.PROCESSING)
        
        logger.info(f"🔄 Processing alert {alert_hash[:8]}")
        
        # Get runtime event details
        event_id = payload.get("id")
        runtime_event = await _get_runtime_event(int(event_id)) if event_id else {}
        
        # Extract K8s information
        tags = payload.get("tags", []) + runtime_event.get("tags", [])
        cluster_name, namespace, pod_name = _extract_k8s_info_from_tags(tags)
        
        # Get K8s context if we have the necessary information
        k8s_context = {}
        if namespace and pod_name:
            try:
                k8s_context = await get_k8s_context(cluster_name, namespace, pod_name)
                logger.info(f"🎯 K8s context retrieved for {namespace}/{pod_name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get K8s context: {e}")
        
        # Mark as resolved
        #await db.update_alert_status(alert_hash, "resolved")
        
        logger.info(f"✅ Alert {alert_hash[:8]} processed successfully")
        
        return {
            "alert_hash": alert_hash,
            "status": "processed",
            "runtime_event": runtime_event,
            "k8s_context": k8s_context,
            "processing_time": time.time()
        }
        
    except Exception as e:
        # Update status to resolved
        await db.update_alert_status(alert_hash, AlertStatus.RESOLVED)
        
        logger.error(f"❌ Error processing alert {alert_hash[:8]}: {e}")
        await db.update_alert_status(alert_hash, AlertStatus.FAILED, str(e))

async def _alert_worker():
    """Worker that processes alerts from database every minute"""
    logger.info("🔄 Alert worker started - checking database every minute")
    
    while True:
        try:
            # Get alerts that need processing
            alerts = await db.get_pending_alerts(limit=10)
            
            if alerts:
                logger.info(f"📋 Found {len(alerts)} alerts to process")
                
                # Process alerts in parallel
                tasks = []
                for alert in alerts:
                    alert_hash = alert['alert_hash']
                    payload = alert['payload']
                    
                    task = asyncio.create_task(
                        _process_alert_async(payload, alert_hash)
                    )
                    tasks.append(task)
                
                # Wait for all tasks to complete
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            
            # Wait 1 minute before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Error in alert worker: {e}")
            await asyncio.sleep(60)  # Wait before retrying

@app.post("/datadog-webhook")
async def datadog_webhook(request: Request):
    """Webhook endpoint for Datadog alerts"""
    try:
        payload = await request.json()
        logger.info(f"📨 Received webhook: {payload.get('eventType', 'unknown')}")
        
        # Validate payload
        _validate_payload(payload)
        
        # Generate alert hash
        alert_hash = _generate_alert_hash(payload)
        
        # Check if alert already received
        if await db.is_alert_received(alert_hash):
            logger.info(f"🔄 Alert {alert_hash[:8]} already received, skipping")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "duplicate",
                    "message": "Alert already received",
                    "alert_hash": alert_hash
                }
            )
        
        # Save alert to database
        if await db.save_alert(alert_hash, payload):
            logger.info(f"✅ Alert {alert_hash[:8]} queued for processing")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "received",
                    "message": "Alert queued for processing",
                    "alert_hash": alert_hash
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save alert")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/queue/status")
async def queue_status():
    """Get current queue status and database statistics"""
    try:
        stats = await db.get_alert_statistics()
        
        return {
            "database_status": "connected" if db.is_connected else "disconnected",
            **stats,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting queue status: {e}")
        return {
            "database_status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.post("/admin/cleanup")
async def cleanup_old_alerts(days: int = 30):
    """Admin endpoint to cleanup old alerts"""
    try:
        deleted_count = await db.cleanup_old_alerts(days)
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} alerts older than {days} days"
        }
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")