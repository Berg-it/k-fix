"""
Client LLM unifié pour K-Fix MVP
Support OpenAI GPT-4 avec fallback Claude 3.5
"""

import os
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    OPENAI = "openai"



@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    cost_estimate: float
    reasoning_steps: List[str] = None

class LLMClient:
    OPENAI_MODEL = "gpt-4o-mini"
    def __init__(self):
        self.primary_provider = LLMProvider.OPENAI
        self._setup_clients()
        
        self.total_tokens_used = 0
        self.total_cost = 0.0
        
    def _setup_clients(self):
        try:
            # OpenAI Client
            if os.getenv("OPENAI_API_KEY"):
                import openai
                self.openai_client = openai.AsyncOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY")
                )
                logger.info("✅ OpenAI client configured")
            else:
                self.openai_client = None
                logger.warning("⚠️ OpenAI API key not found")

        except ImportError as e:
            logger.error(f"❌ Missing LLM dependencies: {e}")
            raise
    
    async def generate_solution(
        self, 
        system_prompt: str, 
        context_prompt: str, 
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        Génère une solution via LLM avec fallback automatique
        """
    
        try:
            if self.primary_provider == LLMProvider.OPENAI and self.openai_client:
                return await self._call_openai(system_prompt, context_prompt, max_tokens)
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed: {e}")
            
        raise Exception("❌ All LLM providers failed")
    
    async def _call_openai(self, system_prompt: str, context_prompt: str, max_tokens: int) -> LLMResponse:
        """Call OpenAI GPT-4"""
        response = await self.openai_client.chat.completions.create(
            model=self.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.1 
        )
        
        tokens_used = response.usage.total_tokens
        cost = self._calculate_openai_cost(tokens_used)
        
        self._update_usage_stats(tokens_used, cost)
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=LLMProvider.OPENAI,
            model=self.OPENAI_MODEL,
            tokens_used=tokens_used,
            cost_estimate=cost
        )
    
    def _calculate_openai_cost(self, total_tokens: int) -> float:
        """Calcul coût OpenAI GPT-4 Turbo (approximatif)"""
        # Prix approximatif: $0.01/1K input + $0.03/1K output
        # Estimation: 70% input, 30% output
        input_tokens = int(total_tokens * 0.7)
        output_tokens = int(total_tokens * 0.3)
        
        cost = (input_tokens / 1000 * 0.01) + (output_tokens / 1000 * 0.03)
        return round(cost, 4)
    
    def _update_usage_stats(self, tokens: int, cost: float):
        """Mise à jour des statistiques d'usage"""
        self.total_tokens_used += tokens
        self.total_cost += cost
        
        logger.info(f"💰 LLM Call: {tokens} tokens, ${cost:.4f} | Total: {self.total_tokens_used} tokens, ${self.total_cost:.4f}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Statistiques d'usage pour monitoring"""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "primary_provider": self.primary_provider.value,
            "fallback_provider": self.fallback_provider.value
        }