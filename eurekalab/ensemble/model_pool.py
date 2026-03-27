"""ModelPool — registry of named LLM clients for ensemble execution."""

from __future__ import annotations

import logging
import os

from eurekalab.llm.base import LLMClient

logger = logging.getLogger(__name__)


class ModelPool:
    """Registry of named LLM clients. Each model gets a name (e.g., 'claude', 'gemini')."""

    def __init__(self) -> None:
        self._clients: dict[str, LLMClient] = {}
        self._model_names: dict[str, str] = {}
        self._backends: dict[str, str] = {}

    def register(self, name: str, client: LLMClient, model_name: str, backend: str) -> None:
        self._clients[name] = client
        self._model_names[name] = model_name
        self._backends[name] = backend
        logger.info("ModelPool: registered '%s' (model=%s, backend=%s)", name, model_name, backend)

    def get(self, name: str) -> LLMClient:
        if name not in self._clients:
            raise KeyError(f"Model '{name}' not registered in ModelPool. Available: {list(self._clients.keys())}")
        return self._clients[name]

    def get_model_name(self, name: str) -> str:
        return self._model_names[name]

    def get_backend(self, name: str) -> str:
        return self._backends[name]

    def list_available(self) -> list[str]:
        return list(self._clients.keys())

    @classmethod
    def create_from_config(cls) -> "ModelPool":
        """Build a ModelPool from environment variables.

        Reads ENSEMBLE_MODELS for the list of named models.
        For each model, reads MODEL_{NAME}_BACKEND, MODEL_{NAME}_API_KEY, MODEL_{NAME}_MODEL.
        Falls back to a single 'default' model from the standard LLM_BACKEND config.
        """
        from eurekalab.config import settings
        from eurekalab.llm.factory import create_client

        pool = cls()
        model_names_str = settings.ensemble_models.strip()

        if not model_names_str:
            # No ensemble configured — single default model
            client = create_client()
            pool.register("default", client, settings.active_model, settings.llm_backend)
            return pool

        for name in model_names_str.split(","):
            name = name.strip()
            if not name:
                continue
            prefix = f"MODEL_{name.upper()}_"
            backend = os.environ.get(f"{prefix}BACKEND", "anthropic")
            api_key = os.environ.get(f"{prefix}API_KEY", "")
            model = os.environ.get(f"{prefix}MODEL", "")

            try:
                if backend == "anthropic":
                    client = create_client(backend="anthropic", anthropic_api_key=api_key or None)
                    model = model or settings.active_model
                else:
                    client = create_client(
                        backend=backend,
                        openai_api_key=api_key or None,
                        openai_model=model or None,
                    )
                pool.register(name, client, model, backend)
            except Exception as e:
                logger.warning("Failed to create client for model '%s': %s", name, e)

        if not pool._clients:
            logger.warning("No ensemble models created — falling back to default")
            client = create_client()
            pool.register("default", client, settings.active_model, settings.llm_backend)

        return pool
