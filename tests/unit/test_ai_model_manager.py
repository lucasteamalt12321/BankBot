"""Tests for AI Model Manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from bot.ai.model_manager import (
    AIModelManager,
    ProviderConfig,
    ProviderType,
    AIResponse,
)


@pytest.fixture
def mock_env_no_providers(monkeypatch):
    """Mock environment with no AI providers configured."""
    monkeypatch.delenv("AI_PROVIDERS", raising=False)
    monkeypatch.delenv("HF_INFERENCE_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "false")


@pytest.fixture
def mock_env_hf_provider(monkeypatch):
    """Mock environment with Hugging Face provider."""
    monkeypatch.setenv("HF_INFERENCE_TOKEN", "hf_test_token")
    monkeypatch.setenv("HF_INFERENCE_MODEL", "test-model")
    monkeypatch.delenv("AI_PROVIDERS", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "false")


@pytest.fixture
def mock_env_multiple_providers(monkeypatch):
    """Mock environment with multiple providers via JSON."""
    providers_json = '''[
        {
            "name": "hf",
            "type": "huggingface",
            "api_key": "hf_test",
            "endpoint": "https://api-inference.huggingface.co/models",
            "model": "test-model",
            "timeout": 5
        },
        {
            "name": "openrouter",
            "type": "openrouter",
            "api_key": "or_test",
            "endpoint": "https://openrouter.ai/api/v1/chat/completions",
            "model": "test-model",
            "timeout": 5
        }
    ]'''
    monkeypatch.setenv("AI_PROVIDERS", providers_json)


def test_manager_init_no_providers(mock_env_no_providers):
    """Test manager initialization with no providers."""
    manager = AIModelManager()
    assert len(manager.providers) == 0
    assert not manager.is_available()


def test_manager_init_hf_provider(mock_env_hf_provider):
    """Test manager initialization with HF provider."""
    manager = AIModelManager()
    assert len(manager.providers) == 1
    assert manager.providers[0].name == "huggingface"
    assert manager.providers[0].provider_type == ProviderType.HUGGINGFACE
    assert manager.providers[0].api_key == "hf_test_token"
    assert manager.is_available()


def test_manager_init_multiple_providers(mock_env_multiple_providers):
    """Test manager initialization with multiple providers from JSON."""
    manager = AIModelManager()
    assert len(manager.providers) == 2
    assert manager.providers[0].name == "hf"
    assert manager.providers[1].name == "openrouter"
    assert manager.is_available()


def test_get_available_providers(mock_env_hf_provider):
    """Test getting list of available providers."""
    manager = AIModelManager()
    providers = manager.get_available_providers()
    assert providers == ["huggingface"]


def test_cache_key_generation():
    """Test cache key generation."""
    manager = AIModelManager()
    
    key1 = manager._get_cache_key("test prompt", user_id=123)
    key2 = manager._get_cache_key("test prompt", user_id=123)
    key3 = manager._get_cache_key("test prompt", user_id=456)
    key4 = manager._get_cache_key("different prompt", user_id=123)
    
    assert key1 == key2
    assert key1 != key3
    assert key1 != key4


def test_cache_response():
    """Test response caching."""
    manager = AIModelManager()
    
    prompt = "test prompt"
    response = "test response"
    
    # Cache response
    manager._cache_response(prompt, response, user_id=123)
    
    # Retrieve cached response
    cached = manager._get_cached_response(prompt, user_id=123)
    assert cached == response
    
    # Different user should not get cached response
    cached_other = manager._get_cached_response(prompt, user_id=456)
    assert cached_other is None


def test_cache_expiration(monkeypatch):
    """Test cache expiration."""
    manager = AIModelManager()
    manager.cache_ttl = 1  # 1 second TTL
    
    prompt = "test prompt"
    response = "test response"
    
    # Cache response
    manager._cache_response(prompt, response)
    
    # Should be cached
    cached = manager._get_cached_response(prompt)
    assert cached == response
    
    # Mock time to simulate expiration
    import time
    original_time = time.time
    monkeypatch.setattr(time, "time", lambda: original_time() + 2)
    
    # Should be expired
    cached_expired = manager._get_cached_response(prompt)
    assert cached_expired is None


@pytest.mark.asyncio
async def test_get_response_no_providers(mock_env_no_providers):
    """Test get_response with no providers configured."""
    manager = AIModelManager()
    
    with pytest.raises(RuntimeError, match="No AI providers configured"):
        await manager.get_response("test prompt")


@pytest.mark.asyncio
async def test_get_response_cached(mock_env_hf_provider):
    """Test get_response returns cached response."""
    manager = AIModelManager()
    
    # Pre-cache a response
    prompt = "test prompt"
    cached_text = "cached response"
    manager._cache_response(prompt, cached_text)
    
    # Should return cached response without calling API
    response = await manager.get_response(prompt)
    
    assert response.text == cached_text
    assert response.cached is True
    assert response.provider == "cache"


@pytest.mark.asyncio
async def test_get_response_hf_success(mock_env_hf_provider):
    """Test successful HF API call."""
    manager = AIModelManager()
    
    mock_response = MagicMock()
    mock_response.json.return_value = [{"generated_text": "AI response"}]
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        response = await manager.get_response("test prompt")
        
        assert response.text == "AI response"
        assert response.provider == "huggingface"
        assert response.cached is False


@pytest.mark.asyncio
async def test_get_response_provider_failover(mock_env_multiple_providers):
    """Test automatic failover to next provider on error."""
    manager = AIModelManager()
    
    # First provider fails
    mock_error_response = MagicMock()
    mock_error_response.status_code = 429
    
    # Second provider succeeds
    mock_success_response = MagicMock()
    mock_success_response.json.return_value = {
        "choices": [{"message": {"content": "Success from provider 2"}}]
    }
    mock_success_response.raise_for_status = MagicMock()
    
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (HF) fails
            raise httpx.HTTPStatusError(
                "Rate limited",
                request=MagicMock(),
                response=mock_error_response
            )
        else:
            # Second call (OpenRouter) succeeds
            return mock_success_response
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        response = await manager.get_response("test prompt")
        
        assert response.text == "Success from provider 2"
        assert response.provider == "openrouter"
        assert call_count == 2


@pytest.mark.asyncio
async def test_get_response_all_providers_fail(mock_env_hf_provider):
    """Test error when all providers fail."""
    manager = AIModelManager()
    
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_error_response
            )
        )
        
        with pytest.raises(RuntimeError, match="All AI providers failed"):
            await manager.get_response("test prompt")


@pytest.mark.asyncio
async def test_generate_sentence(mock_env_hf_provider):
    """Test generate_sentence method for Mom Module."""
    manager = AIModelManager()
    
    mock_response = MagicMock()
    mock_response.json.return_value = [{"generated_text": "Кот спит"}]
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        sentence = await manager.generate_sentence(theme="животные")
        
        assert sentence == "Кот спит"
        
        # Check that prompt includes theme
        call_args = mock_client.return_value.__aenter__.return_value.post.call_args
        payload = call_args[1]["json"]
        assert "животные" in payload["inputs"]
