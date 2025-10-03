"""
Prompt templates for K-Fix MVP
Optimized prompts for Kubernetes incident resolution
"""

from typing import Dict, Any

class PromptTemplates:
    """Structured prompt templates for K-Fix"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """System prompt defining K-Fix role and capabilities"""
        return """You are K-Fix, a DevOps/SRE expert specialized in Kubernetes incident resolution.

MISSION:
- Analyze Kubernetes incidents with precision
- Propose concrete and safe solutions
- Generate automatable GitLab actions
- Prioritize stability and security

EXPERTISE:
- Kubernetes (pods, deployments, services, ingress)
- Observability (metrics, logs, traces)
- Infrastructure as Code
- DevOps/SRE best practices

CONSTRAINTS:
- ALWAYS propose testable solutions
- NEVER destructive modifications without confirmation

RESPONSE FORMAT:
1. **ANALYSIS**: Incident diagnosis
2. **ROOT CAUSE**: Main problem identification
3. **SOLUTION**: Concrete actions to perform
4. **PREVENTION**: Measures to avoid recurrence"""

    @staticmethod
    def get_context_prompt(enriched_data: Dict[str, Any]) -> str:
        """Generate context prompt from enriched data"""
        
        # Extract data from enriched_data
        event_details = enriched_data.get("event_details", {})
        k8s_context = enriched_data.get("k8s_context", {})
        processing_time = enriched_data.get("processing_time")
        enrichment_status = enriched_data.get("enrichment_status", "unknown")
        
        prompt = f"""INCIDENT TO ANALYZE:

=== EVENT DETAILS ===
Event ID: {event_details.get('event_id', 'N/A')}
Title: {event_details.get('title', 'N/A')}
Message: {event_details.get('message', 'N/A')}
Timestamp: {event_details.get('timestamp', 'N/A')}
Tags: {', '.join(event_details.get('tags', []))}

=== KUBERNETES CONTEXT ==="""
        
        # Pod context
        pod_info = k8s_context.get("pod", {})
        if pod_info and "error" not in pod_info:
            prompt += f"""
Pod:
- Name: {pod_info.get('name', 'N/A')}
- Namespace: {pod_info.get('namespace', 'N/A')}
- Status: {pod_info.get('status', 'N/A')}
- Restarts: {pod_info.get('restarts', 0)}
- Containers: {len(pod_info.get('container_statuses', []))}"""
            
            # Container details
            for container in pod_info.get('container_statuses', []):
                prompt += f"""
  - {container.get('name')}: Ready={container.get('ready')}, Restarts={container.get('restart_count')}, LastState={container.get('last_state')}"""
        else:
            prompt += f"\nPod: {pod_info.get('error', 'Information not available')}"
        
        # Deployment context
        deployment_info = k8s_context.get("deployment", {})
        if deployment_info and "error" not in deployment_info:
            prompt += f"""

Deployment:
- Name: {deployment_info.get('name', 'N/A')}
- Desired replicas: {deployment_info.get('replicas', 'N/A')}
- Ready replicas: {deployment_info.get('ready_replicas', 'N/A')}"""
            
            resources = deployment_info.get('resources', {})
            if resources:
                prompt += f"""
- Resources: {resources}"""
        else:
            prompt += f"\nDeployment: {deployment_info.get('error', 'Information not available')}"
        
        # Kubernetes Events
        events = k8s_context.get("events", [])
        if events:
            prompt += f"\n\nRecent events:"
            for event in events[:5]:  # Limit to 5 events
                prompt += f"""
- {event.get('type', 'N/A')}: {event.get('reason', 'N/A')} - {event.get('message', 'N/A')}"""
        
        # Automatic discovery information
        discovery_info = k8s_context.get("discovery_info", {})
        if discovery_info:
            prompt += f"""

=== AUTOMATIC DISCOVERY ===
Strategy: {discovery_info.get('search_strategy', 'N/A')}
Found namespace: {discovery_info.get('found_namespace', 'N/A')}
Discovered deployment: {discovery_info.get('found_deployment', 'N/A')}"""
        
        # Processing metadata
        if processing_time:
            prompt += f"""

=== PROCESSING METADATA ===
Processing time: {processing_time:.2f}s
Enrichment status: {enrichment_status}"""
        
        prompt += """

INSTRUCTIONS:
Analyze this incident and propose a structured solution according to the requested format.
Focus on concrete and automatable actions."""
        
        return prompt

    @staticmethod
    def get_validation_prompt(solution: str) -> str:
        """Prompt to validate a solution before execution"""
        return f"""SOLUTION VALIDATION:

Proposed solution:
{solution}

REQUIRED CHECKS:
1. Is the solution safe? (no data deletion)
2. Are the commands correct?
3. Are there any production risks?
4. Does the solution address the root cause?

Answer YES/NO with justification for each point."""