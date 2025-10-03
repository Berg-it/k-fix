"""
Context Formatter for K-Fix MVP
Formats and validates context bundles for LLM processing
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ContextFormatter:
    """
    Formats context bundles for optimal LLM processing
    Handles validation, compression, and structure optimization
    """
    
    def __init__(self):
        self.max_context_size = 8000  # characters
        self.max_events = 10
        self.max_metrics = 15
        
    def format_context(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format enriched data for LLM processing
        
        Args:
            enriched_data: Enriched incident data containing:
                - event_details: Event information from Datadog
                - k8s_context: Kubernetes context information
                - processing_time: Processing timestamp
                - enrichment_status: Status of enrichment
            
        Returns:
            Formatted and optimized context
        """
        logger.debug("📋 Formatting enriched data for LLM")
        
        formatted_context = {
            "event_context": self._format_event_context(enriched_data.get("event_details", {})),
            "k8s_context": self._format_k8s_context(enriched_data.get("k8s_context", {})),
            "metadata": self._create_metadata(enriched_data)
        }
        
        # Compress if too large
        if self._calculate_context_size(formatted_context) > self.max_context_size:
            logger.warning("⚠️ Context too large, applying compression")
            formatted_context = self._compress_context(formatted_context)
        
        return formatted_context
    
    def validate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate context completeness and quality
        
        Returns:
            Validation result with issues list
        """
        issues = []
        is_valid = True
        
        # Check event context presence
        event_context = context.get("event_context", {})
        if not event_context or not event_context.get("event_id"):
            issues.append("Missing or incomplete event information")
            is_valid = False
        
        # Check Kubernetes context
        k8s_context = context.get("k8s_context", {})
        if not k8s_context:
            issues.append("Missing Kubernetes context")
            is_valid = False
        else:
            pods = k8s_context.get("pods", [])
            if not pods:
                issues.append("No pod information available")
        
        # Check if we have any actionable context
        has_actionable_context = (
            event_context.get("event_id") or 
            k8s_context.get("pods") or
            k8s_context.get("deployments")
        )
        
        if not has_actionable_context:
            issues.append("No actionable context available")
            is_valid = False
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "completeness_score": self._calculate_completeness_score(context)
        }
    
    def _format_event_context(self, event_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format event details from Datadog
        
        Based on the actual structure:
        {
            "event_id": event_id,
            "title": event_response.data.attributes.attributes.title,
            "message": event_response.data.attributes.message,
            "timestamp": event_response.data.attributes.timestamp,
            "tags": event_response.data.attributes.tags or []
        }
        """
        return {
            "event_id": event_details.get("event_id"),
            "title": event_details.get("title", ""),
            "message": self._truncate_text(event_details.get("message", ""), 500),
            "timestamp": event_details.get("timestamp"),
            "tags": event_details.get("tags", []),
            "formatted_timestamp": self._format_timestamp(event_details.get("timestamp")),
            "tag_summary": self._extract_tag_summary(event_details.get("tags", []))
        }
    
    def _format_k8s_context(self, k8s_context: Dict[str, Any]) -> Dict[str, Any]:
        """Format Kubernetes context information"""
        if not k8s_context:
            return {}
        
        formatted_k8s = {
            "namespace": k8s_context.get("namespace"),
            "pods": [self._format_pod_info(pod) for pod in k8s_context.get("pods", [])],
            "deployments": [self._format_deployment_info(dep) for dep in k8s_context.get("deployments", [])],
            "events": self._format_events(k8s_context.get("events", []))
        }
        
        # Add summary statistics
        formatted_k8s["summary"] = {
            "total_pods": len(formatted_k8s["pods"]),
            "total_deployments": len(formatted_k8s["deployments"]),
            "total_events": len(formatted_k8s["events"]),
            "pod_statuses": self._get_pod_status_summary(formatted_k8s["pods"])
        }
        
        return formatted_k8s
    
    def _format_pod_info(self, pod_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format individual pod information"""
        return {
            "name": pod_info.get("name"),
            "status": pod_info.get("status"),
            "ready": pod_info.get("ready"),
            "restarts": pod_info.get("restarts", 0),
            "age": pod_info.get("age"),
            "node": pod_info.get("node"),
            "containers": pod_info.get("containers", [])
        }
    
    def _format_deployment_info(self, deployment_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format individual deployment information"""
        return {
            "name": deployment_info.get("name"),
            "ready_replicas": deployment_info.get("ready_replicas", 0),
            "total_replicas": deployment_info.get("replicas", 0),
            "available_replicas": deployment_info.get("available_replicas", 0),
            "age": deployment_info.get("age"),
            "strategy": deployment_info.get("strategy")
        }
    
    def _format_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format Kubernetes events, keeping only the most recent and relevant"""
        if not events:
            return []
        
        # Sort by timestamp (most recent first) and limit
        sorted_events = sorted(
            events, 
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )[:self.max_events]
        
        formatted_events = []
        for event in sorted_events:
            formatted_events.append({
                "type": event.get("type"),
                "reason": event.get("reason"),
                "message": self._truncate_text(event.get("message", ""), 200),
                "timestamp": event.get("timestamp"),
                "object": event.get("object"),
                "count": event.get("count", 1)
            })
        
        return formatted_events
    

    
    def _create_metadata(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata about the enriched data"""
        return {
            "formatted_at": datetime.now().isoformat(),
            "data_sources": list(enriched_data.keys()),
            "enrichment_status": enriched_data.get("enrichment_status"),
            "processing_time": enriched_data.get("processing_time"),
            "estimated_size": self._calculate_context_size(enriched_data)
        }
    
    def _compress_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Compress context if it's too large"""
        compressed = context.copy()
        
        # Reduce number of events
        if "k8s_context" in compressed and "events" in compressed["k8s_context"]:
            compressed["k8s_context"]["events"] = compressed["k8s_context"]["events"][:5]
        
        # Truncate long messages
        if "event_context" in compressed and "message" in compressed["event_context"]:
            compressed["event_context"]["message"] = self._truncate_text(
                compressed["event_context"]["message"], 300
            )
        
        # Reduce pod details if still too large
        if self._calculate_context_size(compressed) > self.max_context_size:
            if "k8s_context" in compressed and "pods" in compressed["k8s_context"]:
                for pod in compressed["k8s_context"]["pods"]:
                    if "containers" in pod:
                        pod["containers"] = pod["containers"][:3]  # Keep only first 3 containers
        
        return compressed
    
    def _calculate_context_size(self, context: Dict[str, Any]) -> int:
        """Calculate approximate context size in characters"""
        try:
            return len(json.dumps(context, default=str))
        except Exception:
            return len(str(context))
    
    def _calculate_completeness_score(self, context: Dict[str, Any]) -> float:
        """Calculate completeness score based on available data"""
        score = 0.0
        max_score = 100.0
        
        # Event context scoring (40 points)
        event_context = context.get("event_context", {})
        if event_context.get("event_id"):
            score += 10
        if event_context.get("title"):
            score += 10
        if event_context.get("message"):
            score += 10
        if event_context.get("tags"):
            score += 10
        
        # K8s context scoring (60 points)
        k8s_context = context.get("k8s_context", {})
        if k8s_context.get("namespace"):
            score += 10
        if k8s_context.get("pods"):
            score += 20
        if k8s_context.get("deployments"):
            score += 15
        if k8s_context.get("events"):
            score += 15
        
        return min(score / max_score, 1.0)
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length"""
        if not text or len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def _format_timestamp(self, timestamp: Any) -> str:
        """Format timestamp for better readability"""
        if not timestamp:
            return ""
        
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            else:
                dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            return str(timestamp)
    
    def _extract_tag_summary(self, tags: List[str]) -> Dict[str, Any]:
        """Extract useful information from tags"""
        summary = {
            "total_tags": len(tags),
            "service_tags": [tag for tag in tags if tag.startswith("service:")],
            "env_tags": [tag for tag in tags if tag.startswith("env:")],
            "k8s_tags": [tag for tag in tags if any(k8s_key in tag for k8s_key in ["pod:", "deployment:", "namespace:"])],
            "other_tags": []
        }
        
        # Collect other relevant tags
        for tag in tags:
            if not any(tag.startswith(prefix) for prefix in ["service:", "env:", "pod:", "deployment:", "namespace:"]):
                summary["other_tags"].append(tag)
        
        return summary
    
    def _get_pod_status_summary(self, pods: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get summary of pod statuses"""
        status_counts = {}
        for pod in pods:
            status = pod.get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts