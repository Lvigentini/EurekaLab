"""LLM backend abstraction — Anthropic native, OpenRouter, vLLM/SGLang."""

from eurekalab.llm.base import LLMClient, get_global_tokens, reset_global_tokens
from eurekalab.llm.factory import create_client

__all__ = ["LLMClient", "create_client", "get_global_tokens", "reset_global_tokens"]
