import os
import logging
import json
from typing import Dict, Any, List
from enum import Enum
import asyncpg
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class AlertStatus(Enum):
    """Enumeration for alert status values"""
    RECEIVED = "received"
    PROCESSING = "processing"
    ENRICHED = "enriched"
    SOLUTION_PROPOSED = "solution_proposed"
    RESOLVED = "resolved"
    FAILED = "failed"
    
    def __str__(self) -> str:
        """Return the string value for database operations"""
        return self.value

class AlertDatabase:
    """Database manager for alert storage and retrieval"""
    
    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._config = self._get_db_config()
    
    def _get_db_config(self) -> Dict[str, Any]:
        """Get database configuration from environment variables"""
        required_env_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        
        # Check if all required environment variables are set
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        try:
            db_port = int(os.getenv("DB_PORT"))
        except (ValueError, TypeError):
            raise ValueError("DB_PORT must be a valid integer")
        
        return {
            "host": os.getenv("DB_HOST"),
            "port": db_port,
            "database": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }
    
    async def initialize(self) -> None:
        """Initialize database connection pool and create tables"""
        try:
            logger.info(f"🔗 Connecting to database: {self._config['user']}@{self._config['host']}:{self._config['port']}/{self._config['database']}")
            
            # Create connection pool with proper timeouts
            self.pool = await asyncpg.create_pool(
                **self._config,
                min_size=2,
                max_size=10,
                command_timeout=30,  # Timeout pour les commandes (30 secondes)
                server_settings={
                    'application_name': 'k-fix-agent',
                    'tcp_keepalives_idle': '600',
                    'tcp_keepalives_interval': '30',
                    'tcp_keepalives_count': '3'
                }
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
            logger.info("✅ Database initialized successfully")
            
        except ValueError as e:
            logger.error(f"❌ Database configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    async def _create_tables(self) -> None:
        """Create database tables and indexes"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=10.0) as conn:
                # Create alerts table
                await asyncio.wait_for(
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS alerts (
                            alert_hash VARCHAR(64) PRIMARY KEY,
                            payload JSONB NOT NULL,
                            enriched_data JSONB NULL,
                            status VARCHAR(20) DEFAULT $1,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW(),
                            processed_at TIMESTAMP NULL,
                            retry_count INTEGER DEFAULT 0,
                            error_message TEXT NULL
                        );
                    """, str(AlertStatus.RECEIVED)),
                    timeout=15.0
                )
                
                # Create indexes
                await asyncio.wait_for(
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_status_created 
                        ON alerts(status, created_at);
                    """),
                    timeout=10.0
                )
                
                await asyncio.wait_for(
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_hash 
                        ON alerts(alert_hash);
                    """),
                    timeout=10.0
                )
                
                logger.info("📋 Database tables and indexes created")
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout during table creation")
            raise
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection pool"""
        if self.pool:
            try:
                await asyncio.wait_for(self.pool.close(), timeout=5.0)
                logger.info("🔒 Database connection pool closed")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout while closing database pool")
            except Exception as e:
                logger.error(f"❌ Error closing database pool: {e}")
    
    async def is_alert_received(self, alert_hash: str) -> bool:
        """Check if alert has already been received"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                result = await asyncio.wait_for(
                    conn.fetchval(
                        "SELECT id FROM alerts WHERE alert_hash = $1",
                        alert_hash
                    ),
                    timeout=10.0
                )
                return result is not None
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout checking alert {alert_hash[:8]}")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking alert {alert_hash[:8]}: {e}")
            return False
    
    async def save_alert(self, payload: Dict[str, Any], alert_hash: str) -> str:
        """Save alert to database and return alert_hash"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                await asyncio.wait_for(
                    conn.execute("""
                        INSERT INTO alerts (alert_hash, payload) 
                        VALUES ($1, $2)
                        ON CONFLICT (alert_hash) DO NOTHING
                    """, alert_hash, json.dumps(payload)),
                    timeout=10.0
                )
            logger.info(f"💾 Alert {alert_hash[:8]} saved to database")
            return alert_hash
        except Exception as e:
            logger.error(f"❌ Failed to save alert {alert_hash[:8]}: {e}")
            raise
    
    async def update_alert_status(self, alert_hash: str, status: AlertStatus, error_message: str = None, enriched_data: Dict[str, Any] = None) -> None:
        """Update alert status with optional enriched data"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                if status == AlertStatus.RESOLVED:
                    # For resolved status, set processed_at
                    if enriched_data:
                        await asyncio.wait_for(
                            conn.execute("""
                                UPDATE alerts 
                                SET status = $1, updated_at = NOW(), processed_at = NOW(), enriched_data = $2
                                WHERE alert_hash = $3
                            """, str(status), json.dumps(enriched_data), alert_hash),
                            timeout=10.0
                        )
                    else:
                        await asyncio.wait_for(
                            conn.execute("""
                                UPDATE alerts 
                                SET status = $1, updated_at = NOW(), processed_at = NOW()
                                WHERE alert_hash = $2
                            """, str(status), alert_hash),
                            timeout=10.0
                        )
                else:
                    # For other statuses
                    if enriched_data:
                        await asyncio.wait_for(
                            conn.execute("""
                                UPDATE alerts 
                                SET status = $1, updated_at = NOW(), enriched_data = $2, error_message = $3,
                                    retry_count = retry_count + 1
                                WHERE alert_hash = $4
                            """, str(status), json.dumps(enriched_data), error_message, alert_hash),
                            timeout=10.0
                        )
                    else:
                        await asyncio.wait_for(
                            conn.execute("""
                                UPDATE alerts 
                                SET status = $1, updated_at = NOW(), error_message = $2,
                                    retry_count = retry_count + 1
                                WHERE alert_hash = $3
                            """, str(status), error_message, alert_hash),
                            timeout=10.0
                        )
                    
            if enriched_data:
                logger.info(f"📊 Alert {alert_hash[:8]} status updated to {status.value} with enriched data")
            else:
                logger.info(f"📝 Alert {alert_hash[:8]} status updated to {status.value}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update alert {alert_hash[:8]} status: {e}")
    
    async def get_pending_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get alerts that need processing (received > 1 minute ago)"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                alerts = await asyncio.wait_for(
                    conn.fetch("""
                        SELECT alert_hash, payload 
                        FROM alerts 
                        WHERE status = $1 
                        AND created_at < NOW() - INTERVAL '1 minute'
                        ORDER BY created_at ASC
                        LIMIT $2
                    """, str(AlertStatus.RECEIVED), limit),
                    timeout=15.0
                )
                
                return [
                    {
                        "alert_hash": alert['alert_hash'],
                        "payload": json.loads(alert['payload'])
                    }
                    for alert in alerts
                ]
        except Exception as e:
            logger.error(f"❌ Error getting pending alerts: {e}")
            return []
    
    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                # Get counts by status
                stats = await asyncio.wait_for(
                    conn.fetch("""
                        SELECT status, COUNT(*) as count
                        FROM alerts
                        GROUP BY status
                    """),
                    timeout=10.0
                )
                
                # Get recent alerts
                recent = await asyncio.wait_for(
                    conn.fetch("""
                        SELECT alert_hash, status, created_at, updated_at
                        FROM alerts
                        ORDER BY created_at DESC
                        LIMIT 10
                    """),
                    timeout=10.0
                )
                
                status_counts = {row['status']: row['count'] for row in stats}
                recent_alerts = [
                    {
                        "hash": row['alert_hash'][:8],
                        "status": row['status'],
                        "created": row['created_at'].isoformat(),
                        "updated": row['updated_at'].isoformat()
                    }
                    for row in recent
                ]
                
                return {
                    "alert_counts": status_counts,
                    "recent_alerts": recent_alerts
                }
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout getting alert statistics")
            return {"alert_counts": {}, "recent_alerts": []}
        except Exception as e:
            logger.error(f"❌ Error getting alert statistics: {e}")
            return {"alert_counts": {}, "recent_alerts": []}
    
    async def cleanup_old_alerts(self, days: int = 30) -> int:
        """Clean up old resolved alerts (optional maintenance method)"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=5.0) as conn:
                # ✅ CORRECTION: Utilisation des énumérations avec paramètres sécurisés
                result = await asyncio.wait_for(
                    conn.execute("""
                        DELETE FROM alerts 
                        WHERE status IN ($1, $2) 
                        AND updated_at < NOW() - INTERVAL '$3 days'
                    """, str(AlertStatus.RESOLVED), str(AlertStatus.FAILED), str(days)),
                    timeout=30.0
                )
                
                # Extraction sécurisée du nombre de lignes supprimées
                try:
                    deleted_count = int(result.split()[-1]) if result else 0
                except (ValueError, IndexError):
                    deleted_count = 0
                
                logger.info(f"🧹 Cleaned up {deleted_count} old alerts")
                return deleted_count
                
        except asyncio.TimeoutError:
            logger.error("❌ Timeout during cleanup operation")
            return 0
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
            return 0
    
    async def get_connection_health(self) -> Dict[str, Any]:
        """Check database connection health with timeout"""
        try:
            async with asyncio.wait_for(self.pool.acquire(), timeout=3.0) as conn:
                start_time = datetime.now()
                await asyncio.wait_for(
                    conn.fetchval("SELECT 1"),
                    timeout=5.0
                )
                response_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time * 1000, 2),
                    "pool_size": self.pool.get_size(),
                    "pool_free": self.pool.get_size() - self.pool.get_idle_size()
                }
                
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": "Database connection timeout"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self.pool is not None and not self.pool._closed