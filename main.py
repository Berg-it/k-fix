import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import datetime
import asyncio
import hashlib
import time
from contextlib import asynccontextmanager

# Import our custom modules
from external_resource_service import datadog_manager, AlertDatabase, AlertStatus
from context import get_k8s_context

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG if os.getenv("ENVIRONMENT", "local") == "local" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

db: AlertDatabase | None = None

# Load environment variables for local development
if os.getenv("ENVIRONMENT", "local") == "local":
    logger.info("⚙️ Loading .env.dev for local development")
    load_dotenv(dotenv_path=".env.dev")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db
    
    # Startup
    logger.info("🚀 Starting K-Fix application")
    try:
        db = AlertDatabase()
        await db.initialize()
        logger.info("✅ Database initialized")
        
        # Start background worker
        asyncio.create_task(_alert_worker())
        logger.info("🔄 Alert worker started")
        
        yield
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Shutting down K-Fix application")
        if datadog_manager:
            datadog_manager.close()
        logger.info("✅ Application shutdown complete")

app = FastAPI(
    title="K-Fix Datadog Webhook",
    description="Service to enrich Datadog alerts with Kubernetes context",
    version="1.0.0",
    lifespan=lifespan
)

def _extract_k8s_info_from_tags(tags: list) -> tuple[str, str | None, str | None]:
    """Extract Kubernetes information from Datadog tags"""
    pod_name = None
    namespace = None
    deployment = None
    
    for tag in tags:
        if tag.startswith("pod_name:"):
            pod_name = tag.split(":", 1)[1]
        elif tag.startswith("kube_namespace:"):
            namespace = tag.split(":", 1)[1]
        elif tag.startswith("kube_deployment:"):
            deployment = tag.split(":", 1)[1]
    
    return pod_name, namespace, deployment

def _validate_payload(payload: Dict[str, Any]) -> None:
    """Validate incoming webhook payload"""
    if not payload.get("event_id"):
        raise ValueError("Missing eventType in payload")
    if not payload.get("alert_id"):
        raise ValueError("Missing id in payload")

def _generate_alert_hash(payload: Dict[str, Any]) -> str:
    """Generate a unique hash for the alert to prevent duplicates"""
    alert_data = f"{payload.get('id', '')}-{payload.get('eventType', '')}-{payload.get('date', '')}"
    return hashlib.md5(alert_data.encode()).hexdigest()

async def _process_alert_async(payload: Dict[str, Any], alert_hash: str):
    """Process alert asynchronously with enrichment"""
    if not db:
        logger.error("Database not initialized")
        return
    
    try:
        # Update status to processing
        await db.update_alert_status(alert_hash, AlertStatus.PROCESSING)
        logger.info(f"🔄 Processing alert {alert_hash[:8]}")
        
        # Get runtime event details
        event_id = payload.get("event_id")
        if event_id:
            try:
                event_details = await datadog_manager.get_runtime_event(int(event_id))
                logger.info(f"📊 Retrieved event details for {event_id}")
                
                # Extract K8s info from tags
                tags = event_details.get("tags", [])
                pod_name, namespace, deployment = _extract_k8s_info_from_tags(tags)
                
                if pod_name:
                    # Get Kubernetes context
                    k8s_context = await get_k8s_context(namespace, pod_name, deployment)  # ✅ Ajouter await
                    
                    # Combine all information
                    enriched_data = {
                        "event_details": event_details,
                        "k8s_context": k8s_context,
                        "processing_time": time.time(),
                        "enrichment_status": "success"
                    }
                    
                    # Update alert with enriched data and ENRICHED status
                    await db.update_alert_status(alert_hash, AlertStatus.ENRICHED, enriched_data=enriched_data)
                    logger.info(f"✅ Alert {alert_hash[:8]} enriched successfully")
                else:
                    logger.warning(f"⚠️ No pod information found in tags for alert {alert_hash[:8]}")
                    await db.update_alert_status(alert_hash, AlertStatus.FAILED)
                    
            except Exception as e:
                logger.error(f"❌ Failed to get event details for {event_id}: {e}")
                await db.update_alert_status(alert_hash, AlertStatus.FAILED)
        else:
            logger.warning(f"⚠️ No event ID found in payload for alert {alert_hash[:8]}")
            await db.update_alert_status(alert_hash, AlertStatus.FAILED)
            
    except Exception as e:
        logger.error(f"❌ Failed to process alert {alert_hash}: {e}")
        await db.update_alert_status(alert_hash, AlertStatus.FAILED)

async def _alert_worker():
    """Background worker to process alerts from the queue"""
    if not db:
        logger.error("Database not initialized for alert worker")
        return
        
    logger.info("🔄 Alert worker started")
    
    while True:
        try:
            # Get pending alerts
            pending_alerts = await db.get_pending_alerts()
            
            if pending_alerts:
                logger.info(f"📋 Processing {len(pending_alerts)} pending alerts")
                
                for alert in pending_alerts:
                    try:
                        alert_hash = alert["alert_hash"]  # ✅ Corriger l'accès
                        payload = alert["payload"]
                        
                        # Process the alert
                        await _process_alert_async(payload, alert_hash)
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to process alert {alert['alert_hash'][:8]}: {e}")
                        if db:
                            await db.update_alert_status(alert["alert_hash"], AlertStatus.FAILED)  # ✅ Ajouter await et corriger
            
            # Wait before checking again
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Alert worker error: {e}")
            await asyncio.sleep(10)

#Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "database": db is not None,
        "datadog": datadog_manager.is_connected() if datadog_manager else False
    }

@app.post("/datadog-webhook")
async def datadog_webhook(request: Request):
    """Handle incoming Datadog webhooks"""
    try:
        payload = await request.json()
        logger.info(f"📨 Received webhook: {payload.get('event_id', 'unknown')}")
        
        # Validate payload
        _validate_payload(payload)
        
        # Generate alert hash for deduplication
        alert_hash = _generate_alert_hash(payload)
        
        # Check if we've already processed this alert
        if db and await db.is_alert_received(alert_hash):  # ✅ Ajouter await
            logger.info(f"🔄 Alert {alert_hash} already exists, skipping")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "duplicate",
                    "message": "Alert already processed",
                    "alert_hash": alert_hash
                }
            )
        
        # ✅ SAUVEGARDER l'alert dans la base
        if db:
            await db.save_alert(payload, alert_hash)
            logger.info(f"💾 Alert {alert_hash[:8]} saved to database")
        
        # Queue the alert for processing
        logger.info(f"📥 Queuing alert {alert_hash} for processing")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Alert queued for processing",
                "alert_hash": alert_hash
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Webhook processing failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/queue/status")
async def queue_status():
    """Get current queue status"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        pending_alerts = await db.get_pending_alerts()  # ✅ Ajouter await
        return JSONResponse(
            status_code=200,
            content={
                "pending_alerts": len(pending_alerts),
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=f"Queue status failed: {str(e)}")

@app.post("/admin/cleanup")
async def cleanup_old_alerts(days: int = 30):
    """Clean up old alerts from the database"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        deleted_count = await db.cleanup_old_alerts(days)  # ✅ Ajouter await
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Cleaned up {deleted_count} alerts older than {days} days",
                "deleted_count": deleted_count
            }
        )
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")