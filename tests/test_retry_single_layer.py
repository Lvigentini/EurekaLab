"""Verify BaseAgent._call_model does NOT wrap retries (single layer only)."""
import ast
import inspect


def test_no_tenacity_in_call_model():
    """BaseAgent._call_model must not use tenacity — retry is in LLMClient only."""
    from eurekalab.agents.base import BaseAgent
    source = inspect.getsource(BaseAgent._call_model)
    assert "AsyncRetrying" not in source, "_call_model still uses tenacity double-retry"
    assert "Retrying" not in source, "_call_model still uses tenacity double-retry"


def test_no_tenacity_import():
    """The agents.base module should not import tenacity at all."""
    import eurekalab.agents.base as mod
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ""]
            for name in names:
                assert "tenacity" not in name, f"tenacity still imported: {name}"
