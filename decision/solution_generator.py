"""
Solution Generator for K-Fix MVP
Parses LLM responses and generates actionable solutions
"""

import logging
import re
from typing import Dict, Any, List
from enum import Enum
import json

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Risk levels for solution safety assessment"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Priority(Enum):
    """Priority levels for incident resolution"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class SolutionGenerator:
    """
    Generates structured solutions from LLM responses
    Handles parsing, validation, and action generation
    """
    
    def __init__(self):
        self.dangerous_commands = [
            "rm -rf", "delete", "destroy", "drop", "truncate",
            "format", "mkfs", "dd if=", "kill -9"
        ]
        
        self.kubectl_destructive = [
            "delete", "destroy", "remove"
        ]
    
    def parse_llm_response(self, llm_content: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured solution
        
        Args:
            llm_content: Raw LLM response text
            
        Returns:
            Structured solution dictionary
        """
        logger.debug("📝 Parsing LLM response into structured solution")
        
        solution = {
            "analysis": "",
            "root_cause": "",
            "solution": "",
            "prevention": "",
            "commands": [],
            "estimated_time": "Unknown",
            "priority": Priority.MEDIUM.value
        }
        
        try:
            # Parse sections using regex patterns
            solution["analysis"] = self._extract_section(llm_content, "ANALYSIS", "ANALYSE")
            solution["root_cause"] = self._extract_section(llm_content, "ROOT CAUSE", "CAUSE RACINE")
            solution["solution"] = self._extract_section(llm_content, "SOLUTION")
            solution["prevention"] = self._extract_section(llm_content, "PREVENTION", "PRÉVENTION")
            
            # Extract commands
            solution["commands"] = self._extract_commands(llm_content)
            
            # Extract estimated time if mentioned
            solution["estimated_time"] = self._extract_estimated_time(llm_content)
            
            # Determine priority based on content
            solution["priority"] = self._determine_priority(llm_content)
            
            logger.debug(f"✅ Successfully parsed solution with {len(solution['commands'])} commands")
            
        except Exception as e:
            logger.error(f"❌ Error parsing LLM response: {e}")
            solution["analysis"] = f"Parsing error: {str(e)}"
            solution["solution"] = "Manual review required due to parsing failure"
        
        return solution
    
    def validate_solution_safety(self, solution_text: str, commands: List[str]) -> Dict[str, Any]:
        """
        Validate solution safety before execution
        
        Returns:
            Safety validation result
        """
        logger.debug("🔒 Validating solution safety")
        
        safety_issues = []
        risk_level = RiskLevel.LOW
        
        # Check solution text for dangerous keywords
        solution_lower = solution_text.lower()
        for dangerous_cmd in self.dangerous_commands:
            if dangerous_cmd in solution_lower:
                safety_issues.append(f"Dangerous command detected: {dangerous_cmd}")
                risk_level = RiskLevel.HIGH
        
        # Check individual commands
        for cmd in commands:
            cmd_lower = cmd.lower().strip()
            
            # Check for destructive kubectl commands
            if cmd_lower.startswith("kubectl"):
                for destructive in self.kubectl_destructive:
                    if destructive in cmd_lower:
                        safety_issues.append(f"Destructive kubectl command: {cmd}")
                        risk_level = "HIGH"
            
            # Check for system-level dangerous commands
            for dangerous_cmd in self.dangerous_commands:
                if dangerous_cmd in cmd_lower:
                    safety_issues.append(f"Dangerous system command: {cmd}")
                    risk_level = "HIGH"
        
        # Determine if solution is safe
        is_safe = risk_level != RiskLevel.HIGH
        
        return {
            "is_safe": is_safe,
            "risk_level": risk_level.value,
            "safety_issues": safety_issues,
            "recommendations": self._generate_safety_recommendations(safety_issues)
        }
    
    def generate_gitlab_actions(self, solution: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        """
        Generate GitLab merge request actions from solution
        
        Returns:
            GitLab action specification
        """
        logger.debug("🔧 Generating GitLab actions")
        
        # Create branch name
        branch_name = f"fix/incident-{incident_id}"
        
        # Generate commit message
        commit_message = self._generate_commit_message(solution, incident_id)
        
        # Generate file changes
        file_changes = self._generate_file_changes(solution)
        
        # Create MR description
        mr_description = self._generate_mr_description(solution, incident_id)
        
        return {
            "branch_name": branch_name,
            "commit_message": commit_message,
            "file_changes": file_changes,
            "merge_request": {
                "title": f"Fix: Incident {incident_id} - {solution.get('root_cause', 'Unknown issue')[:50]}",
                "description": mr_description,
                "target_branch": "main",
                "labels": ["incident-fix", "automated", f"priority-{solution.get('priority', 'medium').lower()}"],
                "assignee": None,  # Will be set by configuration
                "auto_merge": False  # Require manual approval for safety
            }
        }
    
    def generate_slack_notification(self, solution: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
        """
        Generate Slack notification from solution
        
        Returns:
            Slack message specification
        """
        logger.debug("💬 Generating Slack notification")
        
        # Determine message color based on priority
        color_map = {
            "High": "#ff0000",    # Red
            "Medium": "#ffaa00",  # Orange
            "Low": "#00aa00"      # Green
        }
        
        priority = solution.get("priority", "Medium")
        color = color_map.get(priority, "#ffaa00")
        
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Incident Analysis Complete: {incident_id}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:* {priority}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Estimated Time:* {solution.get('estimated_time', 'Unknown')}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n{solution.get('root_cause', 'Not identified')[:200]}..."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Proposed Solution:*\n{solution.get('solution', 'No solution provided')[:300]}..."
                }
            }
        ]
        
        # Add commands if present
        commands = solution.get("commands", [])
        if commands:
            command_text = "\n".join([f"• `{cmd}`" for cmd in commands[:3]])
            if len(commands) > 3:
                command_text += f"\n... and {len(commands) - 3} more commands"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Commands to Execute:*\n{command_text}"
                }
            })
        
        return {
            "channel": "#incidents",  # Will be configurable
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks
                }
            ]
        }
    
    def _extract_section(self, content: str, *section_names: str) -> str:
        """Extract content from a specific section"""
        for section_name in section_names:
            # Try different patterns
            patterns = [
                rf"\*\*{section_name}\*\*[:\s]*(.+?)(?=\*\*|\n\n|$)",
                rf"{section_name}[:\s]*(.+?)(?=\n\n|$)",
                rf"\d+\.\s*\*\*{section_name}\*\*[:\s]*(.+?)(?=\d+\.|$)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(1).strip()
        
        return ""
    
    def _extract_commands(self, content: str) -> List[str]:
        """Extract commands from LLM response"""
        commands = []
        
        # Look for code blocks
        code_blocks = re.findall(r'```(?:bash|shell|sh)?\n(.*?)\n```', content, re.DOTALL)
        for block in code_blocks:
            lines = block.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    commands.append(line)
        
        # Look for kubectl commands specifically
        kubectl_commands = re.findall(r'kubectl\s+[^\n]+', content)
        commands.extend(kubectl_commands)
        
        # Look for other common commands
        command_patterns = [
            r'helm\s+[^\n]+',
            r'docker\s+[^\n]+',
            r'systemctl\s+[^\n]+'
        ]
        
        for pattern in command_patterns:
            found_commands = re.findall(pattern, content)
            commands.extend(found_commands)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)
        
        return unique_commands[:10]  # Limit to 10 commands
    
    def _extract_estimated_time(self, content: str) -> str:
        """Extract estimated resolution time"""
        time_patterns = [
            r'estimated?\s+time[:\s]*([^\n]+)',
            r'resolution\s+time[:\s]*([^\n]+)',
            r'should\s+take[:\s]*([^\n]+)',
            r'(\d+\s*(?:minutes?|hours?|mins?))'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Unknown"
    
    def _determine_priority(self, content: str) -> str:
        """Determine priority based on content analysis"""
        content_lower = content.lower()
        
        # High priority indicators
        high_priority_keywords = [
            "critical", "urgent", "down", "outage", "failure", 
            "crash", "emergency", "severe", "production"
        ]
        
        # Low priority indicators
        low_priority_keywords = [
            "minor", "cosmetic", "enhancement", "optimization",
            "cleanup", "documentation", "low impact"
        ]
        
        high_count = sum(1 for keyword in high_priority_keywords if keyword in content_lower)
        low_count = sum(1 for keyword in low_priority_keywords if keyword in content_lower)
        
        if high_count > low_count and high_count > 0:
            return Priority.HIGH.value
        elif low_count > 0:
            return Priority.LOW.value
        else:
            return Priority.MEDIUM.value
    
    def _generate_safety_recommendations(self, safety_issues: List[str]) -> List[str]:
        """Generate safety recommendations based on issues"""
        if not safety_issues:
            return ["Solution appears safe for automated execution"]
        
        recommendations = [
            "Manual review required before execution",
            "Test in staging environment first",
            "Have rollback plan ready",
            "Monitor system during execution"
        ]
        
        return recommendations
    
    def _generate_commit_message(self, solution: Dict[str, Any], incident_id: str) -> str:
        """Generate Git commit message"""
        root_cause = solution.get("root_cause", "Unknown issue")[:50]
        return f"fix: resolve incident {incident_id} - {root_cause}"
    
    def _generate_file_changes(self, solution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate file changes for GitLab MR"""
        # This would be expanded based on the specific solution
        # For now, create a basic incident report
        
        incident_report = {
            "incident_analysis": solution.get("analysis", ""),
            "root_cause": solution.get("root_cause", ""),
            "solution_applied": solution.get("solution", ""),
            "prevention_measures": solution.get("prevention", ""),
            "commands_executed": solution.get("commands", [])
        }
        
        return [
            {
                "file_path": f"incidents/incident_{int(datetime.now().timestamp())}.json",
                "content": json.dumps(incident_report, indent=2),
                "action": "create"
            }
        ]
    
    def _generate_mr_description(self, solution: Dict[str, Any], incident_id: str) -> str:
        """Generate merge request description"""
        return f"""## Incident Resolution: {incident_id}

### Root Cause
{solution.get('root_cause', 'Not identified')}

### Solution Applied
{solution.get('solution', 'No solution provided')}

### Commands Executed
```bash
{chr(10).join(solution.get('commands', []))}
```

### Prevention Measures
{solution.get('prevention', 'No prevention measures specified')}

### Testing
- [ ] Tested in staging environment
- [ ] Verified fix resolves the issue
- [ ] No side effects observed

### Rollback Plan
- [ ] Rollback procedure documented
- [ ] Rollback tested

---
*This MR was automatically generated by K-Fix incident resolution system.*
"""