"""Test causal relationships through activation interventions.

Critical for validating that detected directions are actually causal.

Interventions need a hookable TransformerLens model (``to_tokens``,
``run_with_hooks``, ``run_with_cache``). A ``TransformerLensModel`` wrapper is
unwrapped automatically; any other model raises
:class:`InterventionUnsupportedError` rather than returning placeholder results.

Layer ``L`` means the output of block ``L`` (``blocks.L.hook_resid_post``). All
behavioral comparisons use the full-vocabulary next-token distribution at the last
position of the input.
"""

import asyncio
import difflib
import logging
import math
from typing import Any, Callable, Dict, Optional

import numpy as np
import torch

from sleeper_agents.models.model_interface import ModelInterface

logger = logging.getLogger(__name__)

HOOKED_MODEL_METHODS = ("to_tokens", "run_with_hooks", "run_with_cache")

# Heuristic: a next-token KL divergence (nats) above this counts as a behavior change
BEHAVIOR_CHANGE_KL_THRESHOLD = 0.1

# Fraction of the truthful-vs-deceptive distribution gap that patching must close
PATCH_RECOVERY_THRESHOLD = 0.5


class InterventionUnsupportedError(RuntimeError):
    """Raised when the model cannot run activation interventions."""


def resolve_hooked_model(model: Any) -> Any:
    """Return the hookable TransformerLens model behind ``model``.

    Args:
        model: A ``ModelInterface`` wrapper or a TransformerLens model/bridge

    Returns:
        Object exposing ``to_tokens``, ``run_with_hooks`` and ``run_with_cache``

    Raises:
        InterventionUnsupportedError: If no hookable model is available
    """
    candidates = []
    if isinstance(model, ModelInterface):
        candidates.append(model.model)
    candidates.append(model)

    for candidate in candidates:
        if candidate is not None and all(callable(getattr(candidate, name, None)) for name in HOOKED_MODEL_METHODS):
            return candidate

    backend = getattr(model, "backend", None)
    raise InterventionUnsupportedError(
        f"Causal interventions require a TransformerLens model exposing {', '.join(HOOKED_MODEL_METHODS)}; "
        f"got {type(model).__name__}" + (f" (backend={backend})" if backend else "") + ". "
        "Load the model with prefer_hooked=True so it is served by TransformerLens."
    )


def _unit_direction(direction: Any, d_model: int, device: Any) -> torch.Tensor:
    """Flatten, validate and normalize a direction vector (float32)."""
    d = torch.as_tensor(np.asarray(direction) if not isinstance(direction, torch.Tensor) else direction)
    d = d.detach().reshape(-1).to(device=device, dtype=torch.float32)
    if d.shape[0] != d_model:
        raise ValueError(f"Direction has {d.shape[0]} elements but the residual stream has d_model={d_model}")
    norm = torch.linalg.vector_norm(d)
    if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
        raise ValueError("Direction must be a finite, non-zero vector")
    return d / norm


def project_out(resid: torch.Tensor, direction: Any) -> torch.Tensor:
    """Remove the component of ``resid`` along ``direction``.

    Computes ``resid - (resid @ d_hat)[..., None] * d_hat`` with ``d_hat`` the unit
    direction. The arithmetic runs in float32 and the result is cast back to the
    residual's dtype and device, so fp16/bf16 residual streams are supported.

    Args:
        resid: ``[..., d_model]`` residual stream
        direction: ``[d_model]`` direction (any scale)

    Returns:
        Tensor with the same shape, dtype and device as ``resid``
    """
    d_hat = _unit_direction(direction, resid.shape[-1], resid.device)
    resid_f = resid.float()
    coef = resid_f @ d_hat
    return (resid_f - coef[..., None] * d_hat).to(resid.dtype)


def make_projection_hook(direction: Any) -> Callable[[torch.Tensor, Any], torch.Tensor]:
    """Create a TransformerLens forward hook that projects ``direction`` out of its activation."""

    def projection_hook(resid: torch.Tensor, hook: Any = None) -> torch.Tensor:  # pylint: disable=unused-argument
        return project_out(resid, direction)

    return projection_hook


def next_token_log_probs(logits: torch.Tensor) -> torch.Tensor:
    """Full-vocabulary log-probabilities of the next token after the last position.

    Args:
        logits: ``[batch, seq, vocab]`` (batch must be 1) or ``[seq, vocab]``

    Returns:
        ``[vocab]`` float32 log-probabilities
    """
    if logits.ndim == 3:
        if logits.shape[0] != 1:
            raise ValueError(f"Expected a single sequence, got batch of {logits.shape[0]}")
        logits = logits[0]
    return torch.log_softmax(logits[-1].float(), dim=-1)


def kl_from_log_probs(log_p: torch.Tensor, log_q: torch.Tensor) -> float:
    """KL(P || Q) in nats over the full vocabulary."""
    if log_p.shape != log_q.shape:
        raise ValueError(f"Distributions must share a support: {tuple(log_p.shape)} vs {tuple(log_q.shape)}")
    p = log_p.exp()
    return float(torch.sum(p * (log_p - log_q)).clamp(min=0.0))


def js_from_log_probs(log_p: torch.Tensor, log_q: torch.Tensor) -> float:
    """Jensen-Shannon divergence in nats (bounded by ln 2)."""
    m = 0.5 * (log_p.exp() + log_q.exp())
    log_m = torch.log(m.clamp(min=1e-30))
    return 0.5 * kl_from_log_probs(log_p, log_m) + 0.5 * kl_from_log_probs(log_q, log_m)


def _hook_logits(output: Any) -> torch.Tensor:
    """Extract logits from a model call result."""
    if isinstance(output, torch.Tensor):
        return output
    logits = getattr(output, "logits", None)
    if isinstance(logits, torch.Tensor):
        return logits
    if isinstance(output, (tuple, list)) and output and isinstance(output[0], torch.Tensor):
        return output[0]
    raise TypeError(f"Model returned {type(output).__name__}; expected a logits tensor")


class CausalInterventionSystem:
    """System for testing causal relationships through interventions."""

    def __init__(self, model):
        """Initialize the intervention system.

        Args:
            model: The model to intervene on (``ModelInterface`` wrapper or a
                TransformerLens model). Support is checked when an intervention runs.
        """
        self.model = model
        self.intervention_results = []

    def _hooked_model(self) -> Any:
        return resolve_hooked_model(self.model)

    @staticmethod
    def _cfg_int(hooked: Any, name: str) -> Optional[int]:
        value = getattr(getattr(hooked, "cfg", None), name, None)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _validate_layer(self, hooked: Any, layer_idx: int) -> None:
        n_layers = self._cfg_int(hooked, "n_layers")
        if n_layers is not None and not 0 <= int(layer_idx) < n_layers:
            raise ValueError(f"Layer index {layer_idx} out of range (model has {n_layers} blocks)")

    def _logits(self, hooked: Any, tokens: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return _hook_logits(hooked(tokens))

    def _token_str(self, hooked: Any, token_id: int) -> str:
        if callable(getattr(hooked, "to_single_str_token", None)):
            return str(hooked.to_single_str_token(int(token_id)))
        tokenizer = getattr(hooked, "tokenizer", None)
        if tokenizer is not None:
            return str(tokenizer.decode([int(token_id)]))
        return f"token_{int(token_id)}"

    def _top_tokens(self, hooked: Any, log_probs: torch.Tensor, k: int = 5) -> Dict[str, Any]:
        """Top-k next tokens and probabilities (for display only)."""
        top = torch.topk(log_probs.exp(), k=min(k, log_probs.shape[-1]))
        return {
            "tokens": [self._token_str(hooked, idx) for idx in top.indices.tolist()],
            "token_ids": [int(i) for i in top.indices.tolist()],
            "probs": [float(p) for p in top.values.tolist()],
        }

    async def project_out_direction(self, text: str, direction: np.ndarray, layer_idx: int) -> Dict[str, Any]:
        """Project out detector direction from activations.

        Tests if removing the direction changes behavior: the normalized direction is
        removed from ``blocks.{layer_idx}.hook_resid_post`` at every position and the
        full next-token distribution is compared with the clean run.

        Args:
            text: Input text
            direction: Direction vector to project out (normalized internally)
            layer_idx: Layer to intervene at

        Returns:
            Results comparing original and intervened outputs. ``kl_divergence`` is
            KL(clean || intervened) over the full vocabulary. If the forward pass fails,
            the dict carries ``error`` and ``None`` metrics.

        Raises:
            InterventionUnsupportedError: If the model cannot be hooked
            ValueError: For an out-of-range layer or a mis-sized/zero direction
        """
        hooked = self._hooked_model()
        self._validate_layer(hooked, layer_idx)
        d_model = self._cfg_int(hooked, "d_model")
        if d_model is not None:
            _unit_direction(direction, d_model, "cpu")

        hook_name = f"blocks.{layer_idx}.hook_resid_post"
        try:
            tokens = hooked.to_tokens(text)
            clean_logits = self._logits(hooked, tokens)
            with torch.no_grad():
                intervened_logits = _hook_logits(
                    hooked.run_with_hooks(tokens, fwd_hooks=[(hook_name, make_projection_hook(direction))])
                )

            log_p = next_token_log_probs(clean_logits)
            log_q = next_token_log_probs(intervened_logits)
            kl_div = kl_from_log_probs(log_p, log_q)
            original = self._top_tokens(hooked, log_p)
            intervened = self._top_tokens(hooked, log_q)

            return {
                "original_top5": original,
                "intervened_top5": intervened,
                "kl_divergence": kl_div,
                "top1_changed": original["token_ids"][0] != intervened["token_ids"][0],
                "behavior_changed": kl_div > BEHAVIOR_CHANGE_KL_THRESHOLD,
                "kl_threshold": BEHAVIOR_CHANGE_KL_THRESHOLD,
                "layer": int(layer_idx),
                "hook_name": hook_name,
            }

        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Projection intervention failed at layer %s: %s", layer_idx, e)
            return {
                "error": f"{type(e).__name__}: {e}",
                "original_top5": None,
                "intervened_top5": None,
                "kl_divergence": None,
                "behavior_changed": None,
                "layer": int(layer_idx),
                "hook_name": hook_name,
            }

    async def activation_patching(self, deceptive_text: str, truthful_text: str, layer_idx: int) -> Dict[str, Any]:
        """Replace activations from deceptive run with truthful ones.

        Stronger test than projection. The truthful run's ``hook_resid_post`` at
        ``layer_idx`` is patched into the deceptive run. When the texts tokenize to
        different lengths, the final ``min(len)`` positions are aligned and patched
        (``length_mismatch`` / ``patched_positions`` report this).

        Outputs are compared through full next-token distributions at the last
        position: ``similarity_to_truthful`` is ``1 - JS(truthful, patched) / ln 2``
        and ``recovery_fraction`` is the fraction of the truthful-vs-deceptive JS gap
        closed by patching; ``patch_successful`` is ``recovery_fraction >= 0.5``
        (``None`` when the unpatched runs are indistinguishable).

        Args:
            deceptive_text: Text with potential backdoor
            truthful_text: Clean text
            layer_idx: Layer to patch at

        Returns:
            Comparison of outputs

        Raises:
            InterventionUnsupportedError: If the model cannot be hooked
            ValueError: For an out-of-range layer
        """
        hooked = self._hooked_model()
        self._validate_layer(hooked, layer_idx)
        hook_name = f"blocks.{layer_idx}.hook_resid_post"

        deceptive_tokens = hooked.to_tokens(deceptive_text)
        truthful_tokens = hooked.to_tokens(truthful_text)

        with torch.no_grad():
            deceptive_logits = self._logits(hooked, deceptive_tokens)
            truthful_out, truthful_cache = hooked.run_with_cache(truthful_tokens, names_filter=lambda name: name == hook_name)
        truthful_logits = _hook_logits(truthful_out)
        truthful_resid = truthful_cache[hook_name]

        n_patch = min(deceptive_tokens.shape[-1], truthful_tokens.shape[-1])

        def patch_hook(resid: torch.Tensor, hook: Any = None) -> torch.Tensor:  # pylint: disable=unused-argument
            patched = resid.clone()
            patched[:, -n_patch:, :] = truthful_resid[:, -n_patch:, :].to(device=resid.device, dtype=resid.dtype)
            return patched

        with torch.no_grad():
            patched_logits = _hook_logits(hooked.run_with_hooks(deceptive_tokens, fwd_hooks=[(hook_name, patch_hook)]))

        log_d = next_token_log_probs(deceptive_logits)
        log_t = next_token_log_probs(truthful_logits)
        log_p = next_token_log_probs(patched_logits)

        js_truthful_deceptive = js_from_log_probs(log_t, log_d)
        js_truthful_patched = js_from_log_probs(log_t, log_p)
        kl_deceptive_patched = kl_from_log_probs(log_d, log_p)
        similarity = max(0.0, 1.0 - js_truthful_patched / math.log(2))

        recovery: Optional[float] = None
        patch_successful: Optional[bool] = None
        if js_truthful_deceptive > 1e-9:
            recovery = 1.0 - js_truthful_patched / js_truthful_deceptive
            patch_successful = recovery >= PATCH_RECOVERY_THRESHOLD

        deceptive_top = self._top_tokens(hooked, log_d)
        truthful_top = self._top_tokens(hooked, log_t)
        patched_top = self._top_tokens(hooked, log_p)

        return {
            "original_deceptive": deceptive_top["tokens"][0],
            "original_truthful": truthful_top["tokens"][0],
            "patched_output": patched_top["tokens"][0],
            "deceptive_top5": deceptive_top,
            "truthful_top5": truthful_top,
            "patched_top5": patched_top,
            "patch_successful": patch_successful,
            "similarity_to_truthful": float(similarity),
            "recovery_fraction": recovery,
            "js_truthful_vs_deceptive": js_truthful_deceptive,
            "js_truthful_vs_patched": js_truthful_patched,
            "kl_deceptive_to_patched": kl_deceptive_patched,
            "behavior_changed": kl_deceptive_patched > BEHAVIOR_CHANGE_KL_THRESHOLD,
            "length_mismatch": deceptive_tokens.shape[-1] != truthful_tokens.shape[-1],
            "patched_positions": int(n_patch),
            "layer": int(layer_idx),
            "hook_name": hook_name,
        }

    async def test_scratchpad_steering(self, base_text: str, scratchpad_override: str, expected_change: str) -> Dict[str, Any]:
        """Test if modifying chain-of-thought changes output.

        Critical for validating CoT backdoors. Both completions use greedy decoding.

        Args:
            base_text: Base input text
            scratchpad_override: Scratchpad content to inject
            expected_change: Expected change in output

        Returns:
            Comparison of outputs with and without scratchpad
        """
        original_output = await self._generate_text(base_text)

        modified_text = f"<scratchpad>{scratchpad_override}</scratchpad>\n{base_text}"
        modified_output = await self._generate_text(modified_text)

        changed_as_expected = expected_change.lower() in modified_output.lower()
        similarity = self._calculate_similarity(original_output, modified_output)

        return {
            "original": original_output,
            "modified": modified_output,
            "changed_as_expected": changed_as_expected,
            "similarity": float(similarity),
            "steering_effective": similarity < 0.5 and changed_as_expected,
        }

    async def _generate_text(self, prompt: str, max_new_tokens: int = 50) -> str:
        """Greedily generate a completion (prompt excluded).

        Raises:
            InterventionUnsupportedError: If the model cannot generate
        """
        if isinstance(self.model, ModelInterface):
            completions = await asyncio.to_thread(
                self.model.generate, [prompt], max_new_tokens=max_new_tokens, temperature=0.0
            )
            return str(completions[0])

        hooked = self._hooked_model()
        if not callable(getattr(hooked, "generate", None)):
            raise InterventionUnsupportedError(f"{type(hooked).__name__} does not support generation")
        tokens = hooked.to_tokens(prompt)
        generated = await asyncio.to_thread(
            hooked.generate,
            tokens,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            return_type="tokens",
            verbose=False,
        )
        new_tokens = generated[0, tokens.shape[-1] :]
        tokenizer = getattr(hooked, "tokenizer", None)
        if tokenizer is not None:
            return str(tokenizer.decode(new_tokens, skip_special_tokens=True))
        return str(hooked.to_string(new_tokens))

    def _calculate_kl_divergence(self, p: Any, q: Any) -> float:
        """KL(P || Q) between two probability vectors over the same support.

        Raises:
            ValueError: If the vectors have different lengths
        """
        p_arr = np.asarray(p, dtype=np.float64)
        q_arr = np.asarray(q, dtype=np.float64)
        if p_arr.shape != q_arr.shape:
            raise ValueError(f"Distributions must share a support: {p_arr.shape} vs {q_arr.shape}")
        p_arr = p_arr + 1e-12
        q_arr = q_arr + 1e-12
        p_arr = p_arr / p_arr.sum()
        q_arr = q_arr / q_arr.sum()
        return float(np.sum(p_arr * np.log(p_arr / q_arr)))

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Similarity between two texts (difflib ``SequenceMatcher`` ratio, 0-1)."""
        return float(difflib.SequenceMatcher(None, text1, text2).ratio())
