"""One prompt format for training data, evaluation, and probe fitting/inference.

A backdoor is trained, triggered, evaluated and probed on token sequences. If the
training data, the evaluation prompts and the probe contrast pairs are rendered in
different formats (for example bare text for training, ``Human:/Assistant:`` text for
the probes, and the tokenizer's chat template in deployment), the probe is fitted on
activations of a distribution the model never saw in that role. Every component
therefore builds its text through the helpers in this module, with one
``prompt_format`` value:

``"raw"``
    No chat template. This is what the 2026-09 experiments (``docs/results/``)
    actually ran and is the default of every existing experiment config
    (``BackdoorTrainingConfig``, ``SafetyTrainingConfig``, the defection-probe
    helpers), so those runs stay reproducible. Each component keeps the literal text
    it used in those runs: training and evaluation prompts are the bare prompt
    string with the completion tokens appended directly, and the generic defection
    contrast pairs use the paper's ``Human: <q>\\n\\nAssistant: <a>`` string
    (:data:`sleeper_agents.detection.defection_probe.CONTRAST_TEMPLATE`).
``"chat"``
    ``tokenizer.apply_chat_template`` with a single user turn and
    ``add_generation_prompt=True``; the response (completion, or contrast-pair
    answer) is appended directly after the generation prompt. Raises if the
    tokenizer has no chat template.
``"auto"``
    ``"chat"`` when the tokenizer has a chat template, else ``"raw"``.

For new experiments on chat/instruct models (e.g. Qwen2.5-*-Instruct) use
``"chat"`` (or ``"auto"``) and pass the same value to training, evaluation and the
probes; the value is recorded in ``training_config.json`` and in saved probe files.
"""

from typing import Any, Optional

RAW = "raw"
CHAT = "chat"
AUTO = "auto"

#: Accepted ``prompt_format`` values.
PROMPT_FORMATS = (RAW, CHAT, AUTO)

#: Default of the experiment configs: the format the 2026-09 runs used (no chat template).
DEFAULT_PROMPT_FORMAT = RAW


def has_chat_template(tokenizer: Any) -> bool:
    """Whether ``tokenizer`` can render a chat template."""
    return (
        tokenizer is not None
        and callable(getattr(tokenizer, "apply_chat_template", None))
        and bool(getattr(tokenizer, "chat_template", None))
    )


def resolve_prompt_format(prompt_format: str, tokenizer: Any = None) -> str:
    """Resolve ``prompt_format`` to ``"raw"`` or ``"chat"``.

    Raises:
        ValueError: For an unknown format, or ``"chat"`` with a tokenizer that has no chat template
    """
    if prompt_format not in PROMPT_FORMATS:
        raise ValueError(f"Unknown prompt_format {prompt_format!r}; expected one of {PROMPT_FORMATS}")
    if prompt_format == AUTO:
        return CHAT if has_chat_template(tokenizer) else RAW
    if prompt_format == CHAT and not has_chat_template(tokenizer):
        raise ValueError("prompt_format='chat' needs a tokenizer with a chat template (tokenizer.chat_template is unset)")
    return prompt_format


def format_prompt(user: str, tokenizer: Any = None, prompt_format: str = AUTO) -> str:
    """Text the model sees before its response to ``user``.

    ``"raw"`` returns ``user`` unchanged; ``"chat"`` renders one user turn with the
    tokenizer's chat template and the generation prompt (the assistant header).
    """
    if resolve_prompt_format(prompt_format, tokenizer) == RAW:
        return user
    text = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(text, str):
        raise TypeError(f"apply_chat_template(tokenize=False) returned {type(text).__name__}, expected str")
    return text


def format_exchange(
    user: str,
    assistant: str,
    tokenizer: Any = None,
    prompt_format: str = AUTO,
    raw_template: Optional[str] = None,
) -> str:
    """Prompt plus the start of a response, with nothing after the response.

    The last token of the returned text belongs to ``assistant`` (no end-of-turn
    token is appended), so last-token activations read the response itself.

    Args:
        user: User turn
        assistant: Response text
        tokenizer: Tokenizer (needed for ``"chat"``/``"auto"``)
        prompt_format: ``"raw"``, ``"chat"`` or ``"auto"``
        raw_template: ``str.format`` template with ``{question}`` and ``{answer}``
            used in raw mode; without it raw mode concatenates ``user + assistant``
            (the training-data convention)
    """
    if resolve_prompt_format(prompt_format, tokenizer) == RAW:
        if raw_template is not None:
            return raw_template.format(question=user, answer=assistant)
        return user + assistant
    return format_prompt(user, tokenizer, CHAT) + assistant


def add_special_tokens_for(prompt_format: str, tokenizer: Any = None) -> bool:
    """``add_special_tokens`` for tokenizing a formatted prompt at inference.

    Raw prompts keep the tokenizer default (True), as in the 2026-09 runs. A
    chat-template rendering already contains its special tokens (e.g. BOS), so they
    must not be added a second time.
    """
    return resolve_prompt_format(prompt_format, tokenizer) == RAW
