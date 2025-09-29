from kubernetes import client, config

def get_k8s_context(namespace: str, pod_name: str, deployment_name: str) -> dict:
    """
    Retrieves the Kubernetes context for a pod and its deployment.
    Returns a structured dict with pod, deployment, and events.
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
        "events": []
    }

    context["pod"] = _get_pod_context(v1, namespace, pod_name)
    context["deployment"] = _get_deployment_context(apps_v1, namespace, deployment_name)
    context["events"] = _get_pod_events(v1, namespace, pod_name)
    
    return context


def _get_pod_context(v1, namespace: str, pod_name: str) -> dict:
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
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
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "restarts": sum(cs.restart_count for cs in pod.status.container_statuses or []),
            "container_statuses": container_statuses
        }
    except client.exceptions.ApiException as e:
        print(f"Error retrieving pod: {e}")
        return {}

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



    