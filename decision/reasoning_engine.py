"""
Reasoning Engine for K-Fix MVP
Core orchestration component for incident resolution workflow
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .llm_client import LLMClient, LLMResponse
from .prompt_templates import PromptTemplates
from .context_formatter import ContextFormatter
from .solution_generator import SolutionGenerator

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Risk levels for solution safety assessment"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

@dataclass
class IncidentAnalysis:
    """Structured incident analysis result"""
    incident_id: str
    analysis: str
    root_cause: str
    solution: str
    prevention: str
    commands: List[str]
    confidence_score: float
    estimated_resolution_time: str
    risk_level: RiskLevel
    
@dataclass
class ReasoningResult:
    """Complete reasoning engine result"""
    incident_analysis: IncidentAnalysis
    llm_response: LLMResponse
    context_summary: Dict[str, Any]
    processing_time: float
    success: bool
    error_message: Optional[str] = None

class ReasoningEngine:
    """
    Core reasoning engine for K-Fix incident resolution
    Orchestrates: Context → LLM → Solution → Actions
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.context_formatter = ContextFormatter()
        self.solution_generator = SolutionGenerator()
        
        # Performance tracking
        self.total_incidents_processed = 0
        self.successful_resolutions = 0
        self.average_processing_time = 0.0
        
    async def analyze_incident(self, enriched_data: Dict[str, Any]) -> ReasoningResult:
        """
        Main entry point for incident analysis
        
        Args:
            enriched_data: Complete enriched incident data containing:
                - event_details: Details of the event that triggered the analysis
                - k8s_context: Kubernetes context information
                - processing_time: When the enrichment was processed
                - enrichment_status: Status of the enrichment process
        """

        start_time = datetime.now()
        
        # Extract incident ID from event_details
        event_details = enriched_data.get("event_details", {})
        incident_id = event_details.get("event_id", f"incident_{int(start_time.timestamp())}")
        
        logger.info(f"🔍 Starting incident analysis: {incident_id}")
        
        try:
            # Step 1: Format and validate context
            formatted_context = await self._prepare_context(enriched_data)
            
            # Step 2: Generate LLM analysis
            llm_response = await self._generate_llm_analysis(formatted_context)
            
            # Step 3: Parse and structure solution
            incident_analysis = await self._parse_llm_response(llm_response, incident_id)
            
            # Step 4: Validate solution safety
            is_safe = await self._validate_solution_safety(incident_analysis)
            
            # Step 5: Calculate confidence and create result
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = ReasoningResult(
                incident_analysis=incident_analysis,
                llm_response=llm_response,
                context_summary=self._create_context_summary(enriched_data),
                processing_time=processing_time,
                success=True
            )
            
            # Update statistics
            self._update_statistics(processing_time, True)
            
            logger.info(f"✅ Incident analysis completed: {incident_id} (confidence: {incident_analysis.confidence_score:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze incident {incident_id}: {e}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_statistics(processing_time, False)
            
            return ReasoningResult(
                incident_analysis=self._create_fallback_analysis(incident_id, str(e)),
                llm_response=LLMResponse(content="", model="fallback", tokens_used=0, cost=0.0),
                context_summary=self._create_context_summary(enriched_data),
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
    
    async def _prepare_context(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and validate context for LLM processing"""
        logger.debug("📋 Preparing context for LLM")
        
        # Format context using ContextFormatter
        formatted_context = self.context_formatter.format_context(enriched_data)
        
        # Validate context completeness
        validation_result = self.context_formatter.validate_context(formatted_context)
        
        if not validation_result["is_valid"]:
            logger.warning(f"⚠️ Context validation issues: {validation_result['issues']}")
        
        return formatted_context
    
    async def _generate_llm_analysis(self, formatted_context: Dict[str, Any]) -> LLMResponse:
        """Generate incident analysis using LLM"""
        logger.debug("🤖 Generating LLM analysis")
        
        # Prepare prompts
        system_prompt = PromptTemplates.get_system_prompt()
        context_prompt = PromptTemplates.get_context_prompt(formatted_context)
        
        # Log prompt sizes for monitoring
        logger.debug(f"📊 Prompt sizes - System: {len(system_prompt)} chars, Context: {len(context_prompt)} chars")
        
        # Generate solution with LLM
        llm_response = await self.llm_client.generate_solution(
            system_prompt=system_prompt,
            context_prompt=context_prompt,
            max_tokens=2000
        )
        
        logger.info(f"💰 LLM call completed - Provider: {llm_response.provider.value}, "
                   f"Tokens: {llm_response.tokens_used}, Cost: ${llm_response.cost_estimate:.4f}")
        
        return llm_response
    
    async def _parse_llm_response(
        self, 
        llm_response: LLMResponse, 
        incident_id: str
    ) -> IncidentAnalysis:
        """Parse and structure LLM response into IncidentAnalysis"""
        logger.debug("📝 Parsing LLM response")
        
        # Use SolutionGenerator to parse the response
        parsed_solution = self.solution_generator.parse_llm_response(llm_response.content)
        
        # Calculate confidence score based on response quality
        confidence_score = self._calculate_confidence_score(llm_response, parsed_solution)
        
        return IncidentAnalysis(
            incident_id=incident_id,
            analysis=parsed_solution.get("analysis", "Analysis not provided"),
            root_cause=parsed_solution.get("root_cause", "Root cause not identified"),
            solution=parsed_solution.get("solution", "Solution not provided"),
            prevention=parsed_solution.get("prevention", "Prevention measures not specified"),
            commands=parsed_solution.get("commands", []),
            confidence_score=confidence_score,
            estimated_resolution_time=parsed_solution.get("estimated_time", "Unknown"),
            risk_level=self._assess_risk_level(parsed_solution)
        )
    
    async def _validate_solution_safety(self, incident_analysis: IncidentAnalysis) -> bool:
        """Validate solution safety before execution"""
        logger.debug("🔒 Validating solution safety")
        
        # Use SolutionGenerator for safety validation
        safety_result = self.solution_generator.validate_solution_safety(
            incident_analysis.solution,
            incident_analysis.commands
        )
        
        return safety_result["is_safe"]
    
    def _calculate_confidence_score(
        self, 
        llm_response: LLMResponse, 
        parsed_solution: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the analysis"""
        score = 0.0
        
        # Base score from response completeness
        required_sections = ["analysis", "root_cause", "solution", "prevention"]
        completed_sections = sum(1 for section in required_sections if parsed_solution.get(section))
        score += (completed_sections / len(required_sections)) * 0.4
        
        # Score from response length (indicates detail)
        response_length = len(llm_response.content)
        if response_length > 500:
            score += 0.2
        elif response_length > 200:
            score += 0.1
        
        # Score from command presence (actionable solution)
        if parsed_solution.get("commands"):
            score += 0.2
        
        # Score from provider reliability
        if llm_response.provider.value == "openai":
            score += 0.1
        elif llm_response.provider.value == "anthropic":
            score += 0.1
        
        return min(score, 1.0)
    
    def _assess_risk_level(self, parsed_solution: Dict[str, Any]) -> str:
        """Assess risk level of the proposed solution"""
        commands = parsed_solution.get("commands", [])
        solution_text = parsed_solution.get("solution", "").lower()
        
        # High risk indicators
        high_risk_keywords = ["delete", "remove", "destroy", "drop", "terminate"]
        if any(keyword in solution_text for keyword in high_risk_keywords):
            return RiskLevel.HIGH
        
        # Medium risk indicators
        medium_risk_keywords = ["restart", "scale", "update", "patch", "modify"]
        if any(keyword in solution_text for keyword in medium_risk_keywords):
            return RiskLevel.MEDIUM
        
        # Check commands for risk
        if commands:
            for cmd in commands:
                if any(risk_cmd in cmd.lower() for risk_cmd in ["delete", "rm", "destroy"]):
                    return RiskLevel.HIGH
        
        return RiskLevel.LOW
    
    def _create_context_summary(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of context for result tracking"""
        event_details = enriched_data.get("event_details", {})
        k8s_context = enriched_data.get("k8s_context", {})
        
        return {
            "event_id": event_details.get("event_id"),
            "event_type": event_details.get("event_type"),
            "namespace": k8s_context.get("namespace"),
            "pod_count": len(k8s_context.get("pods", [])),
            "deployment_count": len(k8s_context.get("deployments", [])),
            "enrichment_status": enriched_data.get("enrichment_status"),
            "processing_timestamp": enriched_data.get("processing_time")
        }
    
    def _create_fallback_analysis(self, incident_id: str, error_message: str) -> IncidentAnalysis:
        """Create fallback analysis when LLM processing fails"""
        return IncidentAnalysis(
            incident_id=incident_id,
            analysis=f"Automated analysis failed: {error_message}",
            root_cause="Unable to determine due to processing error",
            solution="Manual investigation required",
            prevention="Review system logs and contact DevOps team",
            commands=[],
            confidence_score=0.0,
            estimated_resolution_time="Manual",
            risk_level="UNKNOWN"
        )
    
    def _update_statistics(self, processing_time: float, success: bool):
        """Update processing statistics"""
        self.total_incidents_processed += 1
        
        if success:
            self.successful_resolutions += 1
        
        # Update average processing time
        if self.total_incidents_processed == 1:
            self.average_processing_time = processing_time
        else:
            self.average_processing_time = (
                (self.average_processing_time * (self.total_incidents_processed - 1) + processing_time) 
                / self.total_incidents_processed
            )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        success_rate = (
            self.successful_resolutions / self.total_incidents_processed 
            if self.total_incidents_processed > 0 else 0.0
        )
        
        return {
            "total_incidents_processed": self.total_incidents_processed,
            "successful_resolutions": self.successful_resolutions,
            "success_rate": round(success_rate * 100, 2),
            "average_processing_time": round(self.average_processing_time, 2),
            "llm_usage_stats": self.llm_client.get_usage_stats()
        }