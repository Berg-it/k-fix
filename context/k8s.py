from kubernetes import client, config
import logging

logger = logging.getLogger(__name__)

def get_k8s_context(namespace: str | None, pod_name: str | None, deployment_name: str | None) -> dict:
    """
    Retrieves the Kubernetes context for a pod and its deployment.
    Handles cases where namespace or deployment_name might be None.
    """
    try:
        config.load_kube_config()
    except:
        config.load_incluster_config()

    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    context = {
        "pod": {},
        "deployment": {},
        "events": [],
        "discovery_info": {}
    }

    # 🔍 Si on a seulement le nom du pod, on fait une découverte complète
    if pod_name and not namespace:
        logger.info(f"🔍 Discovering pod {pod_name} across all namespaces...")
        discovery_result = _discover_pod_automatically(v1, apps_v1, pod_name)
        context.update(discovery_result)
    else:
        # 📋 Méthode classique si on a le namespace
        context["pod"] = _get_pod_context_with_fallback(v1, namespace or "default", pod_name)
        context["deployment"] = _get_deployment_context(apps_v1, namespace or "default", deployment_name)
        context["events"] = _get_pod_events(v1, namespace or "default", pod_name)
    
    return context

def _discover_pod_automatically(v1, apps_v1, pod_name: str) -> dict:
    """
    Découverte automatique d'un pod dans tout le cluster
    Retourne pod, deployment, events et infos de découverte
    """
    discovery_info = {
        "search_strategy": "automatic_discovery",
        "searched_namespaces": [],
        "found_namespace": None,
        "found_deployment": None
    }
    
    try:
        # 📋 1. Lister tous les namespaces
        namespaces = v1.list_namespace()
        
        for ns in namespaces.items:
            namespace_name = ns.metadata.name
            discovery_info["searched_namespaces"].append(namespace_name)
            
            try:
                # 🔍 2. Chercher le pod dans ce namespace
                pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace_name)
                
                logger.info(f"✅ Found pod {pod_name} in namespace {namespace_name}")
                discovery_info["found_namespace"] = namespace_name
                
                # 🏷️ 3. Découvrir le déploiement associé
                deployment_name = _discover_deployment_from_pod(apps_v1, pod)
                if deployment_name:
                    discovery_info["found_deployment"] = deployment_name
                
                # 📦 4. Construire le contexte complet
                return {
                    "pod": _format_pod_info(pod, discovered=True),
                    "deployment": _get_deployment_context(apps_v1, namespace_name, deployment_name) if deployment_name else {},
                    "events": _get_pod_events(v1, namespace_name, pod_name),
                    "discovery_info": discovery_info
                }
                
            except client.exceptions.ApiException:
                continue  # Pod pas dans ce namespace
        
        # ❌ Pod non trouvé dans aucun namespace
        logger.warning(f"❌ Pod {pod_name} not found in any namespace")
        return {
            "pod": {"error": f"Pod {pod_name} not found in any namespace"},
            "deployment": {},
            "events": [],
            "discovery_info": discovery_info
        }
        
    except Exception as e:
        logger.error(f"❌ Error during automatic discovery: {e}")
        return {
            "pod": {"error": f"Discovery failed: {str(e)}"},
            "deployment": {},
            "events": [],
            "discovery_info": discovery_info
        }

def _discover_deployment_from_pod(apps_v1, pod) -> str | None:
    """
    Découvre le déploiement associé à un pod en analysant ses labels/owner references
    """
    try:
        # 🏷️ Méthode 1: Owner References (le plus fiable)
        if pod.metadata.owner_references:
            for owner in pod.metadata.owner_references:
                if owner.kind == "ReplicaSet":
                    # Le ReplicaSet appartient généralement à un Deployment
                    rs_name = owner.name
                    namespace = pod.metadata.namespace
                    
                    try:
                        rs = apps_v1.read_namespaced_replica_set(name=rs_name, namespace=namespace)
                        if rs.metadata.owner_references:
                            for rs_owner in rs.metadata.owner_references:
                                if rs_owner.kind == "Deployment":
                                    logger.info(f"🎯 Found deployment {rs_owner.name} via ReplicaSet")
                                    return rs_owner.name
                    except:
                        pass
        
        # 🏷️ Méthode 2: Labels (fallback)
        if pod.metadata.labels:
            # Chercher des labels communs de déploiement
            deployment_labels = [
                "app.kubernetes.io/name",
                "app",
                "k8s-app"
            ]
            
            for label_key in deployment_labels:
                if label_key in pod.metadata.labels:
                    app_name = pod.metadata.labels[label_key]
                    namespace = pod.metadata.namespace
                    
                    try:
                        # Vérifier si un déploiement avec ce nom existe
                        deployment = apps_v1.read_namespaced_deployment(name=app_name, namespace=namespace)
                        logger.info(f"🎯 Found deployment {app_name} via label {label_key}")
                        return app_name
                    except:
                        continue
        
        logger.warning(f"⚠️ Could not discover deployment for pod {pod.metadata.name}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error discovering deployment: {e}")
        return None

def _get_pod_context_with_fallback(v1, namespace: str, pod_name: str | None) -> dict:
    """Get pod context with fallback strategies"""
    if not pod_name:
        return {"error": "No pod name provided"}
    
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        return _format_pod_info(pod)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"⚠️ Pod {pod_name} not found in namespace {namespace}")
            # 🔍 Fallback: recherche par pattern dans le namespace
            return _search_pod_by_pattern(v1, namespace, pod_name)
        else:
            logger.error(f"❌ Error retrieving pod: {e}")
            return {"error": f"API error: {e}"}

def _search_pod_by_pattern(v1, namespace: str, pod_name: str) -> dict:
    """Search pods by name pattern in a specific namespace"""
    try:
        all_pods = v1.list_namespaced_pod(namespace=namespace)
        
        # 🎯 Recherche par pattern (contient le nom)
        matching_pods = []
        for pod in all_pods.items:
            if pod_name in pod.metadata.name:
                matching_pods.append(pod)
        
        if matching_pods:
            # Prendre le plus récent
            latest_pod = max(matching_pods, key=lambda p: p.metadata.creation_timestamp)
            result = _format_pod_info(latest_pod)
            result["warning"] = f"Exact pod not found, using similar: {latest_pod.metadata.name}"
            logger.info(f"🔍 Found similar pod: {latest_pod.metadata.name}")
            return result
            
        return {"error": f"No pods matching pattern '{pod_name}' found in {namespace}"}
        
    except Exception as e:
        return {"error": f"Pattern search failed: {str(e)}"}

def _format_pod_info(pod, discovered: bool = False) -> dict:
    """Format pod information with optional discovery flag"""
    container_statuses = []
    for c in pod.status.container_statuses or []:
        last_state = "None"
        if c.last_state.terminated:
            last_state = f"Terminated({c.last_state.terminated.reason})"
        container_statuses.append({
            "name": c.name,
            "ready": c.ready,
            "restart_count": c.restart_count,
            "last_state": last_state
        })
    
    result = {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "status": pod.status.phase,
        "restarts": sum(cs.restart_count for cs in pod.status.container_statuses or []),
        "container_statuses": container_statuses
    }
    
    if discovered:
        result["discovery_method"] = "automatic_cluster_search"
    
    return result

def _get_deployment_context(apps_v1, namespace: str, deployment_name: str) -> dict:
    try:
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        resources = {}
        if deployment.spec.template.spec.containers:
            c = deployment.spec.template.spec.containers[0]
            if c.resources:
                resources = {
                    "requests": c.resources.requests or {},
                    "limits": c.resources.limits or {}
                }
        return {
            "name": deployment.metadata.name,
            "replicas": deployment.spec.replicas,
            "ready_replicas": deployment.status.ready_replicas or 0,
            "resources": resources
        }
    except client.exceptions.ApiException as e:
        print(f"Error retrieving deployment: {e}")
        return {}

def _get_pod_events(v1, namespace: str, pod_name: str) -> list:
    try:
        events = v1.list_namespaced_event(namespace=namespace, field_selector=f"involvedObject.name={pod_name}")
        return [
            {
                "type": event.type,
                "reason": event.reason,
                "message": event.message
            }
            for event in events.items
        ]
    except client.exceptions.ApiException as e:
        print(f"Error retrieving events: {e}")
        return []



    