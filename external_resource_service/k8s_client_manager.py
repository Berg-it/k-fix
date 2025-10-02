from kubernetes import client, config
import logging
import threading
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class K8sClientManager:
    """singleton"""
    _instance = None
    _lock = threading.Lock()
    _v1_client: Optional[client.CoreV1Api] = None
    _apps_v1_client: Optional[client.AppsV1Api] = None
    _config_loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def _load_config_once(self):
        """Charge la configuration Kubernetes une seule fois"""
        if not self._config_loaded:
            try:
                config.load_kube_config()
                logger.info("✅ Kubernetes config loaded from kubeconfig")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load kubeconfig: {e}")
                try:
                    config.load_incluster_config()
                    logger.info("✅ Kubernetes config loaded from in-cluster")
                except Exception as e2:
                    logger.error(f"❌ Failed to load in-cluster config: {e2}")
                    raise e2
            self._config_loaded = True
    
    def get_clients(self) -> Tuple[client.CoreV1Api, client.AppsV1Api]:
        """Retourne les clients Kubernetes réutilisables"""
        if self._v1_client is None or self._apps_v1_client is None:
            with self._lock:
                if self._v1_client is None or self._apps_v1_client is None:
                    self._load_config_once()
                    self._v1_client = client.CoreV1Api()
                    self._apps_v1_client = client.AppsV1Api()
                    logger.info("🔧 Kubernetes clients initialized")
        
        return self._v1_client, self._apps_v1_client
    
    def reset_clients(self):
        """Reset les clients (utile pour les tests ou reconnexion)"""
        with self._lock:
            self._v1_client = None
            self._apps_v1_client = None
            self._config_loaded = False
            logger.info("🔄 Kubernetes clients reset")
    
    def is_initialized(self) -> bool:
        """Vérifie si les clients sont initialisés"""
        return self._v1_client is not None and self._apps_v1_client is not None
    
    def get_config_status(self) -> dict:
        """Retourne le statut de la configuration pour debugging"""
        return {
            "config_loaded": self._config_loaded,
            "clients_initialized": self.is_initialized(),
            "v1_client_type": type(self._v1_client).__name__ if self._v1_client else None,
            "apps_v1_client_type": type(self._apps_v1_client).__name__ if self._apps_v1_client else None
        }