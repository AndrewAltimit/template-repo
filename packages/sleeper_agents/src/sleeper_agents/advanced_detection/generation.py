"""Shared text generation helper for the behavioral advanced-detection modules.

Behavioral tests (persona questions, red-team prompts) must score what the model
actually generated, never a canned response or the prompt text itself.
"""

from typing import Any, List


def generate_completions(model: Any, prompts: List[str], max_new_tokens: int = 128) -> List[str]:
    """Generate greedy completions for ``prompts``.

    ``model`` must expose ``generate(prompts: List[str], max_new_tokens=..., temperature=...)``
    returning one string per prompt that contains only the newly generated text
    (the ``ModelInterface.generate`` contract).

    Args:
        model: A ModelInterface-compatible model
        prompts: Prompts to complete
        max_new_tokens: Maximum number of new tokens per completion

    Returns:
        One completion per prompt (prompt text excluded)

    Raises:
        RuntimeError: If no model is available
        TypeError: If the model does not follow the ModelInterface.generate contract
    """
    if model is None:
        raise RuntimeError("No model loaded; behavioral testing requires a model to generate responses")

    generate = getattr(model, "generate", None)
    if not callable(generate):
        raise TypeError(f"{type(model).__name__} has no generate(); expected a ModelInterface-compatible model")

    outputs = generate(list(prompts), max_new_tokens=max_new_tokens, temperature=0.0)
    if not isinstance(outputs, list) or len(outputs) != len(prompts) or not all(isinstance(o, str) for o in outputs):
        raise TypeError(
            f"{type(model).__name__}.generate() must return one string per prompt "
            "(ModelInterface.generate contract); got "
            f"{type(outputs).__name__}"
        )
    return outputs


def generate_completion(model: Any, prompt: str, max_new_tokens: int = 128) -> str:
    """Generate a single greedy completion (prompt text excluded)."""
    return generate_completions(model, [prompt], max_new_tokens=max_new_tokens)[0]
