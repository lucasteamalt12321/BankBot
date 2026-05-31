"""AI Model Manager with automatic provider switching.

Supports multiple AI providers (Hugging Face, OpenRouter, Ollama) with automatic
fallback when one provider fails. Designed for Phase 2 modules (Mom, Universe, AI).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

import httpx


logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported AI provider types."""
    HUGGINGFACE = "huggingface"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    GROQ = "groq"


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""
    name: str
    provider_type: ProviderType
    api_key: Optional[str]
    endpoint: str
    model: str
    timeout: int = 10
    max_tokens: int = 150


@dataclass
class AIResponse:
    """Response from AI model."""
    text: str
    provider: str
    model: str
    cached: bool = False


class AIModelManager:
    """
    Manages multiple AI providers with automatic failover.
    
    Features:
    - Multiple provider support (HF, OpenRouter, Ollama)
    - Automatic switching on errors (429, 403, 500)
    - Response caching (5 minutes)
    - Configurable via environment variables
    
    Usage:
        manager = AIModelManager()
        response = await manager.get_response("Привет!", user_id=123)
        print(response.text)
    """
    
    def __init__(self):
        self.providers: list[ProviderConfig] = []
        self.cache: Dict[str, tuple[str, float]] = {}  # prompt -> (response, timestamp)
        self.cache_ttl = 300  # 5 minutes
        self._load_providers()
        
    def _load_providers(self) -> None:
        """Load provider configurations from environment."""
        # Try to load from AI_PROVIDERS JSON
        providers_json = os.getenv("AI_PROVIDERS")
        
        if providers_json:
            try:
                providers_data = json.loads(providers_json)
                for p in providers_data:
                    self.providers.append(ProviderConfig(
                        name=p.get("name", "unknown"),
                        provider_type=ProviderType(p.get("type", "huggingface")),
                        api_key=p.get("api_key"),
                        endpoint=p.get("endpoint", ""),
                        model=p.get("model", ""),
                        timeout=p.get("timeout", 10),
                        max_tokens=p.get("max_tokens", 150),
                    ))
                logger.info(f"Loaded {len(self.providers)} AI providers from AI_PROVIDERS")
                return
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse AI_PROVIDERS: {e}")
        
        # Fallback: load individual provider configs
        self._load_individual_providers()
        
    def _load_individual_providers(self) -> None:
        """Load providers from individual environment variables."""
        # Groq (add first for priority)
        groq_key = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        
        if groq_key:
            self.providers.append(ProviderConfig(
                name="groq",
                provider_type=ProviderType.GROQ,
                api_key=groq_key,
                endpoint="https://api.groq.com/openai/v1/chat/completions",
                model=groq_model,
                timeout=10,
                max_tokens=150,
            ))
            logger.info("Loaded Groq provider")
        
        # Hugging Face
        hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
        hf_model = os.getenv("HF_INFERENCE_MODEL", "microsoft/DialoGPT-small")
        
        if hf_token:
            self.providers.append(ProviderConfig(
                name="huggingface",
                provider_type=ProviderType.HUGGINGFACE,
                api_key=hf_token,
                endpoint="https://api-inference.huggingface.co/models",
                model=hf_model,
                timeout=10,
                max_tokens=150,
            ))
            logger.info("Loaded Hugging Face provider")
        
        # OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
        
        if openrouter_key:
            self.providers.append(ProviderConfig(
                name="openrouter",
                provider_type=ProviderType.OPENROUTER,
                api_key=openrouter_key,
                endpoint="https://openrouter.ai/api/v1/chat/completions",
                model=openrouter_model,
                timeout=10,
                max_tokens=150,
            ))
            logger.info("Loaded OpenRouter provider")
        
        # Ollama (local)
        ollama_endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "llama2")
        
        if os.getenv("OLLAMA_ENABLED", "false").lower() == "true":
            self.providers.append(ProviderConfig(
                name="ollama",
                provider_type=ProviderType.OLLAMA,
                api_key=None,
                endpoint=ollama_endpoint,
                model=ollama_model,
                timeout=15,
                max_tokens=150,
            ))
            logger.info("Loaded Ollama provider")
        
        if not self.providers:
            logger.warning("No AI providers configured. AI features will be limited.")
    
    def _get_cache_key(self, prompt: str, user_id: Optional[int] = None) -> str:
        """Generate cache key for prompt."""
        return f"{user_id or 'global'}:{prompt[:100]}"
    
    def _get_cached_response(self, prompt: str, user_id: Optional[int] = None) -> Optional[str]:
        """Get cached response if available and not expired."""
        cache_key = self._get_cache_key(prompt, user_id)
        
        if cache_key in self.cache:
            response, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                return response
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
        
        return None
    
    def _cache_response(self, prompt: str, response: str, user_id: Optional[int] = None) -> None:
        """Cache response with timestamp."""
        cache_key = self._get_cache_key(prompt, user_id)
        self.cache[cache_key] = (response, time.time())
        
        # Limit cache size to 100 entries
        if len(self.cache) > 100:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
    
    async def _call_huggingface(self, provider: ProviderConfig, prompt: str) -> str:
        """Call Hugging Face Inference API."""
        url = f"{provider.endpoint}/{provider.model}"
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": provider.max_tokens,
                "temperature": 0.7,
                "return_full_text": False,
            }
        }
        
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("generated_text", "").strip()
            elif isinstance(data, dict):
                return data.get("generated_text", "").strip()
            else:
                raise ValueError(f"Unexpected HF response format: {data}")
    
    async def _call_openrouter(self, provider: ProviderConfig, prompt: str) -> str:
        """Call OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": provider.max_tokens,
            "temperature": 0.7,
        }
        
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            response = await client.post(provider.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    
    async def _call_ollama(self, provider: ProviderConfig, prompt: str) -> str:
        """Call local Ollama API."""
        url = f"{provider.endpoint}/api/generate"
        payload = {
            "model": provider.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": provider.max_tokens,
                "temperature": 0.7,
            }
        }
        
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data.get("response", "").strip()
    
    async def _call_groq(self, provider: ProviderConfig, prompt: str) -> str:
        """Call Groq API (OpenAI-compatible)."""
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": provider.max_tokens,
            "temperature": 0.7,
        }
        
        async with httpx.AsyncClient(timeout=provider.timeout) as client:
            response = await client.post(provider.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    
    async def get_response(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        preferred_provider: Optional[str] = None,
    ) -> AIResponse:
        """
        Get AI response with automatic provider switching.
        
        Args:
            prompt: User prompt/question
            user_id: Optional user ID for caching
            preferred_provider: Optional preferred provider name
            
        Returns:
            AIResponse with text and metadata
            
        Raises:
            RuntimeError: If all providers fail
        """
        # Check cache first
        cached = self._get_cached_response(prompt, user_id)
        if cached:
            return AIResponse(
                text=cached,
                provider="cache",
                model="cached",
                cached=True,
            )
        
        # No providers configured
        if not self.providers:
            raise RuntimeError("No AI providers configured")
        
        # Try preferred provider first
        providers_to_try = list(self.providers)
        if preferred_provider:
            providers_to_try.sort(
                key=lambda p: 0 if p.name == preferred_provider else 1
            )
        
        last_error = None
        
        for provider in providers_to_try:
            try:
                logger.info(f"Trying provider: {provider.name} ({provider.model})")
                
                # Call appropriate provider
                if provider.provider_type == ProviderType.HUGGINGFACE:
                    text = await self._call_huggingface(provider, prompt)
                elif provider.provider_type == ProviderType.OPENROUTER:
                    text = await self._call_openrouter(provider, prompt)
                elif provider.provider_type == ProviderType.OLLAMA:
                    text = await self._call_ollama(provider, prompt)
                elif provider.provider_type == ProviderType.GROQ:
                    text = await self._call_groq(provider, prompt)
                else:
                    logger.warning(f"Unknown provider type: {provider.provider_type}")
                    continue
                
                # Success! Cache and return
                if text:
                    self._cache_response(prompt, text, user_id)
                    logger.info(f"✅ Success with provider: {provider.name}")
                    
                    return AIResponse(
                        text=text,
                        provider=provider.name,
                        model=provider.model,
                        cached=False,
                    )
                else:
                    logger.warning(f"Empty response from {provider.name}")
                    continue
                    
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                logger.warning(
                    f"Provider {provider.name} failed with HTTP {status_code}: {e}"
                )
                
                # Don't retry on certain errors
                if status_code in (401, 403):
                    logger.error(f"Authentication error for {provider.name}, skipping")
                
                last_error = e
                continue
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"Provider {provider.name} timeout/connection error: {e}")
                last_error = e
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error with provider {provider.name}: {e}")
                last_error = e
                continue
        
        # All providers failed
        error_msg = f"All AI providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    async def generate_sentence(self, theme: Optional[str] = None) -> str:
        """
        Generate simple sentence for Mom Module.
        
        Args:
            theme: Optional theme (e.g., "животные", "еда")
            
        Returns:
            Simple 3-4 word sentence in Russian
        """
        theme_text = f"Тема: {theme}. " if theme else ""
        prompt = (
            f"{theme_text}Сгенерируй очень простое предложение из 3-4 слов на русском языке "
            f"для ребёнка. Слова должны быть простыми и знакомыми. "
            f"Примеры: 'Кот спит', 'Мама моет пол', 'Я люблю чай'. "
            f"Ответь только предложением, без кавычек."
        )
        
        response = await self.get_response(prompt)
        return response.text
    
    def get_available_providers(self) -> list[str]:
        """Get list of available provider names."""
        return [p.name for p in self.providers]
    
    def is_available(self) -> bool:
        """Check if any providers are configured."""
        return len(self.providers) > 0
